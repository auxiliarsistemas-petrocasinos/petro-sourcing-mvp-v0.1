from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "research.db"
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL
                    UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                query TEXT NOT NULL,
                result_json TEXT NOT NULL,
                user_id INTEGER
            )
            """
        )

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(research)"
            ).fetchall()
        }

        if "user_id" not in columns:
            conn.execute(
                """
                ALTER TABLE research
                ADD COLUMN user_id INTEGER
                """
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_research_user_id
            ON research(user_id, id DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_sessions_user_id
            ON sessions(user_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_sessions_expires_at
            ON sessions(expires_at)
            """
        )

        conn.commit()


def create_user(
    username: str,
    display_name: str,
    password_hash: str,
    role: str = "user",
) -> int:
    if role not in {"user", "admin"}:
        raise ValueError(
            "Rol de usuario no soportado."
        )

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO users(
                username,
                display_name,
                password_hash,
                role,
                active,
                created_at
            )
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (
                username,
                display_name,
                password_hash,
                role,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_user_by_username(
    username: str,
) -> dict | None:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                id,
                username,
                display_name,
                password_hash,
                role,
                active,
                created_at
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username,),
        ).fetchone()

    return dict(row) if row else None


def get_user_by_id(
    user_id: int,
) -> dict | None:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                id,
                username,
                display_name,
                role,
                active,
                created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return dict(row) if row else None


def list_users() -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                id,
                username,
                display_name,
                role,
                active,
                created_at
            FROM users
            ORDER BY username
            """
        ).fetchall()

    return [dict(row) for row in rows]


def update_user_password(
    user_id: int,
    password_hash: str,
) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (
                password_hash,
                user_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def set_user_active(
    user_id: int,
    active: bool,
) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE users
            SET active = ?
            WHERE id = ?
            """,
            (
                1 if active else 0,
                user_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def create_session(
    token_hash: str,
    user_id: int,
    created_at: str,
    expires_at: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions(
                token_hash,
                user_id,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                token_hash,
                user_id,
                created_at,
                expires_at,
            ),
        )
        conn.commit()


def get_session_user(
    token_hash: str,
    now_iso: str,
) -> dict | None:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                users.id,
                users.username,
                users.display_name,
                users.role,
                users.active,
                users.created_at
            FROM sessions
            JOIN users
                ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.expires_at > ?
              AND users.active = 1
            """,
            (
                token_hash,
                now_iso,
            ),
        ).fetchone()

    return dict(row) if row else None


def delete_session(
    token_hash: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            DELETE FROM sessions
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        conn.commit()


def delete_sessions_for_user(
    user_id: int,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            DELETE FROM sessions
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()


def delete_expired_sessions(
    now_iso: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            DELETE FROM sessions
            WHERE expires_at <= ?
            """,
            (now_iso,),
        )
        conn.commit()


def save_research(
    query: str,
    payload: dict,
    user_id: int,
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO research(
                created_at,
                query,
                result_json,
                user_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                query,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                user_id,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_research(
    research_id: int,
    payload: dict,
    user_id: int,
) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE research
            SET result_json = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                research_id,
                user_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def list_research(
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                id,
                created_at,
                query
            FROM research
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_research(
    research_id: int,
    user_id: int,
) -> dict | None:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                id,
                created_at,
                query,
                result_json
            FROM research
            WHERE id = ?
              AND user_id = ?
            """,
            (
                research_id,
                user_id,
            ),
        ).fetchone()

    if not row:
        return None

    data = dict(row)
    data["result"] = json.loads(
        data.pop("result_json")
    )
    return data
