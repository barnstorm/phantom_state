# Phantom State + phantom_scribe Integration

## TL;DR

```bash
# From phantom_state directory
python scripts/enhance_phantom_scribe.py --project /path/to/your/story
```

This adds **character knowledge boundaries** to your phantom_scribe projects.

## What You Get

### 1. Automatic MCP Setup
- Phantom State MCP server configured in `.claude/mcp_config.json`
- Ready to use with Claude Code (Codex CLI users can reuse the same MCP server settings in their Codex MCP config)
- Uses `uv` for zero-config dependency management

### 2. New Agents

**state-manager** - Set up and maintain narrative state
- Create moments (temporal markers)
- Register characters with traits/voice
- Log facts and knowledge events
- Track who knows what, when, and how

**knowledge-query** - Fast character knowledge lookups
- "What does Alice know at ch3_midpoint?"
- Returns facts + memories in seconds
- Use before writing any character POV

### 3. State Tracking Templates

**templates/state/KNOWLEDGE_TRACKING.md**
- Track characters, moments, facts, knowledge events
- Registry of who knows what
- Take (branch) tracking

**templates/state/STATE_MANAGEMENT_GUIDE.md**
- Complete workflow guide
- Examples for mystery, thriller, multi-POV
- Best practices and troubleshooting

## Why This Matters

### The Problem

```
You: "Write Alice's POV. She doesn't know Bob is the killer yet."

Claude: "Alice suspected Bob all along. His nervous behavior..."
```

**The prompt didn't work** - Claude "leaked" information.

### The Solution

```
1. Query Alice's state at this moment
2. Phantom State returns ONLY what she actually knows
3. Claude literally cannot access anything else
4. No information leakage possible
```

## Quick Start

### 1. Enhance Your Project

```bash
cd phantom_state
python scripts/enhance_phantom_scribe.py --project ~/stories/my_mystery
```

### 2. Restart Your MCP Client

Pick up new agents and MCP configuration (Claude Code) or reload your Codex CLI session after adding MCP config.

### 3. Set Up State (state-manager)

```
You: "Set up narrative state for my mystery novel with 3 POV characters"

state-manager:
- Creates moments for each chapter
- Registers Detective, Suspect, Witness
- Creates trunk take (canonical timeline)
```

### 4. Write with Bounded Knowledge

**Before writing Detective's POV:**
```
You: "What does Detective know at ch5_investigation?"

knowledge-query returns:
- Facts: 3 clues discovered
- Memories: Recent dialogue, perceptions
- Does NOT include: What suspect knows, future revelations
```

**Write the scene** using only that knowledge.

**After writing:**
```
You: "Log new knowledge from this scene:
- Detective discovered fingerprints (source: discovered)
- Detective heard suspect's alibi (source: told)"

state-manager logs the updates
```

## Workflow Integration

Works seamlessly with existing phantom_scribe agents:

```
story-orchestrator → Creates beat sheet
        ↓
state-manager → Sets up moments/characters
        ↓
Chapter Writing Loop:
    knowledge-query → "What does X know?"
    [Write scene]
    state-manager → Log new facts/knowledge
        ↓
canon-keeper + state-manager → Track canon facts
```

## Example: Mystery Novel

```
# Detective doesn't know murder weapon location (ch1-4)
detective_state = query_state("detective", "ch4_investigation", 1)
# detective_state.facts = [other clues, not weapon location]

# Suspect knows (was there when it happened)
suspect_state = query_state("suspect", "ch1_opening", 1)
# suspect_state.facts includes weapon location

# Detective discovers it (ch5)
log_knowledge("detective", weapon_fact_id, "ch5_discovery", 1, "discovered")

# Now detective knows
detective_state = query_state("detective", "ch6_analysis", 1)
# detective_state.facts includes weapon location (just learned!)
```

## Features

### Asymmetric Knowledge
Each character has their own private knowledge store.

### Temporal Gating
Knowledge at moment M+1 doesn't leak to queries at moment M.

### Source Tracking
- `witnessed` - Saw it happen
- `told` - Another character revealed it
- `inferred` - Deduced from available info
- `discovered` - Found through investigation

### Branching Exploration
```
# Try alternate timeline
alt_take = create_take(parent=1, branch_point="ch3_midpoint",
                       notes="What if Detective knew earlier?")

# Modify knowledge in new take
log_knowledge("detective", secret_fact, "ch2_investigation", alt_take, "discovered")

# Compare both timelines
trunk_state = query_state("detective", "ch5", take=1)
alt_state = query_state("detective", "ch5", take=alt_take)

# Choose which timeline to continue
```

### Vector Memory Search
```
query_state("alice", "ch10_climax", 1,
            query_text="safe combination")
```
Returns memories semantically similar to "safe combination" - relevant dialogue, perceptions, thoughts.

## Use Cases

### Mystery/Thriller
- Track clue distribution
- Fair play detection (does detective have needed clues?)
- Control information reveals
- Red herrings per character

### Multi-POV
- Each POV has different knowledge
- No accidental information leakage
- Build dramatic irony (reader knows, character doesn't)

### Unreliable Narrator
- Track "false facts" narrator believes
- Query to check what narrator thinks vs reality
- Reveal truth gradually

### Complex Worldbuilding
- Characters learn world rules progressively
- Track who knows which secrets
- Manage knowledge economy

## Advanced

### Direct MCP Tool Access

All phantom_state MCP tools available:
- `create_moment`, `create_take`, `list_takes`
- `register_character`, `get_character`
- `log_fact`, `log_knowledge`
- `dialogue`, `embed_memory`
- `query_state`, `get_ancestry`

See [MCP_USAGE.md](MCP_USAGE.md) for complete reference.

### Custom Workflows

```python
# Python API also available
from phantom_state import NarrativeStateEngine, EngineConfig

engine = NarrativeStateEngine(EngineConfig(db_path="story.db"))
state = engine.query_state("detective", "ch5", 1)
```

## Documentation

- [PHANTOM_SCRIBE_INTEGRATION.md](PHANTOM_SCRIBE_INTEGRATION.md) - Complete guide
- [MCP_USAGE.md](MCP_USAGE.md) - MCP tool reference
- [UV_SETUP.md](UV_SETUP.md) - Fast installation guide

## Support

- Phantom State: [Issues](https://github.com/yourusername/phantom_state/issues)
- phantom_scribe: [Issues](https://github.com/barnstorm/phantom_scribe/issues)
