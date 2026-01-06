# MCP Implementation Summary

This document summarizes the Model Context Protocol (MCP) server implementation for Phantom State.

## What Was Added

### Core MCP Server
- **File**: [src/phantom_state/mcp.py](src/phantom_state/mcp.py)
- Single server instance with 12 tools exposing the engine's full API
- Environment-based configuration (no code changes needed for different deployments)
- Stateless design with global engine instance shared across connections

### Tools Exposed

1. **Moment Management**
   - `create_moment` - Create temporal markers

2. **Take (Branch) Management**
   - `create_take` - Create narrative branches
   - `list_takes` - List all takes with filters
   - `set_take_status` - Update take status (active/archived/trunk)
   - `get_ancestry` - Get take lineage

3. **Character Management**
   - `register_character` - Register character and create memory store
   - `get_character` - Get character data

4. **Fact & Knowledge**
   - `log_fact` - Record world-level facts
   - `log_knowledge` - Record character learning events

5. **Memory & Dialogue**
   - `embed_memory` - Store experiential memories
   - `dialogue` - Convenience method for dialogue exchanges

6. **State Queries**
   - `query_state` - Get character's bounded knowledge state

### Configuration

**Environment Variables** (see [.env.example](.env.example)):
```bash
PHANTOM_DB_PATH=narrative.db
PHANTOM_EMBEDDING_BACKEND=local
PHANTOM_EMBEDDING_MODEL=all-MiniLM-L6-v2
PHANTOM_OPENAI_MODEL=text-embedding-3-small
PHANTOM_VECTOR_DIMENSIONS=384
```

**MCP Client Config** (see [mcp_config.example.json](mcp_config.example.json)):
```json
{
  "mcpServers": {
    "phantom_state": {
      "command": "python",
      "args": ["-m", "phantom_state.mcp"],
      "env": { ... }
    }
  }
}
```

### Documentation

- [MCP_USAGE.md](MCP_USAGE.md) - Comprehensive usage guide with examples
- [examples/mcp_client_example.py](examples/mcp_client_example.py) - Full working example
- Updated [README.md](README.md) and [CLAUDE.md](CLAUDE.md)

### Package Updates

**pyproject.toml changes**:
- Added `mcp>=0.9.0` to dependencies
- Added CLI entry point: `phantom-state-mcp`
- Added package data config for schema.sql

## Design Decisions

### Single Engine Instance
The MCP server maintains one shared `NarrativeStateEngine` instance initialized on first tool call. This:
- Avoids database connection overhead
- Maintains consistent state across calls
- Simplifies configuration

### Environment-Based Config
Configuration via environment variables instead of init tool:
- Stateless server design
- Simpler client setup
- Standard practice for MCP servers

### Trust-Based Character Scoping
Character agents are trusted to query only their own state:
- Enforced through system prompts, not code
- Keeps API surface simple
- Matches MCP security model

### Tool vs. Resource Model
Exposed engine operations as **tools** rather than resources:
- Tools are for actions (create, update, query)
- Resources are for static data retrieval
- Better fit for narrative engine's operation-heavy API

## Architecture

```
┌─────────────────────────────────────────┐
│  Client (Codex CLI / Claude Desktop / Custom Agent) │
└────────────────┬────────────────────────┘
                 │ MCP protocol (stdio)
┌────────────────▼────────────────────────┐
│  phantom_state MCP Server               │
│  - 12 tools                             │
│  - Environment config                   │
│  - Single engine instance               │
└────────────────┬────────────────────────┘
                 │ Direct API calls
┌────────────────▼────────────────────────┐
│  NarrativeStateEngine                   │
│  - SQLite + sqlite-vec                  │
│  - Per-character memory stores          │
└─────────────────────────────────────────┘
```

## Usage Patterns

### 1. DM Orchestrator
Human or agent coordinates the narrative:
- Creates moments and characters
- Records facts and knowledge events
- Queries character states before generating responses
- Manages take branches for exploration

### 2. Character Agents
Individual character agents constrained by system prompt:
- Each queries only their own character state
- Trust-based scoping (no enforcement at API level)
- System prompt includes character_id constraint

### 3. Multi-Take Development
Explore alternate narrative paths:
- Branch from any moment
- Query character states in different takes
- Compare outcomes across branches
- Archive unsuccessful takes

## Testing

Verified with [test_mcp_server.py](test_mcp_server.py):
```bash
$ .venv/Scripts/python.exe test_mcp_server.py
[OK] MCP server module imported successfully
[OK] Found 12 tools
[OK] Engine initialized with config
[OK] All tests passed!
```

## Future Enhancements

Potential additions (not implemented):

1. **Resources API**
   - Read-only access to moments, takes, characters
   - More efficient for reference data

2. **Batch Operations**
   - Multi-fact logging
   - Bulk memory embedding
   - Transaction-based updates

3. **State Snapshots**
   - Export character state at moment
   - Import pre-defined states
   - State comparison tools

4. **Validation Layer**
   - Character scope enforcement (if trust model insufficient)
   - Fact consistency checking
   - Moment sequence validation

5. **Performance Tools**
   - Query profiling
   - Embedding cache stats
   - Database size monitoring

## Integration Examples

### With Codex CLI / Claude Desktop

Add to your MCP client config, then:

```
User: "Create a detective mystery with two characters who know different clues."

Claude:
1. Creates moments (m1, m2, m3)
2. Registers characters (detective, suspect)
3. Logs facts (murder weapon location, alibi details)
4. Records asymmetric knowledge (suspect knows weapon location, detective doesn't)
5. Queries character states before generating dialogue
6. Records dialogue with proper listener/speaker tracking
```

### With Custom Workflow

```python
# Orchestrator coordinates narrative beats
for beat in story_beats:
    # Query each character's state
    for char in beat.characters:
        state = await mcp.query_state(char, beat.moment, beat.take)

        # Generate action based on bounded knowledge
        action = generate_with_llm(state)

        # Record to narrative
        await mcp.embed_memory(char, action, beat.moment, beat.take, "action")
```

## uv Support

Phantom State now fully supports [uv](https://github.com/astral-sh/uv), the extremely fast Python package installer.

### Benefits
- **10-100x faster** installation than pip
- Works with MCP `uv run --with phantom_state` for zero-config deployment
- Automatic environment management
- See [UV_SETUP.md](UV_SETUP.md) for complete guide

### Quick Start with uv

```bash
# Install
uv pip install -e ".[dev]"

# Run MCP server
uv run python -m phantom_state.mcp

# Run tests
uv run pytest
```

### MCP Configuration with uv

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

This configuration automatically manages dependencies - no manual installation needed!

## Conclusion

The MCP server provides a clean, standardized interface to Phantom State's narrative engine. It exposes all core functionality through 12 tools while maintaining the engine's architectural guarantees around bounded knowledge and temporal isolation.

No changes were made to the core engine — the MCP layer is purely additive, allowing the same codebase to be used via direct Python API or MCP protocol.

With `uv` support, installation and deployment are faster than ever, making it easy to integrate Phantom State into any workflow.
