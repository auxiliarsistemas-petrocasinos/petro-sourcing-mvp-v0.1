from app import db


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

    research_id = db.save_research(
        "Necesito comprar un producto.",
        {"value": 1},
    )

    updated = db.update_research(
        research_id,
        {"value": 2},
    )

    assert updated is True

    stored = db.get_research(research_id)

    assert stored is not None
    assert stored["result"] == {"value": 2}

    assert db.update_research(
        999_999,
        {"value": 3},
    ) is False
