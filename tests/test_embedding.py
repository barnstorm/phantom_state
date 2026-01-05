"""Tests for embedding and memory operations."""

import pytest
from phantom_state import NarrativeStateEngine, EngineConfig


def test_embed_memory(seeded_engine):
    """Test embedding a memory."""
    engine, take_id = seeded_engine

    memory_id = engine.embed_memory(
        character_id="alice",
        chunk="I saw something strange in the garden.",
        moment_id="m1",
        take_id=take_id,
        chunk_type="perceived",
        tags={"location": "garden"},
    )

    assert memory_id is not None

    # Check metadata was stored
    row = engine.db.execute(
        "SELECT * FROM memory_metadata WHERE id = ?", (memory_id,)
    ).fetchone()
    assert row["chunk"] == "I saw something strange in the garden."
    assert row["chunk_type"] == "perceived"

    # Check vector was stored
    vec_row = engine.db.execute(
        "SELECT rowid FROM alice_vec WHERE rowid = ?", (memory_id,)
    ).fetchone()
    assert vec_row is not None


def test_dialogue(seeded_engine):
    """Test dialogue convenience method."""
    engine, take_id = seeded_engine

    result = engine.dialogue(
        speaker="alice",
        content="Hello Bob, how are you?",
        moment_id="m1",
        take_id=take_id,
        listeners=["bob"],
        speaker_tags={"tone": "friendly"},
        listener_tags={"reaction": "surprised"},
    )

    assert "speaker_memory_id" in result
    assert "listener_memory_ids" in result
    assert len(result["listener_memory_ids"]) == 1

    # Check speaker memory is 'said'
    speaker_mem = engine.db.execute(
        "SELECT chunk_type FROM memory_metadata WHERE id = ?",
        (result["speaker_memory_id"],),
    ).fetchone()
    assert speaker_mem["chunk_type"] == "said"

    # Check listener memory is 'heard'
    listener_mem = engine.db.execute(
        "SELECT chunk_type FROM memory_metadata WHERE id = ?",
        (result["listener_memory_ids"][0],),
    ).fetchone()
    assert listener_mem["chunk_type"] == "heard"


def test_dialogue_multiple_listeners(seeded_engine):
    """Test dialogue with multiple listeners."""
    engine, take_id = seeded_engine

    # Register a third character
    engine.register_character("charlie", "Charlie")

    result = engine.dialogue(
        speaker="alice",
        content="Everyone listen up!",
        moment_id="m1",
        take_id=take_id,
        listeners=["bob", "charlie"],
    )

    assert len(result["listener_memory_ids"]) == 2


def test_memory_not_shared_between_characters(seeded_engine):
    """Test that memories are character-specific."""
    engine, take_id = seeded_engine

    # Only Alice perceives something
    engine.embed_memory(
        character_id="alice",
        chunk="A secret door opens",
        moment_id="m1",
        take_id=take_id,
        chunk_type="perceived",
    )

    # Query both characters
    alice_state = engine.query_state("alice", "m1", take_id)
    bob_state = engine.query_state("bob", "m1", take_id)

    assert len(alice_state.memories) == 1
    assert alice_state.memories[0].chunk == "A secret door opens"

    assert len(bob_state.memories) == 0
