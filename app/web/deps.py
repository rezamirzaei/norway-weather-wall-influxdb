from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Form, HTTPException, Request, status

from app.schemas.auth import User

SESSION_USER_KEY = "user"
CSRF_TOKEN_KEY = "csrf_token"


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_TOKEN_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_TOKEN_KEY] = token
    return token


def validate_csrf_token(request: Request, csrf_token: str) -> None:
    expected = request.session.get(CSRF_TOKEN_KEY)
    if not isinstance(expected, str) or not secrets.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")


def csrf_protect(
    request: Request,
    csrf_token: Annotated[str, Form()],
) -> None:
    validate_csrf_token(request, csrf_token)


def get_session_user(request: Request) -> User | None:
    raw = request.session.get(SESSION_USER_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return User.model_validate(raw)
    except Exception:
        return None


def require_session_user(request: Request) -> User:
    user = get_session_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/ui/login"},
        )
    return user

