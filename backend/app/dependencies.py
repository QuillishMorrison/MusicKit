from fastapi import Depends, Request

from .auth import require_session


def get_current_session(request: Request) -> dict:
    return require_session(request)


def get_current_user(session: dict = Depends(get_current_session)) -> dict:
    return session
