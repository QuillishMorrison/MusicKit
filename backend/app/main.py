from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .auth import clear_session_cookie, create_session_token, set_session_cookie
from .config import get_settings
from .db import get_db, init_db
from .dependencies import get_current_user
from .schemas import DownloadRecord, DownloadRequest, DownloadResponse, HealthResponse, MeResponse, RelatedTrack, SearchResult, TelegramAuthRequest, UserResponse
from .services.navidrome import build_player_url, build_track_download_url
from .services.telegram import validate_init_data
from .services.yt import download_track, search_tracks

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url, settings.telegram_webapp_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(app=settings.app_name)


@app.post("/auth/telegram", response_model=UserResponse)
def auth_telegram(payload: TelegramAuthRequest, response: Response) -> UserResponse:
    telegram_user = validate_init_data(payload.init_data)
    session_payload = {
        "telegram_id": telegram_user.telegram_id,
        "username": telegram_user.username,
        "display_name": telegram_user.display_name,
    }
    token = create_session_token(session_payload, settings)
    set_session_cookie(response, token, settings)
    return UserResponse(
        telegram_id=telegram_user.telegram_id,
        username=telegram_user.username,
        display_name=telegram_user.display_name,
        navidrome_url=build_player_url(),
    )


@app.post("/auth/logout")
def logout(response: Response) -> dict[str, str]:
    clear_session_cookie(response, settings)
    return {"status": "ok"}


@app.get("/me", response_model=MeResponse)
def me(user: dict = Depends(get_current_user)) -> MeResponse:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT source_id, title, artist, duration_seconds, relative_path, status, source_url
            FROM downloads
            WHERE telegram_user_id = ?
            ORDER BY updated_at DESC
            LIMIT 5
            """,
            (user["telegram_id"],),
        ).fetchall()

    recent_downloads = [
        DownloadRecord(
            source_id=row["source_id"],
            title=row["title"],
            artist=row["artist"],
            duration_seconds=row["duration_seconds"],
            relative_path=row["relative_path"],
            status=row["status"],
            download_url=build_track_download_url(row["source_id"]),
        )
        for row in rows
    ]

    related_tracks = [
        RelatedTrack(title=row["title"], artist=row["artist"], source_url=row["source_url"])
        for row in rows[:3]
    ]

    return MeResponse(
        telegram_id=user["telegram_id"],
        username=user["username"],
        display_name=user["display_name"],
        navidrome_url=build_player_url(),
        recent_downloads=recent_downloads,
        related_tracks=related_tracks,
    )


@app.get("/search", response_model=list[SearchResult])
async def search(q: str, user: dict = Depends(get_current_user)) -> list[SearchResult]:
    if len(q.strip()) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query too short")
    results = await search_tracks(q.strip())
    return [SearchResult(**item) for item in results]


@app.post("/download", response_model=DownloadResponse)
async def download(payload: DownloadRequest, user: dict = Depends(get_current_user)) -> DownloadResponse:
    with get_db() as conn:
        existing = conn.execute(
            """
            SELECT source_id, title, artist, relative_path, status
            FROM downloads
            WHERE source_id = ?
            """,
            (payload.source_id,),
        ).fetchone()

        if existing:
            return DownloadResponse(
                status=existing["status"],
                title=existing["title"],
                artist=existing["artist"],
                source_id=existing["source_id"],
                relative_path=existing["relative_path"],
                player_url=build_player_url(),
                download_url=build_track_download_url(existing["source_id"]),
            )

        conn.execute(
            """
            INSERT INTO downloads (
                telegram_user_id, navidrome_username, source_id, source_url, title, artist,
                duration_seconds, thumbnail_url, relative_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["telegram_id"],
                user["username"],
                payload.source_id,
                payload.source_url,
                payload.title,
                payload.artist,
                payload.duration_seconds,
                payload.thumbnail_url,
                "",
                "processing",
            ),
        )

    try:
        downloaded_path = await download_track(payload.model_dump())
    except Exception:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE downloads
                SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE source_id = ?
                """,
                (payload.source_id,),
            )
        raise

    relative_path = downloaded_path.relative_to(settings.music_root).as_posix()

    with get_db() as conn:
        conn.execute(
            """
            UPDATE downloads
            SET relative_path = ?, status = 'ready', updated_at = CURRENT_TIMESTAMP
            WHERE source_id = ?
            """,
            (relative_path, payload.source_id),
        )

    return DownloadResponse(
        status="ready",
        title=payload.title,
        artist=payload.artist,
        source_id=payload.source_id,
        relative_path=relative_path,
        player_url=build_player_url(),
        download_url=build_track_download_url(payload.source_id),
    )


@app.get("/tracks/{source_id}/file")
def download_file(source_id: str, user: dict = Depends(get_current_user)) -> FileResponse:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT title, relative_path
            FROM downloads
            WHERE source_id = ? AND status = 'ready'
            """,
            (source_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    file_path = settings.music_root / row["relative_path"]
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")

    filename = Path(row["relative_path"]).name
    return FileResponse(path=file_path, filename=filename, media_type="audio/mpeg")


@app.get("/navidrome/auth")
def navidrome_auth(user: dict = Depends(get_current_user)) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["X-Navidrome-User"] = user["username"]
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
