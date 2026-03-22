import hashlib
import hmac
import json
from dataclasses import dataclass
from time import time
from urllib.parse import parse_qsl

from fastapi import HTTPException, status

from ..config import get_settings


@dataclass
class TelegramUser:
    telegram_id: str
    username: str
    display_name: str
    raw: dict


def validate_init_data(init_data: str) -> TelegramUser:
    settings = get_settings()
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    auth_date = parsed.get("auth_date")
    user_payload = parsed.get("user")

    if not received_hash or not auth_date or not user_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incomplete Telegram data")

    if int(time()) - int(auth_date) > 24 * 60 * 60:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram data expired")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram signature")

    user = json.loads(user_payload)
    first_name = user.get("first_name", "").strip()
    last_name = user.get("last_name", "").strip()
    display_name = " ".join(part for part in [first_name, last_name] if part).strip() or user.get("username") or "Telegram User"
    username = f"tg_{user['id']}"

    return TelegramUser(
        telegram_id=str(user["id"]),
        username=username,
        display_name=display_name,
        raw=user,
    )
