"""Tests for branching (take) operations."""

import pytest
from phantom_state import NarrativeStateEngine, EngineConfig


def test_get_ancestry_single_take(engine):
    """Test ancestry with a single take."""
    take_id = engine.create_take(notes="root")

    ancestry = engine.get_ancestry(take_id)

    assert ancestry == [take_id]


def test_get_ancestry_chain(engine):
    """Test ancestry with a chain of takes."""
    engine.create_moment("m1", sequence=1)
    engine.create_moment("m2", sequence=2)

    root = engine.create_take(notes="root")
    child = engine.branch(root, "m1", notes="first branch")
    grandchild = engine.branch(child, "m2", notes="second branch")

    ancestry = engine.get_ancestry(grandchild)

    assert set(ancestry) == {root, child, grandchild}


def test_branch_creates_new_take(engine):
    """Test that branching creates a new take with correct parent."""
    engine.create_moment("m1", sequence=1)

    root = engine.create_take(notes="root")
    branch = engine.branch(root, "m1", notes="branched")

    takes = engine.list_takes()
    assert len(takes) == 2

    branch_take = next(t for t in takes if t.id == branch)
    assert branch_take.parent_take_id == root
    assert branch_take.branch_point == "m1"


def test_list_takes_by_status(engine):
    """Test filtering takes by status."""
    take1 = engine.create_take(notes="active take")
    take2 = engine.create_take(notes="to archive")

    engine.set_take_status(take2, "archived")

    active_takes = engine.list_takes(status="active")
    archived_takes = engine.list_takes(status="archived")

    assert len(active_takes) == 1
    assert active_takes[0].id == take1

    assert len(archived_takes) == 1
    assert archived_takes[0].id == take2


def test_set_take_status_invalid(engine):
    """Test that invalid status raises error."""
    take_id = engine.create_take()

    with pytest.raises(ValueError):
        engine.set_take_status(take_id, "invalid_status")


def test_branch_isolation(seeded_engine):
    """Test that branches are isolated from each other."""
    engine, root_take = seeded_engine

    # Log a fact in root take
    fact1 = engine.log_fact("Root fact", "test", "m1")
    engine.log_knowledge("alice", fact1, "m1", root_take, "discovered")

    # Branch at m2
    branch_take = engine.branch(root_take, "m2", notes="branch")

    # Log different fact in branch
    fact2 = engine.log_fact("Branch fact", "test", "m2")
    engine.log_knowledge("alice", fact2, "m2", branch_take, "discovered")

    # Query both takes at m2
    root_state = engine.query_state("alice", "m2", root_take)
    branch_state = engine.query_state("alice", "m2", branch_take)

    # Root should only have fact1
    root_fact_contents = {f.content for f in root_state.facts}
    assert "Root fact" in root_fact_contents
    assert "Branch fact" not in root_fact_contents

    # Branch should have both (inherits from root)
    branch_fact_contents = {f.content for f in branch_state.facts}
    assert "Root fact" in branch_fact_contents
    assert "Branch fact" in branch_fact_contents
