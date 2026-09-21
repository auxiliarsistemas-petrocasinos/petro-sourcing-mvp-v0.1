from fastapi.testclient import TestClient

from app import db
from app.auth import (
    hash_password,
    verify_password,
)
from app.main import app


def test_password_hash_is_not_plaintext():
    password = (
        "Una-Contrasena-Segura-2026"
    )

    encoded = hash_password(
        password
    )

    assert password not in encoded

    assert verify_password(
        password,
        encoded,
    )

    assert not verify_password(
        "Contraseña incorrecta",
        encoded,
    )


def test_protected_api_requires_login():
    with TestClient(app) as client:
        response = client.get(
            "/api/history"
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Debes iniciar sesión."
    }


def test_login_session_and_logout(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        db,
        "DB_PATH",
        tmp_path / "research.db",
    )

    db.init_db()

    db.create_user(
        username="manuel.amado",
        display_name="Manuel Amado",
        password_hash=hash_password(
            "Clave-Segura-Piloto-2026"
        ),
    )

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "username": "manuel.amado",
                "password": (
                    "Clave-Segura-Piloto-2026"
                ),
            },
        )

        assert login.status_code == 200
        assert login.json()["user"] == {
            "id": 1,
            "username": "manuel.amado",
            "display_name": "Manuel Amado",
            "role": "user",
        }

        cookie = login.headers[
            "set-cookie"
        ].lower()

        assert "httponly" in cookie
        assert "samesite=strict" in cookie

        me = client.get(
            "/api/auth/me"
        )

        assert me.status_code == 200
        assert (
            me.json()["username"]
            == "manuel.amado"
        )

        logout = client.post(
            "/api/auth/logout"
        )

        assert logout.status_code == 200

        after_logout = client.get(
            "/api/auth/me"
        )

        assert (
            after_logout.status_code
            == 401
        )


def test_invalid_password_is_rejected(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        db,
        "DB_PATH",
        tmp_path / "research.db",
    )

    db.init_db()

    db.create_user(
        username="usuario.prueba",
        display_name="Usuario Prueba",
        password_hash=hash_password(
            "Clave-Segura-Piloto-2026"
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "username": (
                    "usuario.prueba"
                ),
                "password": (
                    "Clave-Incorrecta-2026"
                ),
            },
        )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Usuario o contraseña "
            "incorrectos."
        )
    }


def test_home_redirects_to_login_without_session():
    with TestClient(
        app,
        follow_redirects=False,
    ) as client:
        response = client.get("/")

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_page_is_available():
    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert "Iniciar sesión" in response.text
    assert "loginForm" in response.text
