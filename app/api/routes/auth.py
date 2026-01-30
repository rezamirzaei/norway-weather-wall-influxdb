from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import ReadUser, authenticate_user, get_settings
from app.core.config import Settings
from app.core.security import create_access_token
from app.schemas.auth import Token, User

router = APIRouter(prefix="/auth")


@router.post("/token", response_model=Token)
def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Token:
    user = authenticate_user(
        username=form_data.username, password=form_data.password, settings=settings
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        subject=user.username,
        scopes=user.scopes,
        settings=settings,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=User)
def read_users_me(user: ReadUser) -> User:
    return user
