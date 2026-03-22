from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., alias="initData")


class UserResponse(BaseModel):
    telegram_id: str
    username: str
    display_name: str
    navidrome_url: str


class SearchResult(BaseModel):
    source_id: str
    title: str
    artist: str
    duration_seconds: int | None
    thumbnail_url: str | None
    source_url: str


class DownloadRequest(BaseModel):
    source_id: str
    source_url: str
    title: str
    artist: str
    duration_seconds: int | None = None
    thumbnail_url: str | None = None


class DownloadResponse(BaseModel):
    status: str
    title: str
    artist: str
    source_id: str
    relative_path: str
    player_url: str
    download_url: str


class DownloadRecord(BaseModel):
    source_id: str
    title: str
    artist: str
    duration_seconds: int | None
    relative_path: str
    status: str
    download_url: str


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str


class RelatedTrack(BaseModel):
    title: str
    artist: str
    source_url: str


class MeResponse(UserResponse):
    recent_downloads: list[DownloadRecord]
    related_tracks: list[RelatedTrack]
