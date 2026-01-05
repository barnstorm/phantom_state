#!/usr/bin/env python3
"""Enhance phantom_scribe installations with Phantom State narrative engine.

This script detects phantom_scribe installations and adds:
- Phantom State MCP server configuration
- State-aware agents for character knowledge boundaries
- Templates for tracking character knowledge
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def find_phantom_scribe_installations():
    """Find phantom_scribe installations in common locations."""
    locations = []

    # Check current directory
    if (Path.cwd() / ".claude" / "agents" / "story-orchestrator.md").exists():
        locations.append(Path.cwd())

    # Check parent directories (for being inside a phantom_scribe project)
    current = Path.cwd()
    for _ in range(3):  # Search up to 3 levels
        if (current / ".claude" / "agents" / "story-orchestrator.md").exists():
            if current not in locations:
                locations.append(current)
        current = current.parent

    # Check for phantom_scribe in known locations
    home = Path.home()
    codex_skill = home / ".codex" / "skills" / "phantom-scribe"
    if (codex_skill / ".claude" / "agents" / "story-orchestrator.md").exists():
        locations.append(codex_skill)

    return locations


def add_mcp_config(project_dir: Path, db_path: str = "narrative_state.db"):
    """Add Phantom State MCP configuration to project."""
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(exist_ok=True)

    mcp_config_path = claude_dir / "mcp_config.json"

    # Load existing config or create new
    if mcp_config_path.exists():
        with open(mcp_config_path) as f:
            config = json.load(f)
    else:
        config = {"mcpServers": {}}

    # Add phantom_state server if not present
    if "phantom_state" not in config.get("mcpServers", {}):
        config["mcpServers"]["phantom_state"] = {
            "command": "uv",
            "args": ["run", "--with", "phantom_state", "python", "-m", "phantom_state.mcp"],
            "env": {
                "PHANTOM_DB_PATH": str(project_dir / db_path),
                "PHANTOM_EMBEDDING_BACKEND": "local",
                "PHANTOM_EMBEDDING_MODEL": "all-MiniLM-L6-v2",
                "PHANTOM_VECTOR_DIMENSIONS": "384"
            }
        }

        with open(mcp_config_path, "w") as f:
            json.dump(config, f, indent=2)

        print(f"  [+] Added Phantom State MCP config to {mcp_config_path.relative_to(project_dir)}")
        return True
    else:
        print(f"  [-] Phantom State MCP already configured in {mcp_config_path.relative_to(project_dir)}")
        return False


def create_enhanced_agents(project_dir: Path):
    """Create state-aware agent enhancements."""
    agents_dir = project_dir / ".claude" / "agents"
    state_agents_dir = project_dir / ".claude" / "agents" / "state"
    state_agents_dir.mkdir(exist_ok=True)

    # Create state-manager agent
    state_manager = state_agents_dir / "state-manager.md"
    if not state_manager.exists():
        state_manager.write_text("""---
name: state-manager
description: Manages narrative state for character knowledge boundaries. Use when you need to track who knows what, create alternate takes, or query character knowledge at specific moments.
model: sonnet
color: cyan
---

You are the **State Manager** for Phantom Scribe with Phantom State integration.

## Your Role

You manage the narrative state engine to enforce character knowledge boundaries. This ensures characters only know what they've actually learned, preventing information leakage.

## Available MCP Tools

You have access to Phantom State MCP tools (check available tools):

### Setup
- `create_moment` - Create temporal markers (chapter start, scene, revelation)
- `create_take` - Branch the narrative to explore alternatives
- `register_character` - Add character with traits and voice

### Knowledge Management
- `log_fact` - Record world-level truths
- `log_knowledge` - Record when a character learns a fact (witnessed/told/inferred/discovered)

### Memory & Dialogue
- `dialogue` - Record dialogue (auto-embeds to speaker as 'said', listeners as 'heard')
- `embed_memory` - Store experiential memories (perceived, internal, action)

### Queries
- `query_state` - Get what a character knows at a specific moment
- `list_takes` - See all narrative branches
- `get_ancestry` - Trace take lineage

## Workflow

### 1. Setup Phase (Before Writing)
```
1. Create moments for major beats (one per chapter or key scene)
2. Register all POV characters with traits/voice
3. Create root take (take_id=1)
```

### 2. During Writing
```
For each scene:
1. Log facts as they're established
2. Log who learns each fact (and how: witnessed/told/inferred/discovered)
3. Record dialogue with listeners
4. Record internal thoughts, perceptions, actions
```

### 3. Before Generating Character Action/Dialogue
```
ALWAYS query_state for that character at current moment
Use the returned facts and memories to constrain generation
Never let character "know" something not in their state
```

### 4. For Alternate Takes
```
1. Create new take from branch point
2. Modify knowledge events in new take
3. Query character states in both takes to compare
4. Choose which take to continue (or keep both)
```

## Key Principles

**Structural Absence**: If a fact isn't in a character's query_state result, they literally cannot access it. No prompt engineering needed.

**Temporal Gating**: Knowledge logged at moment M+1 doesn't appear in queries at moment M.

**Source Matters**: Track HOW characters learn (witnessed vs told vs inferred).

**Takes for Exploration**: Create branches for "what if X character knew Y?" scenarios.

## Example: Asymmetric Knowledge

```
# Setup
create_moment(id="ch1_opening", sequence=1)
register_character(id="alice", name="Alice")
register_character(id="bob", name="Bob")
create_take()  # returns take_id=1

# Bob discovers secret
fact_id = log_fact(
    content="The safe combination is 7-3-9",
    category="secret",
    moment_id="ch1_opening"
)
log_knowledge(
    character_id="bob",
    fact_id=fact_id,
    moment_id="ch1_opening",
    take_id=1,
    source="discovered"
)

# Before writing Alice's POV
alice_state = query_state("alice", "ch1_opening", 1)
# alice_state.facts = [] (she doesn't know the combination)

# Before writing Bob's POV
bob_state = query_state("bob", "ch1_opening", 1)
# bob_state.facts includes the combination
```

## When to Use This Agent

- **Start of project**: Set up moments, characters, root take
- **Before writing POV scene**: Query character state
- **After scene**: Log new facts and knowledge events
- **Exploring alternatives**: Create takes to try different knowledge distributions
- **Debugging knowledge**: Check if character should know something

## Integration with Story-Orchestrator

When story-orchestrator creates the beat sheet:
1. Use create_moment for each major beat (chapter/act transitions)
2. Register all POV characters
3. Create a take-0 "trunk" for the canonical path

Let the writer manage fact logging during actual drafting.
""")
        print(f"  [OK] Created state-manager agent")

    # Create knowledge-query agent
    knowledge_query = state_agents_dir / "knowledge-query.md"
    if not knowledge_query.exists():
        knowledge_query.write_text("""---
name: knowledge-query
description: Quick queries of character knowledge state. Use this to check what a character knows at a specific moment before writing their POV or dialogue.
model: haiku
color: blue
---

You are the **Knowledge Query** agent - a fast utility for checking character knowledge.

## Your Job

Answer the question: "What does [CHARACTER] know at [MOMENT]?"

## Usage

User provides:
- Character ID
- Moment ID (or "current")
- Take ID (default: 1)
- Optional: specific query text for semantic search

You call `query_state` and return a concise summary:

```
Character: alice
Moment: ch3_midpoint
Take: 1

Facts Known (3):
- [secret] The safe combination is 7-3-9 (learned: told, at ch2_reveal)
- [location] The warehouse is at 42 Dock Street (learned: witnessed, at ch1_opening)
- [motivation] Bob is protecting his sister (learned: inferred, at ch3_conversation)

Recent Memories (5):
- [heard] "I can't tell you everything, but..." (ch3_conversation)
- [perceived] Bob's nervous glance at the safe (ch2_reveal)
- [internal] Something doesn't add up about his story (ch3_conversation)
- [said] "Why won't you just tell me the truth?" (ch3_conversation)
- [action] Followed Bob to the warehouse district (ch2_investigation)
```

## Tips

- If user says "current", ask for moment_id
- Default to take_id=1 unless specified
- Use query_text parameter for semantic search (e.g., "safe combination")
- Keep output focused and actionable
""")
        print(f"  [OK] Created knowledge-query agent")

    return True


def create_state_templates(project_dir: Path):
    """Create templates for tracking narrative state."""
    templates_dir = project_dir / "templates" / "state"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Knowledge tracking template
    knowledge_template = templates_dir / "KNOWLEDGE_TRACKING.md"
    if not knowledge_template.exists():
        knowledge_template.write_text("""# Knowledge Tracking

Track what each character knows and when they learn it.

## Characters

| Character ID | Name | Registered | Traits |
|-------------|------|-----------|--------|
| alice | Alice Chen | [OK] | analytical, curious |
| bob | Bob Martinez | [OK] | secretive, protective |

## Moments

| ID | Sequence | Label | Chapter |
|----|----------|-------|---------|
| ch1_opening | 1 | Opening scene | 1 |
| ch1_discovery | 2 | Safe found | 1 |
| ch2_reveal | 10 | Bob reveals partial truth | 2 |
| ch3_midpoint | 15 | Midpoint revelation | 3 |

## Facts Registry

| Fact ID | Content | Category | Created At |
|---------|---------|----------|------------|
| 1 | Safe combination is 7-3-9 | secret | ch1_opening |
| 2 | Warehouse at 42 Dock Street | location | ch1_opening |
| 3 | Bob protecting his sister | motivation | ch2_reveal |

## Knowledge Events

| Character | Fact | Moment | Source | Notes |
|-----------|------|---------|--------|-------|
| bob | 1 | ch1_opening | discovered | Found combination in ledger |
| alice | 2 | ch1_opening | witnessed | Followed Bob there |
| alice | 3 | ch3_midpoint | inferred | From Bob's behavior pattern |
| alice | 1 | ch4_climax | told | Bob finally reveals it |

## Takes (Branches)

| Take ID | Parent | Branch Point | Status | Notes |
|---------|--------|--------------|--------|-------|
| 1 | - | - | trunk | Main timeline |
| 2 | 1 | ch3_midpoint | active | What if Alice finds out earlier? |
| 3 | 1 | ch2_reveal | archived | Tried full reveal, didn't work |

## Quick Reference

### Before Writing a Character Scene

1. Query their state: `query_state(character, moment, take)`
2. Review facts and memories returned
3. Write scene constrained to that knowledge

### After Writing a Scene

1. Identify new facts established
2. Log who learned each fact (and how)
3. Record dialogue/memories as needed

### Exploring Alternatives

1. Create take from branch point
2. Modify knowledge distribution
3. Compare character states across takes
""")
        print(f"  [OK] Created knowledge tracking template")

    # State management guide
    state_guide = templates_dir / "STATE_MANAGEMENT_GUIDE.md"
    if not state_guide.exists():
        state_guide.write_text("""# State Management Guide

Using Phantom State with phantom_scribe.

## Core Concept

**Structural Absence**: Characters can only access information in their retrieval context. No prompt engineering needed.

## Setup (Once per Project)

1. **Create Moments** (one per major beat):
   ```
   create_moment(id="ch1_opening", sequence=1, label="Opening")
   create_moment(id="ch2_midpoint", sequence=10, label="Midpoint")
   ```

2. **Register Characters**:
   ```
   register_character(
       id="alice",
       name="Alice Chen",
       traits={"analytical": true, "curious": true},
       voice={"style": "precise", "favors_questions": true}
   )
   ```

3. **Create Root Take**:
   ```
   create_take()  # Returns take_id=1 (trunk)
   ```

## During Writing

### Establishing Facts

When a fact is established in the story:
```
fact_id = log_fact(
    content="The murder weapon is in the shed",
    category="evidence",
    moment_id="ch3_discovery"
)
```

### Recording Knowledge

When a character learns:
```
log_knowledge(
    character_id="detective",
    fact_id=fact_id,
    moment_id="ch4_investigation",
    take_id=1,
    source="discovered"  # witnessed/told/inferred/discovered
)
```

### Recording Dialogue

```
dialogue(
    speaker="alice",
    content="I know where you hid it.",
    moment_id="ch5_confrontation",
    take_id=1,
    listeners=["bob"]
)
```

This automatically creates:
- `said` memory for alice
- `heard` memory for bob

### Recording Other Experiences

```
# Internal thoughts
embed_memory(
    character_id="alice",
    chunk="Something about his story doesn't add up.",
    moment_id="ch3_conversation",
    take_id=1,
    chunk_type="internal"
)

# Perceptions
embed_memory(
    character_id="alice",
    chunk="Bob's hand trembled when I mentioned the shed.",
    moment_id="ch5_confrontation",
    take_id=1,
    chunk_type="perceived"
)

# Actions
embed_memory(
    character_id="alice",
    chunk="Followed Bob to the warehouse district.",
    moment_id="ch2_investigation",
    take_id=1,
    chunk_type="action"
)
```

## Querying State

**Before writing any character's POV**, query their knowledge:

```
state = query_state(
    character_id="alice",
    moment_id="ch5_confrontation",
    take_id=1,
    query_text="shed murder weapon",  # Optional: semantic search
    fact_limit=50,
    memory_limit=20
)
```

Returns:
- `facts`: What they know factually
- `memories`: Experiential memories (said, heard, perceived, internal, action)
- `traits`: Their personality constraints
- `voice`: Their speech patterns

**Use this to constrain generation** - the character literally cannot access anything not in the results.

## Branching for Alternatives

### Creating a Branch

```
new_take = create_take(
    parent_take_id=1,
    branch_point="ch3_discovery",
    notes="What if Alice knew about the shed earlier?"
)
```

### Modifying Knowledge in Branch

```
# In new take, Alice learns earlier
log_knowledge(
    character_id="alice",
    fact_id=weapon_fact_id,
    moment_id="ch2_investigation",  # Earlier moment
    take_id=new_take,
    source="discovered"
)
```

### Comparing States

```
# Alice's knowledge in trunk (take 1)
trunk_state = query_state("alice", "ch5_confrontation", take_id=1)

# Alice's knowledge in alternate (take 2)
alt_state = query_state("alice", "ch5_confrontation", take_id=new_take)

# Compare and decide which timeline to continue
```

## Integration with Phantom Scribe Workflow

### With story-orchestrator

After creating beat sheet:
1. Create moments for each chapter/act
2. Register POV characters
3. Create trunk take

### With character-sketcher

After sketching character:
1. Register in state engine with traits/voice from sketch
2. Log any backstory facts they'd know

### With canon-keeper

When logging canon facts:
1. Use log_fact for world truths
2. Log which characters know each fact

### During Chapter Writing

**Before**: Query character state at chapter start moment
**During**: Log dialogue, perceptions, thoughts as you write
**After**: Review and log any new facts/knowledge established

## Best Practices

1. **Moment Granularity**: One moment per chapter or major scene, not every action
2. **Fact vs Memory**: Facts are discrete knowledge, memories are experiential
3. **Source Tracking**: Always specify how knowledge was acquired
4. **Query First**: Always query before writing POV
5. **Takes for Exploration**: Use branches liberally - they're cheap and preserve history

## Common Patterns

### Mystery/Thriller Clues

```
# Establish clue
clue_id = log_fact("Blood on the doorframe", "evidence", "ch2_scene")

# Detective finds it
log_knowledge("detective", clue_id, "ch3_investigation", 1, "discovered")

# Suspect already knew (was there)
log_knowledge("suspect", clue_id, "ch2_scene", 1, "witnessed")
```

### Character Revelation

```
# Secret fact
secret_id = log_fact("Bob is protecting his sister", "motivation", "ch1_opening")

# Bob always knew
log_knowledge("bob", secret_id, "ch1_opening", 1, "witnessed")

# Alice infers it midpoint
log_knowledge("alice", secret_id, "ch3_midpoint", 1, "inferred")
```

### Unreliable Narrator

```
# True fact
truth_id = log_fact("John was at the bar", "alibi", "ch1_opening")

# Narrator believes false version
false_id = log_fact("John was at home", "alibi", "ch1_opening")
log_knowledge("narrator", false_id, "ch1_opening", 1, "told")

# Reader eventually learns truth
log_knowledge("narrator", truth_id, "ch8_reveal", 1, "discovered")
```
""")
        print(f"  [OK] Created state management guide")

    return True


def enhance_project(project_dir: Path, db_path: str = "narrative_state.db"):
    """Enhance a phantom_scribe project with Phantom State."""
    print(f"\nEnhancing: {project_dir}")

    # Add MCP config
    add_mcp_config(project_dir, db_path)

    # Create enhanced agents
    create_enhanced_agents(project_dir)

    # Create state templates
    create_state_templates(project_dir)

    print(f"  [OK] Enhancement complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Enhance phantom_scribe installations with Phantom State",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect and enhance
  python enhance_phantom_scribe.py

  # Enhance specific directory
  python enhance_phantom_scribe.py --project /path/to/story

  # Specify custom database path
  python enhance_phantom_scribe.py --db-path story_state.db

  # List installations without enhancing
  python enhance_phantom_scribe.py --list-only
        """
    )

    parser.add_argument(
        "--project",
        type=Path,
        help="Specific project directory to enhance (auto-detects if not provided)"
    )

    parser.add_argument(
        "--db-path",
        default="narrative_state.db",
        help="Database path for narrative state (default: narrative_state.db)"
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List detected installations without modifying"
    )

    args = parser.parse_args()

    print("Phantom State + phantom_scribe Enhancer")
    print("=" * 50)

    # Find installations
    if args.project:
        if not (args.project / ".claude" / "agents" / "story-orchestrator.md").exists():
            print(f"\n[X] Not a phantom_scribe project: {args.project}")
            print("   (missing .claude/agents/story-orchestrator.md)")
            return 1
        installations = [args.project]
    else:
        print("\nSearching for phantom_scribe installations...")
        installations = find_phantom_scribe_installations()

    if not installations:
        print("\n[X] No phantom_scribe installations found.")
        print("\nSearched:")
        print("  - Current directory")
        print("  - Parent directories (up 3 levels)")
        print("  - ~/.codex/skills/phantom-scribe")
        print("\nTo enhance a specific project:")
        print("  python enhance_phantom_scribe.py --project /path/to/project")
        return 1

    print(f"\n[OK] Found {len(installations)} installation(s):")
    for p in installations:
        print(f"  - {p}")

    if args.list_only:
        return 0

    # Enhance each
    for project in installations:
        enhance_project(project, args.db_path)

    print("\n" + "=" * 50)
    print("[OK] Enhancement complete!")
    print("\nNext steps:")
    print("1. Restart Claude Code to load new agents")
    print("2. Use 'state-manager' agent to set up moments and characters")
    print("3. Use 'knowledge-query' agent to check character knowledge")
    print("4. See templates/state/STATE_MANAGEMENT_GUIDE.md for workflow")

    return 0


if __name__ == "__main__":
    sys.exit(main())
