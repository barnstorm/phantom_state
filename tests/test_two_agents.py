"""Validation test: Two agents with bounded knowledge.

This is the core premise test from the specification.
If this test passes, the fundamental architecture is correct.
"""

import pytest
from phantom_state import NarrativeStateEngine, EngineConfig


def test_bounded_knowledge():
    """
    Two characters, divergent knowledge.
    Verify retrieval returns only appropriate state.
    """
    engine = NarrativeStateEngine(EngineConfig(db_path=":memory:", embedding_backend="hash"))

    try:
        engine.register_character("a", "Character A", {}, {})
        engine.register_character("b", "Character B", {}, {})

        take = engine.create_take()
        m1 = engine.create_moment("m1", 1)

        # Fact only A knows
        fact = engine.log_fact("The treasure is buried under the oak", "secret", "m1")
        engine.log_knowledge("a", fact, "m1", take, "discovered")

        # Query both
        a_state = engine.query_state("a", "m1", take)
        b_state = engine.query_state("b", "m1", take)

        assert len(a_state.facts) == 1
        assert a_state.facts[0].content == "The treasure is buried under the oak"

        assert len(b_state.facts) == 0  # B doesn't know
    finally:
        engine.close()


def test_shared_experience_separate_knowledge():
    """
    Characters can share experiences but have different factual knowledge.
    """
    engine = NarrativeStateEngine(EngineConfig(db_path=":memory:", embedding_backend="hash"))

    try:
        engine.register_character("webb", "Dr. Webb",
            traits={"disposition": "curious", "role": "investigator"},
            voice={"patterns": ["professorial", "asks probing questions"]}
        )
        engine.register_character("alex", "Alex",
            traits={"disposition": "guarded", "coping": "control"},
            voice={"patterns": ["clinical self-talk", "short sentences under stress"]}
        )

        take = engine.create_take(notes="initial run")
        m1 = engine.create_moment("scene1_start", sequence=1, label="First meeting")

        # Establish a fact only Webb knows
        fact_id = engine.log_fact(
            "Alex's father was part of the 1980 experiment",
            category="backstory",
            moment_id="scene1_start"
        )
        engine.log_knowledge("webb", fact_id, "scene1_start", take, source="research")

        # Both characters are in the scene (shared experience)
        engine.dialogue(
            speaker="webb",
            content="I've been researching what happened at PSU in 1980.",
            moment_id="scene1_start",
            take_id=take,
            listeners=["alex"],
            speaker_tags={"emotion": "probing"},
            listener_tags={"emotion": "guarded"}
        )

        # Query states
        alex_state = engine.query_state("alex", "scene1_start", take)
        webb_state = engine.query_state("webb", "scene1_start", take)

        # Alex doesn't know the fact
        assert len(alex_state.facts) == 0

        # Webb knows the fact
        assert len(webb_state.facts) == 1
        assert webb_state.facts[0].content == "Alex's father was part of the 1980 experiment"

        # But both have the memory of what was said
        assert len(alex_state.memories) == 1
        assert alex_state.memories[0].chunk_type == "heard"
        assert "PSU in 1980" in alex_state.memories[0].chunk

        assert len(webb_state.memories) == 1
        assert webb_state.memories[0].chunk_type == "said"
    finally:
        engine.close()


def test_knowledge_revealed_over_time():
    """
    Character learns a fact later in the narrative.
    State at earlier moment should not include the fact.
    """
    engine = NarrativeStateEngine(EngineConfig(db_path=":memory:", embedding_backend="hash"))

    try:
        engine.register_character("detective", "Detective", {}, {})
        engine.register_character("suspect", "Suspect", {}, {})

        take = engine.create_take()

        # Timeline
        engine.create_moment("m1", 1, "Initial interview")
        engine.create_moment("m2", 2, "Evidence discovered")
        engine.create_moment("m3", 3, "Confrontation")

        # The fact exists from the start (world truth)
        fact = engine.log_fact(
            "The murder weapon was a candlestick",
            "evidence",
            "m1"  # established early
        )

        # Suspect always knew
        engine.log_knowledge("suspect", fact, "m1", take, "witnessed")

        # Detective discovers at m2
        engine.log_knowledge("detective", fact, "m2", take, "discovered")

        # At m1: detective doesn't know, suspect knows
        det_m1 = engine.query_state("detective", "m1", take)
        sus_m1 = engine.query_state("suspect", "m1", take)

        assert len(det_m1.facts) == 0
        assert len(sus_m1.facts) == 1

        # At m3: both know
        det_m3 = engine.query_state("detective", "m3", take)
        sus_m3 = engine.query_state("suspect", "m3", take)

        assert len(det_m3.facts) == 1
        assert len(sus_m3.facts) == 1
    finally:
        engine.close()


def test_branch_alternate_revelations():
    """
    Different branches can have different knowledge revelations.
    """
    engine = NarrativeStateEngine(EngineConfig(db_path=":memory:", embedding_backend="hash"))

    try:
        engine.register_character("hero", "Hero", {}, {})

        engine.create_moment("m1", 1, "Start")
        engine.create_moment("m2", 2, "Fork point")
        engine.create_moment("m3", 3, "After fork")

        root_take = engine.create_take(notes="root")

        # Two possible secrets
        secret_a = engine.log_fact("The butler did it", "secret", "m1")
        secret_b = engine.log_fact("The gardener did it", "secret", "m1")

        # Branch A: hero learns secret A
        branch_a = engine.branch(root_take, "m2", notes="butler path")
        engine.log_knowledge("hero", secret_a, "m2", branch_a, "discovered")

        # Branch B: hero learns secret B
        branch_b = engine.branch(root_take, "m2", notes="gardener path")
        engine.log_knowledge("hero", secret_b, "m2", branch_b, "discovered")

        # Query at m3 in each branch
        state_a = engine.query_state("hero", "m3", branch_a)
        state_b = engine.query_state("hero", "m3", branch_b)

        # Branch A: knows about butler
        assert len(state_a.facts) == 1
        assert "butler" in state_a.facts[0].content

        # Branch B: knows about gardener
        assert len(state_b.facts) == 1
        assert "gardener" in state_b.facts[0].content
    finally:
        engine.close()
