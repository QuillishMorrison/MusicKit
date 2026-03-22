import asyncio
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import HTTPException, status
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import MP3

from ..config import get_settings


def _result_to_track(entry: dict[str, Any]) -> dict[str, Any]:
    thumbnails = entry.get("thumbnails") or []
    thumbnail_url = thumbnails[-1]["url"] if thumbnails else entry.get("thumbnail")
    artist = entry.get("channel") or entry.get("uploader") or "YouTube"
    return {
        "source_id": entry["id"],
        "title": entry.get("title") or "Unknown title",
        "artist": artist,
        "duration_seconds": entry.get("duration"),
        "thumbnail_url": thumbnail_url,
        "source_url": f"https://www.youtube.com/watch?v={entry['id']}",
    }


async def search_tracks(query: str) -> list[dict[str, Any]]:
    settings = get_settings()

    def _run_search() -> list[dict[str, Any]]:
        options = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": False,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"ytsearch{settings.search_result_limit}:{query}", download=False)
        entries = info.get("entries") or []
        return [_result_to_track(entry) for entry in entries if entry]

    return await asyncio.to_thread(_run_search)


def sanitize_component(value: str) -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in (" ", "-", "_", ".", "(", ")")).strip()
    return cleaned[:120] or "Unknown"


async def download_track(track: dict[str, Any]) -> Path:
    settings = get_settings()
    artist_dir = settings.download_root / sanitize_component(track["artist"])
    artist_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(artist_dir / f"{sanitize_component(track['title'])} [{track['source_id']}].%(ext)s")

    def _run_download() -> Path:
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
                {"key": "FFmpegMetadata"},
            ],
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([track["source_url"]])
        return Path(output_template.replace("%(ext)s", "mp3"))

    downloaded_path = await asyncio.to_thread(_run_download)
    if not downloaded_path.exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Download failed")
    await asyncio.to_thread(apply_metadata, downloaded_path, track)
    return downloaded_path


def apply_metadata(file_path: Path, track: dict[str, Any]) -> None:
    try:
        audio = EasyID3(file_path)
    except ID3NoHeaderError:
        audio = MP3(file_path, ID3=ID3)
        audio.add_tags()
        audio.save()
        audio = EasyID3(file_path)

    audio["title"] = track["title"]
    audio["artist"] = track["artist"]
    audio["album"] = "Telegram Downloads"
    audio.save()

    if track.get("thumbnail_url"):
        try:
            import httpx

            image_bytes = httpx.get(track["thumbnail_url"], timeout=20).content
            tags = ID3(file_path)
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=image_bytes))
            tags.save(v2_version=3)
        except Exception:
            return
