"""Pytest fixtures for Phantom State tests."""

import pytest
from phantom_state import NarrativeStateEngine, EngineConfig


@pytest.fixture
def engine():
    """Create an in-memory engine for testing."""
    config = EngineConfig(db_path=":memory:")
    engine = NarrativeStateEngine(config)
    yield engine
    engine.close()


@pytest.fixture
def seeded_engine(engine):
    """Engine with basic data seeded."""
    # Create characters
    engine.register_character(
        "alice",
        "Alice",
        traits={"disposition": "curious"},
        voice={"patterns": ["asks questions"]},
    )
    engine.register_character(
        "bob",
        "Bob",
        traits={"disposition": "secretive"},
        voice={"patterns": ["speaks in riddles"]},
    )

    # Create moments
    engine.create_moment("m1", sequence=1, label="Opening")
    engine.create_moment("m2", sequence=2, label="Discovery")
    engine.create_moment("m3", sequence=3, label="Revelation")

    # Create initial take
    take_id = engine.create_take(notes="initial run")

    return engine, take_id
