"""Basic dialogue example from the Phantom State specification.

This example demonstrates:
- Character registration with traits and voice
- Fact and knowledge management
- Dialogue with speaker/listener memory
- Branching for alternate takes
- Querying character state

Note: This example uses pseudo-code for LLM generation.
Replace the generate_response function with your actual LLM calls.
"""

from phantom_state import NarrativeStateEngine, EngineConfig, CharacterState


def generate_response(state: CharacterState, context: str) -> str:
    """Placeholder for actual LLM generation.

    In production, you would:
    1. Format state.facts, state.memories, state.traits, state.voice
    2. Combine with scene context
    3. Call your LLM API
    4. Return the generated response
    """
    # This is just a placeholder
    if state.facts:
        return f"I know something about {state.facts[0].category}..."
    return "I don't know anything about that."


def main():
    # Initialize engine
    config = EngineConfig(db_path="story.db")
    engine = NarrativeStateEngine(config)

    try:
        # Setup characters
        engine.register_character(
            "alex",
            "Alex",
            traits={"disposition": "guarded", "coping": "control"},
            voice={"patterns": ["clinical self-talk", "short sentences under stress"]}
        )
        engine.register_character(
            "webb",
            "Dr. Webb",
            traits={"disposition": "curious", "role": "investigator"},
            voice={"patterns": ["professorial", "asks probing questions"]}
        )

        # Create initial take and moment
        take = engine.create_take(notes="initial run")
        m1 = engine.create_moment("scene1_start", sequence=1, label="First meeting")

        # Establish a fact only Webb knows
        fact_id = engine.log_fact(
            "Alex's father was part of the 1980 experiment",
            category="backstory",
            moment_id="scene1_start"
        )
        engine.log_knowledge("webb", fact_id, "scene1_start", take, source="research")

        # Scene loop - get character states
        alex_state = engine.query_state("alex", "scene1_start", take)
        print(f"Alex's facts: {[f.content for f in alex_state.facts]}")
        # → Alex's facts: []  (Alex doesn't know about the experiment)

        webb_state = engine.query_state("webb", "scene1_start", take)
        print(f"Webb's facts: {[f.content for f in webb_state.facts]}")
        # → Webb's facts: ["Alex's father was part of the 1980 experiment"]

        # Generate dialogue (pseudo-code for LLM calls)
        webb_line = "I've been researching what happened at PSU in 1980."
        print(f"\nWebb: {webb_line}")

        # Record the exchange
        engine.dialogue(
            speaker="webb",
            content=webb_line,
            moment_id="scene1_start",
            take_id=take,
            listeners=["alex"],
            speaker_tags={"emotion": "probing"},
            listener_tags={"emotion": "guarded"}
        )

        alex_line = "I don't know what you're talking about."
        print(f"Alex: {alex_line}")

        engine.dialogue(
            speaker="alex",
            content=alex_line,
            moment_id="scene1_start",
            take_id=take,
            listeners=["webb"],
            speaker_tags={"emotion": "defensive"}
        )

        # Don't like how it went? Branch and retry
        take2 = engine.branch(take, "scene1_start", notes="Webb more direct")
        print(f"\n--- Branched to take {take2} ---")

        # In take2, we can try a different approach
        # The original take's memories remain untouched
        webb_line2 = "Your father. He was there, wasn't he?"
        print(f"\nWebb: {webb_line2}")

        engine.dialogue(
            speaker="webb",
            content=webb_line2,
            moment_id="scene1_start",
            take_id=take2,
            listeners=["alex"],
            speaker_tags={"emotion": "direct"},
            listener_tags={"emotion": "startled"}
        )

        # Show the difference between takes
        print("\n--- Comparing takes ---")

        alex_take1 = engine.query_state("alex", "scene1_start", take)
        alex_take2 = engine.query_state("alex", "scene1_start", take2)

        print(f"Take 1 - Alex heard: {[m.chunk for m in alex_take1.memories]}")
        print(f"Take 2 - Alex heard: {[m.chunk for m in alex_take2.memories]}")

    finally:
        engine.close()


if __name__ == "__main__":
    main()
