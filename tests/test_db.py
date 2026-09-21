from app import db


def create_test_user(
    username: str,
) -> int:
    return db.create_user(
        username=username,
        display_name=username,
        password_hash="test-hash",
    )


def test_update_research_replaces_persisted_payload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        db,
        "DB_PATH",
        tmp_path / "research.db",
    )

    db.init_db()

    user_id = create_test_user(
        "usuario.uno"
    )

    research_id = db.save_research(
        "Necesito comprar un producto.",
        {"value": 1},
        user_id,
    )

    updated = db.update_research(
        research_id,
        {"value": 2},
        user_id,
    )

    assert updated is True

    stored = db.get_research(
        research_id,
        user_id,
    )

    assert stored is not None
    assert stored["result"] == {
        "value": 2
    }

    assert (
        db.update_research(
            999_999,
            {"value": 3},
            user_id,
        )
        is False
    )


def test_research_is_isolated_by_user(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        db,
        "DB_PATH",
        tmp_path / "research.db",
    )

    db.init_db()

    user_a = create_test_user(
        "usuario.a"
    )
    user_b = create_test_user(
        "usuario.b"
    )

    research_a = db.save_research(
        "Compra privada usuario A.",
        {"owner": "A"},
        user_a,
    )

    research_b = db.save_research(
        "Compra privada usuario B.",
        {"owner": "B"},
        user_b,
    )

    history_a = db.list_research(
        user_a
    )
    history_b = db.list_research(
        user_b
    )

    assert [
        row["id"]
        for row in history_a
    ] == [research_a]

    assert [
        row["id"]
        for row in history_b
    ] == [research_b]

    assert (
        db.get_research(
            research_b,
            user_a,
        )
        is None
    )

    assert (
        db.get_research(
            research_a,
            user_b,
        )
        is None
    )

    assert (
        db.update_research(
            research_b,
            {"hacked": True},
            user_a,
        )
        is False
    )

    stored_b = db.get_research(
        research_b,
        user_b,
    )

    assert stored_b is not None
    assert stored_b["result"] == {
        "owner": "B"
    }


def test_legacy_research_is_not_visible_to_users(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        db,
        "DB_PATH",
        tmp_path / "research.db",
    )

    db.init_db()

    user_id = create_test_user(
        "usuario.nuevo"
    )

    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO research(
                created_at,
                query,
                result_json,
                user_id
            )
            VALUES (?, ?, ?, NULL)
            """,
            (
                "2026-09-21T00:00:00+00:00",
                "Investigación histórica",
                "{}",
            ),
        )
        conn.commit()

    assert db.list_research(
        user_id
    ) == []
