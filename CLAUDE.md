# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Phantom State is a narrative state engine for multi-agent dialogue generation. It solves the problem of LLMs failing to simulate characters who "don't know" something by enforcing structural absence rather than prompt-based suppression.

**Core principle**: If information isn't in a character's retrieval context, it can't contaminate their responses.

## Architecture

### Core Concepts
- **Character**: Persistent agent with private memory store. No character can query another's store.
- **Moment**: Abstract temporal marker for ordering and gating knowledge.
- **Take**: A branch of state for "what if" exploration. Full history preserved across branches.
- **Fact**: World-level truth that exists independent of who knows it.
- **Knowledge Event**: Records when a character learns a fact (with source: witnessed/told/inferred/discovered).
- **Memory**: Two types - structured facts and experiential (embedded chunks of dialogue/perception/internal state).

### Database Design
- SQLite with sqlite-vec extension for vector similarity
- Per-character memory tables created dynamically on registration: `{character_id}_memory`
- Take ancestry via recursive CTE for branch history
- Temporal gating via moment sequence numbers

### Key Query Pattern
All queries filter by `take_id IN (ancestry)` to include memories from current branch plus all ancestors, and by `moment.sequence <= current_moment.sequence` for temporal gating.

## Build and Test Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run all tests
pytest

# Run single test file
pytest tests/test_two_agents.py -v

# Run specific test
pytest tests/test_two_agents.py::test_bounded_knowledge -v
```

## File Structure

```
phantom_state/
├── pyproject.toml
├── src/phantom_state/
│   ├── __init__.py
│   ├── engine.py          # NarrativeStateEngine class
│   ├── schema.sql         # table definitions
│   ├── queries.py         # SQL builders
│   ├── embedding.py       # backend abstraction
│   └── models.py          # dataclasses (includes EngineConfig)
├── tests/
│   ├── conftest.py        # pytest fixtures
│   ├── test_schema.py
│   ├── test_branching.py
│   ├── test_queries.py
│   ├── test_embedding.py
│   └── test_two_agents.py # core validation test
└── examples/
    └── basic_dialogue.py
```

## Dependencies

- Python 3.10+
- sqlite-vec >= 0.1.0
- sentence-transformers >= 2.2.0 (local embeddings, default)
- openai >= 1.0.0 (optional, API embeddings)

## Design Constraints

- Engine maintains state only - no story structure, plot management, or LLM calls
- Memory tables created eagerly on character registration
- Take garbage collection is manual only
- Embedding latency target: <500ms from text to stored
- Local embedding default (all-MiniLM-L6-v2, 384 dimensions), OpenAI optional

## Chunk Types

Memory chunks use these types: `said`, `heard`, `internal`, `perceived`, `action`

## Knowledge Sources

When logging knowledge: `witnessed`, `told`, `inferred`, `discovered`
