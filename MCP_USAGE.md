# Phantom State MCP Usage Guide

This guide explains how to use Phantom State through its Model Context Protocol (MCP) interface.

## Overview

The MCP server exposes Phantom State's narrative engine through standardized tools that can be called by:
- Claude Desktop or other MCP clients
- Custom orchestrator agents
- Interactive DM workflows
- Automated narrative systems

## Installation

### Using uv (Recommended - Fast!)

```bash
# Install with MCP support (MCP is included in base dependencies)
uv pip install -e .

# Or install all optional dependencies
uv pip install -e ".[all]"
```

> **New to uv?** See [UV_SETUP.md](UV_SETUP.md) for complete uv setup guide including MCP server configuration.

### Using pip

```bash
# Install with MCP support (MCP is included in base dependencies)
pip install -e .

# Or install all optional dependencies
pip install -e ".[all]"
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
PHANTOM_DB_PATH=narrative.db
PHANTOM_EMBEDDING_BACKEND=local  # or "openai"
PHANTOM_EMBEDDING_MODEL=all-MiniLM-L6-v2
PHANTOM_OPENAI_MODEL=text-embedding-3-small
PHANTOM_VECTOR_DIMENSIONS=384
```

### MCP Client Configuration

For Claude Desktop or similar MCP clients, add to your MCP settings:

**Using standard Python** (see [mcp_config.example.json](mcp_config.example.json)):
```json
{
  "mcpServers": {
    "phantom_state": {
      "command": "python",
      "args": ["-m", "phantom_state.mcp"],
      "env": {
        "PHANTOM_DB_PATH": "narrative.db",
        "PHANTOM_EMBEDDING_BACKEND": "local"
      }
    }
  }
}
```

**Using uv (faster)** (see [mcp_config.uv.example.json](mcp_config.uv.example.json)):
```json
{
  "mcpServers": {
    "phantom_state": {
      "command": "uv",
      "args": ["run", "--with", "phantom_state", "python", "-m", "phantom_state.mcp"],
      "env": {
        "PHANTOM_DB_PATH": "narrative.db",
        "PHANTOM_EMBEDDING_BACKEND": "local"
      }
    }
  }
}
```

## Running the Server

### Standalone Mode

```bash
python -m phantom_state.mcp
```

### As an MCP Server

The server will be automatically launched by your MCP client when configured.

## Available Tools

### Moment Management

#### `create_moment`
Create a temporal marker for ordering events.

```json
{
  "id": "m1",
  "sequence": 1,
  "label": "Opening scene",
  "metadata": {"act": 1, "scene": 1}
}
```

### Take (Branch) Management

#### `create_take`
Create a new narrative branch.

```json
{
  "parent_take_id": 1,
  "branch_point": "m5",
  "notes": "What if Alice told the truth?"
}
```

#### `list_takes`
List all takes, optionally filtered.

```json
{
  "status": "active"
}
```

#### `set_take_status`
Update take status (active/archived/trunk).

```json
{
  "take_id": 2,
  "status": "archived"
}
```

#### `get_ancestry`
Get full lineage of take IDs.

```json
{
  "take_id": 3
}
```

### Character Management

#### `register_character`
Register a character and create their memory store.

```json
{
  "id": "alice",
  "name": "Alice",
  "traits": {
    "curious": true,
    "analytical": true
  },
  "voice": {
    "style": "precise",
    "favors_questions": true
  }
}
```

#### `get_character`
Get character data.

```json
{
  "character_id": "alice"
}
```

### Fact Management

#### `log_fact`
Record a world-level fact.

```json
{
  "content": "The safe combination is 7-3-9",
  "category": "secret",
  "moment_id": "m1"
}
```

#### `log_knowledge`
Record that a character learned a fact.

```json
{
  "character_id": "bob",
  "fact_id": 42,
  "moment_id": "m1",
  "take_id": 1,
  "source": "discovered"
}
```

Sources: `witnessed`, `told`, `inferred`, `discovered`

### Memory Management

#### `embed_memory`
Store experiential memory for a character.

```json
{
  "character_id": "alice",
  "chunk": "She noticed Bob's nervous glance at the safe.",
  "moment_id": "m1",
  "take_id": 1,
  "chunk_type": "perceived",
  "tags": {"suspicious": true}
}
```

Chunk types: `said`, `heard`, `internal`, `perceived`, `action`

#### `dialogue`
Convenience method for dialogue exchange.

```json
{
  "speaker": "alice",
  "content": "Hey Bob, do you know anything about that safe?",
  "moment_id": "m1",
  "take_id": 1,
  "listeners": ["bob"],
  "speaker_tags": {"tone": "casual"},
  "listener_tags": {"reaction": "defensive"}
}
```

This automatically embeds to speaker as `said` and listeners as `heard`.

### State Queries

#### `query_state`
Get everything a character knows/has experienced.

```json
{
  "character_id": "alice",
  "moment_id": "m5",
  "take_id": 1,
  "query_text": "safe combination",
  "fact_limit": 50,
  "memory_limit": 20
}
```

If `query_text` is provided, memories are ordered by semantic similarity. Otherwise, chronological.

**Returns:**
```json
{
  "character_id": "alice",
  "moment_id": "m5",
  "take_id": 1,
  "traits": {...},
  "voice": {...},
  "facts": [
    {
      "id": 42,
      "content": "...",
      "category": "secret",
      "source": "told",
      "moment_id": "m3"
    }
  ],
  "memories": [
    {
      "id": 123,
      "chunk": "...",
      "chunk_type": "heard",
      "tags": {},
      "moment_id": "m2"
    }
  ]
}
```

## Workflow Patterns

### DM Orchestration

The DM (human or agent) coordinates the story:

1. **Initialize narrative**: Create moments, root take, register characters
2. **Execute beats**: For each story beat:
   - Log facts as they're established
   - Record who learns what via `log_knowledge`
   - Record dialogue/actions via `dialogue` or `embed_memory`
3. **Query character state**: Before having a character act/speak, query their state
4. **Branch exploration**: Create takes to explore "what if" scenarios
5. **Canonize**: Set final take to `trunk` status

### Character Agent Pattern

Individual character agents can be scoped to their character:

```python
# Character agent system prompt includes:
"""
You are Alice. Query your state with character_id='alice'.
You may ONLY read your own state - never query other characters.
"""
```

Trust-based scoping — the system prompt constrains tool usage.

### Multi-Take Development

Explore different narrative branches:

```bash
# Create alternative where Alice knows the secret
take_id = create_take(parent=1, branch_point="m1", notes="Alice discovers safe")
log_knowledge(character="alice", fact_id=42, moment="m1", take=take_id, source="discovered")

# Compare Alice's state in different takes
alice_trunk = query_state(character="alice", moment="m5", take=1)
alice_alt = query_state(character="alice", moment="m5", take=take_id)
```

## Integration Examples

### With Claude Code

When Claude Code has Phantom State MCP configured:

```
User: "I want to explore a scenario where Bob tells Alice the combination."

Claude:
1. Creates a new take branching from the current moment
2. Uses `dialogue` to record Bob's confession
3. Uses `log_knowledge` to mark Alice learning the fact
4. Queries Alice's new state
5. Generates Alice's response based on her updated knowledge
```

### With Custom Orchestrator

```python
async def run_beat(beat: Beat, take_id: int):
    """Execute a story beat."""
    # Query what each character knows
    states = {
        char_id: await query_state(char_id, beat.moment, take_id)
        for char_id in beat.characters
    }

    # Generate character actions based on bounded knowledge
    for char_id in beat.characters:
        action = await generate_action(char_id, states[char_id])
        await embed_memory(char_id, action, beat.moment, take_id, "action")
```

## Best Practices

1. **Moment Granularity**: Create moments at beat boundaries, not every action
2. **Fact vs Memory**: Facts are discrete knowledge; memories are experiential
3. **Source Tracking**: Always specify how knowledge was acquired
4. **Take Management**: Archive unsuccessful branches to keep active list clean
5. **Query Optimization**: Use `query_text` for similarity when context matters
6. **Limits**: Adjust `fact_limit` and `memory_limit` based on context window

## Troubleshooting

### Server won't start
- Check Python version (>=3.10 required)
- Verify MCP package is installed: `pip list | grep mcp`
- Check environment variables are set

### Database errors
- Ensure `PHANTOM_DB_PATH` directory exists and is writable
- Check sqlite-vec extension loaded properly
- Verify database not locked by another process

### Embedding errors
- Local backend: Ensure sentence-transformers installed
- OpenAI backend: Verify `OPENAI_API_KEY` set
- Check vector dimensions match your embedding model

### Character not found
- Verify character registered with `register_character` first
- Check character_id spelling matches exactly

## Performance Notes

- **Embedding latency**: Local ~100-300ms, OpenAI ~200-500ms
- **Query performance**: Scales well to 100K+ memories per character
- **Take branches**: No performance impact until thousands of branches
- **Database size**: ~1KB per memory chunk + embeddings (384-1536 bytes)

## Security Considerations

- **Trust-based scoping**: Character agents trusted to query only their own state
- **No authentication**: Assumes trusted environment (local/internal network)
- **Database access**: Direct SQLite access — protect database file
- **API keys**: Store OpenAI keys in environment, not config files
