from urllib.parse import quote

from ..config import get_settings


def build_player_url() -> str:
    return f"{get_settings().navidrome_external_base_url}/"


def build_track_download_url(source_id: str) -> str:
    return f"/api/tracks/{quote(source_id)}/file"
