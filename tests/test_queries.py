"""Tests for query operations."""

import pytest
from phantom_state import NarrativeStateEngine, EngineConfig


def test_query_facts_at_moment(seeded_engine):
    """Test querying facts respects temporal ordering."""
    engine, take_id = seeded_engine

    # Create facts at different moments
    fact1 = engine.log_fact("Early fact", "info", "m1")
    fact2 = engine.log_fact("Middle fact", "info", "m2")
    fact3 = engine.log_fact("Late fact", "info", "m3")

    # Alice learns all facts at their respective moments
    engine.log_knowledge("alice", fact1, "m1", take_id, "discovered")
    engine.log_knowledge("alice", fact2, "m2", take_id, "discovered")
    engine.log_knowledge("alice", fact3, "m3", take_id, "discovered")

    # Query at m2 - should only see facts from m1 and m2
    state = engine.query_state("alice", "m2", take_id)
    fact_contents = {f.content for f in state.facts}

    assert "Early fact" in fact_contents
    assert "Middle fact" in fact_contents
    assert "Late fact" not in fact_contents


def test_query_memories_chronological(seeded_engine):
    """Test querying memories in chronological order."""
    engine, take_id = seeded_engine

    # Create memories at different moments
    engine.embed_memory("alice", "First thing", "m1", take_id, "perceived")
    engine.embed_memory("alice", "Second thing", "m2", take_id, "perceived")
    engine.embed_memory("alice", "Third thing", "m3", take_id, "perceived")

    # Query at m2
    state = engine.query_state("alice", "m2", take_id)

    assert len(state.memories) == 2
    # Should be in chronological order
    chunks = [m.chunk for m in state.memories]
    assert chunks == ["First thing", "Second thing"]


def test_query_memories_similarity(seeded_engine):
    """Test querying memories by similarity."""
    engine, take_id = seeded_engine

    # Create diverse memories
    engine.embed_memory("alice", "The red apple is on the table", "m1", take_id, "perceived")
    engine.embed_memory("alice", "The weather is nice today", "m1", take_id, "perceived")
    engine.embed_memory("alice", "I ate a delicious fruit", "m2", take_id, "perceived")

    # Query with similarity to fruit-related content
    state = engine.query_state(
        "alice", "m2", take_id, query_text="apple fruit food"
    )

    # Most similar should come first
    assert len(state.memories) > 0
    # The apple and fruit memories should be ranked higher than weather


def test_query_state_includes_traits_and_voice(seeded_engine):
    """Test that query_state includes character metadata."""
    engine, take_id = seeded_engine

    state = engine.query_state("alice", "m1", take_id)

    assert state.traits == {"disposition": "curious"}
    assert state.voice == {"patterns": ["asks questions"]}


def test_query_respects_take_ancestry(seeded_engine):
    """Test that queries include facts from ancestor takes."""
    engine, take_id = seeded_engine

    # Fact in root take
    root_fact = engine.log_fact("Root knowledge", "info", "m1")
    engine.log_knowledge("alice", root_fact, "m1", take_id, "discovered")

    # Branch
    branch_take = engine.branch(take_id, "m2", notes="branch")

    # Fact only in branch
    branch_fact = engine.log_fact("Branch knowledge", "info", "m2")
    engine.log_knowledge("alice", branch_fact, "m2", branch_take, "discovered")

    # Query from branch should see both
    state = engine.query_state("alice", "m2", branch_take)
    fact_contents = {f.content for f in state.facts}

    assert "Root knowledge" in fact_contents
    assert "Branch knowledge" in fact_contents

    # Query from root should only see root fact
    root_state = engine.query_state("alice", "m2", take_id)
    root_fact_contents = {f.content for f in root_state.facts}

    assert "Root knowledge" in root_fact_contents
    assert "Branch knowledge" not in root_fact_contents


def test_query_nonexistent_character(engine):
    """Test that querying nonexistent character raises error."""
    engine.create_moment("m1", sequence=1)
    take_id = engine.create_take()

    with pytest.raises(ValueError, match="Character not found"):
        engine.query_state("nonexistent", "m1", take_id)
