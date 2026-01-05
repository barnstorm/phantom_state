"""Tests for schema creation and basic operations."""

import pytest
from phantom_state import NarrativeStateEngine, EngineConfig


def test_engine_creates_tables(engine):
    """Verify all core tables are created."""
    tables = engine.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {row["name"] for row in tables}

    assert "moments" in table_names
    assert "takes" in table_names
    assert "characters" in table_names
    assert "facts" in table_names
    assert "knowledge_events" in table_names
    assert "memory_metadata" in table_names


def test_create_moment(engine):
    """Test moment creation."""
    moment_id = engine.create_moment("scene1", sequence=1, label="Opening scene")

    assert moment_id == "scene1"

    row = engine.db.execute("SELECT * FROM moments WHERE id = ?", ("scene1",)).fetchone()
    assert row["sequence"] == 1
    assert row["label"] == "Opening scene"


def test_moment_sequence_must_be_unique(engine):
    """Test that moment sequences must be unique."""
    engine.create_moment("m1", sequence=1)

    with pytest.raises(Exception):  # sqlite3.IntegrityError
        engine.create_moment("m2", sequence=1)


def test_create_take(engine):
    """Test take creation."""
    take_id = engine.create_take(notes="first take")

    assert take_id is not None

    row = engine.db.execute("SELECT * FROM takes WHERE id = ?", (take_id,)).fetchone()
    assert row["status"] == "active"
    assert row["notes"] == "first take"


def test_register_character(engine):
    """Test character registration."""
    char_id = engine.register_character(
        "protagonist",
        "The Hero",
        traits={"brave": True},
        voice={"style": "heroic"},
    )

    assert char_id == "protagonist"

    # Check character table
    row = engine.db.execute(
        "SELECT * FROM characters WHERE id = ?", ("protagonist",)
    ).fetchone()
    assert row["name"] == "The Hero"

    # Check vector table was created
    tables = engine.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_vec'"
    ).fetchall()
    table_names = {row["name"] for row in tables}
    assert "protagonist_vec" in table_names


def test_log_fact(engine):
    """Test fact logging."""
    engine.create_moment("m1", sequence=1)

    fact_id = engine.log_fact(
        content="The treasure is hidden",
        category="secret",
        moment_id="m1",
    )

    assert fact_id is not None

    row = engine.db.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
    assert row["content"] == "The treasure is hidden"
    assert row["category"] == "secret"


def test_log_knowledge(engine):
    """Test knowledge event logging."""
    engine.register_character("char1", "Character 1")
    engine.create_moment("m1", sequence=1)
    take_id = engine.create_take()
    fact_id = engine.log_fact("Secret info", "secret", "m1")

    ke_id = engine.log_knowledge(
        character_id="char1",
        fact_id=fact_id,
        moment_id="m1",
        take_id=take_id,
        source="discovered",
    )

    assert ke_id is not None

    row = engine.db.execute(
        "SELECT * FROM knowledge_events WHERE id = ?", (ke_id,)
    ).fetchone()
    assert row["character_id"] == "char1"
    assert row["source"] == "discovered"
