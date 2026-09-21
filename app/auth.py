from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response

from .db import (
    create_session,
    delete_expired_sessions,
    delete_session,
    get_session_user,
    get_user_by_username,
)

load_dotenv()

SESSION_COOKIE_NAME = "petro_session"
PASSWORD_ITERATIONS = int(
    os.getenv("AUTH_PBKDF2_ITERATIONS", "600000")
)
SESSION_HOURS = int(
    os.getenv("AUTH_SESSION_HOURS", "12")
)

USERNAME_PATTERN = re.compile(
    r"^[a-z0-9._-]{3,64}$"
)


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)

    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "El usuario debe tener entre 3 y 64 caracteres "
            "y solo puede contener letras, números, punto, "
            "guion y guion bajo."
        )

    return normalized


def validate_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError(
            "La contraseña debe tener al menos 12 caracteres."
        )

    if len(password) > 128:
        raise ValueError(
            "La contraseña no puede superar 128 caracteres."
        )


def hash_password(password: str) -> str:
    validate_password(password)

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )

    return "$".join(
        (
            "pbkdf2_sha256",
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(
    password: str,
    encoded: str,
) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = (
            encoded.split("$", 3)
        )

        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.urlsafe_b64decode(
            salt_b64.encode("ascii")
        )
        expected = base64.urlsafe_b64decode(
            digest_b64.encode("ascii")
        )

        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(
        calculated,
        expected,
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def authenticate_user(
    username: str,
    password: str,
) -> dict | None:
    normalized = normalize_username(username)
    user = get_user_by_username(normalized)

    if not user:
        # Trabajo criptográfico deliberado para reducir
        # diferencias de tiempo entre usuario inexistente
        # y contraseña incorrecta.
        hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            b"petro-auth-dummy",
            PASSWORD_ITERATIONS,
        )
        return None

    if not user["active"]:
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return None

    return user


def create_user_session(
    user_id: int,
) -> tuple[str, int]:
    delete_expired_sessions(
        datetime.now(UTC).isoformat()
    )

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(
        hours=SESSION_HOURS
    )

    create_session(
        token_hash=_token_hash(token),
        user_id=user_id,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    )

    return token, int(
        timedelta(hours=SESSION_HOURS).total_seconds()
    )


def get_authenticated_user(
    request: Request,
) -> dict | None:
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if not token:
        return None

    return get_session_user(
        _token_hash(token),
        datetime.now(UTC).isoformat(),
    )


def require_user(
    request: Request,
) -> dict:
    user = get_authenticated_user(request)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Debes iniciar sesión.",
        )

    return user


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


def set_session_cookie(
    response: Response,
    token: str,
    max_age: int,
) -> None:
    secure = (
        os.getenv(
            "AUTH_COOKIE_SECURE",
            "false",
        ).strip().lower()
        in {"1", "true", "yes", "on"}
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )


def revoke_request_session(
    request: Request,
) -> None:
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if token:
        delete_session(
            _token_hash(token)
        )


def clear_session_cookie(
    response: Response,
) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )
