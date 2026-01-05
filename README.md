# Phantom State

**Narrative state engine for multi-agent dialogue generation with bounded character knowledge.**

Phantom State solves the problem of LLMs failing to simulate characters who "don't know" something by enforcing **structural absence** rather than prompt-based suppression. If information isn't in a character's retrieval context, it can't contaminate their responses.

## Core Principle

> If a fact isn't in a character's memory store, the LLM literally cannot access it.

No more relying on prompts to make models "forget" things. Knowledge boundaries are enforced at the data layer.

## Key Features

- **Per-character memory isolation** - No character can query another's private memories
- **Temporal gating** - Knowledge learned at moment M doesn't leak to queries at earlier moments
- **Branch preservation** - Explore "what if" scenarios without losing narrative history
- **Dual memory system** - Structured facts + experiential memories with vector similarity
- **Source tracking** - Record how characters learned information (witnessed/told/inferred/discovered)

## Installation

```bash
# Clone or download
git clone <repository-url>
cd phantom_state

# Install with dev dependencies
pip install -e ".[dev]"

# Or just the package
pip install -e .
```

**Requirements:**
- Python 3.10+
- sqlite-vec >= 0.1.0
- sentence-transformers >= 2.2.0 (local embeddings, default)
- openai >= 1.0.0 (optional, for API embeddings)

## Quick Start

```python
from phantom_state import NarrativeStateEngine, EngineConfig

# Initialize engine
config = EngineConfig(db_path="story.db")
engine = NarrativeStateEngine(config)

# Register characters
engine.register_character(
    "detective",
    "Detective Sarah Chen",
    traits={"personality": "analytical", "experience": "15 years"},
    voice={"tone": "matter-of-fact", "quirks": ["uses precise terminology"]}
)

engine.register_character("suspect", "John Doe", {}, {})

# Create narrative structure
take = engine.create_take(notes="initial investigation")
m1 = engine.create_moment("interview_start", sequence=1)
m2 = engine.create_moment("evidence_revealed", sequence=2)

# Establish a fact only the suspect knows
fact = engine.log_fact(
    "The murder weapon was hidden in the garden shed",
    category="evidence",
    moment_id="interview_start"
)
engine.log_knowledge("suspect", fact, "interview_start", take, source="witnessed")

# Detective doesn't know yet
detective_state = engine.query_state("detective", "interview_start", take)
print(detective_state.facts)  # → []

suspect_state = engine.query_state("suspect", "interview_start", take)
print(suspect_state.facts)  # → [Fact(content="The murder weapon...")]

# Detective learns at moment 2
engine.log_knowledge("detective", fact, "evidence_revealed", take, source="discovered")

# Now detective knows
detective_state = engine.query_state("detective", "evidence_revealed", take)
print(detective_state.facts)  # → [Fact(content="The murder weapon...")]

engine.close()
```

## Architecture

### Core Concepts

- **Character**: Persistent agent with private memory store
- **Moment**: Abstract temporal marker for ordering and gating knowledge
- **Take**: A branch of state for "what if" exploration with full history preservation
- **Fact**: World-level truth that exists independent of who knows it
- **Knowledge Event**: Records when a character learns a fact (with source attribution)
- **Memory**: Experiential chunks (dialogue, perception, thoughts) with vector embeddings

### Database Design

- SQLite with sqlite-vec extension for vector similarity search
- Per-character memory tables created dynamically: `{character_id}_memory`
- Take ancestry via recursive CTEs for branch history
- Temporal gating via moment sequence numbers

### Key Query Pattern

All queries filter by:
- `take_id IN (ancestry)` - Include current branch plus all ancestors
- `moment.sequence <= current_moment.sequence` - Temporal gating

## Memory Types

Memories are categorized by type:
- `said` - Character spoke this
- `heard` - Character heard this
- `internal` - Internal thoughts/observations
- `perceived` - Sensory observations
- `action` - Physical actions

## Knowledge Sources

When logging knowledge, specify how it was acquired:
- `witnessed` - Directly observed
- `told` - Learned from another character
- `inferred` - Deduced from available information
- `discovered` - Found through investigation

## Branching & Takes

```python
# Create initial take
take1 = engine.create_take(notes="confrontational approach")

# Record some dialogue...
engine.dialogue("detective", "I know you did it!", "scene1", take1, ["suspect"])

# Don't like the direction? Branch it
take2 = engine.branch(take1, "scene1", notes="friendly approach")

# Try alternate dialogue in the new branch
engine.dialogue("detective", "Help me understand what happened.", "scene1", take2, ["suspect"])

# Original take is preserved, branch explores alternate path
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_two_agents.py -v

# Run with coverage
pytest --cov=phantom_state --cov-report=term-missing
```

**Core validation test:** `tests/test_two_agents.py::test_bounded_knowledge` - If this passes, the fundamental architecture is working correctly.

## Examples

See `examples/basic_dialogue.py` for a complete walkthrough:

```bash
python examples/basic_dialogue.py
```

This demonstrates:
- Character registration with traits and voice
- Asymmetric knowledge (one character knows, another doesn't)
- Dialogue recording with emotional tags
- Branching to explore alternate takes
- State comparison across branches

## Design Philosophy

**What Phantom State does:**
- Maintains narrative state with bounded character knowledge
- Provides retrieval primitives for LLM context construction
- Enforces temporal and branch isolation

**What it doesn't do:**
- Story structure or plot management (build that on top)
- LLM calls (you handle generation)
- Decision-making about what characters should know (you control knowledge events)

Phantom State is a **data layer**, not a story engine. It gives you the primitives to build knowledge-bounded multi-agent narratives.

## Configuration

```python
from phantom_state import EngineConfig

# Local embeddings (default)
config = EngineConfig(
    db_path="story.db",
    embedding_backend="local",
    embedding_dimensions=384  # all-MiniLM-L6-v2 default
)

# OpenAI embeddings
config = EngineConfig(
    db_path="story.db",
    embedding_backend="openai",
    openai_model="text-embedding-3-small",
    embedding_dimensions=1536
)
```

## Performance

- **Embedding latency target:** <500ms from text to stored
- **Local embedding default:** all-MiniLM-L6-v2 (384 dimensions)
- **Vector search:** Optimized via sqlite-vec's KNN implementation

## License

MIT

## Contributing

This project follows test-driven development. All core functionality should have corresponding tests in the `tests/` directory.

When adding features:
1. Write tests first
2. Ensure `tests/test_two_agents.py` still passes
3. Update CLAUDE.md with any architectural changes
4. Run the full test suite before submitting

## Documentation

- [CLAUDE.md](CLAUDE.md) - Detailed architecture and development guide
- [phantom_state_spec.md](phantom_state_spec.md) - Original specification

