import os
from typing import Any

from flask import Response, request

ACCESS_TOKEN_COOKIE = "ri_access_token"


def cookie_secure() -> bool:
    """Default false so HttpOnly cookies work on local http://; set COOKIE_SECURE=true in production."""
    explicit = os.getenv("COOKIE_SECURE", "").strip().lower()
    return explicit in ("1", "true", "yes")


def set_auth_cookie(response: Response, token: str) -> None:
    from app.real_interview.backend.auth.jwt_auth import jwt_expire_seconds

    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        httponly=True,
        secure=cookie_secure(),
        samesite="Lax",
        max_age=jwt_expire_seconds(),
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        "",
        httponly=True,
        secure=cookie_secure(),
        samesite="Lax",
        max_age=0,
        path="/",
    )


def get_cookie_token() -> str | None:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None
