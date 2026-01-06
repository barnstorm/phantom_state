## Phantom State + phantom_scribe Integration

Add character knowledge boundaries to your phantom_scribe story projects.

## What This Does

Phantom State enhances phantom_scribe with **structural knowledge enforcement**:

- **Bounded character knowledge** - Characters only know what they've learned
- **Temporal gating** - Knowledge at moment M doesn't leak to earlier moments
- **Branching exploration** - Try "what if X knew Y?" without losing history
- **Automatic memory** - Dialogue/perceptions/thoughts embedded with vector search

**No more "try to forget this" prompts** - if information isn't in the character's state, the LLM literally can't access it.

## Installation

### 1. Install Phantom State

```bash
cd phantom_state
uv pip install -e .
```

### 2. Enhance Your phantom_scribe Project

```bash
# Auto-detect and enhance
python phantom_state/scripts/enhance_phantom_scribe.py

# Or specify project
python phantom_state/scripts/enhance_phantom_scribe.py --project /path/to/story
```

This adds:
- Phantom State MCP server config to `.claude/mcp_config.json`
- New agents: `state-manager`, `knowledge-query`
- Templates for tracking character knowledge
- State management guide

If you're using Codex CLI (instead of Claude Code), add the Phantom State MCP server to your Codex MCP configuration using `mcp_config.example.json` or `mcp_config.uv.example.json` as a starting point.

### 3. Restart Your MCP Client

Reload to pick up the new agents and/or MCP server.

## Quick Start

### Setup (Once Per Project)

Use the **state-manager** agent:

```
You: "Set up narrative state for this story"

state-manager:
1. Creates moments for each chapter (ch1_opening, ch2_discovery, etc.)
2. Registers POV characters with traits/voice
3. Creates trunk take (canonical timeline)
```

### During Writing

**Before writing a character's POV:**

Use **knowledge-query**:
```
You: "What does Alice know at ch3_midpoint?"

knowledge-query returns:
- Facts she knows (and how she learned them)
- Recent memories (dialogue, perceptions, thoughts)
- Use this to constrain what she can think/say/do
```

**After writing a scene:**

Use **state-manager** to log:
```
You: "Log this scene's knowledge events:
- Bob discovered the safe combination (source: discovered)
- Alice heard Bob mention the warehouse (source: heard)
- Alice perceived Bob's nervous glance (source: witnessed)"

state-manager:
- Logs facts
- Records knowledge events
- Embeds memories
```

## Integration with Existing phantom_scribe Workflow

### With story-orchestrator

After beat sheet generation:
1. Run state-manager to create moments for each major beat
2. Register all POV characters
3. Create trunk take

### With character-sketcher

After character sketch:
1. Register character with traits/voice from sketch
2. Log any backstory facts they'd know from the start

### With canon-keeper

When canon facts are established:
1. Log fact in Phantom State
2. Record which characters know it (and how)

### During Chapter Writing

```
Before: query_state for character at current moment
During: Write constrained to their knowledge
After:  Log new facts and knowledge events
```

## New Agents

### state-manager

**Purpose**: Set up and maintain narrative state

**Use when:**
- Starting a new project (setup moments/characters/trunk)
- After writing a scene (log facts and knowledge)
- Exploring alternate timelines (create takes)

**Key tools:**
- `create_moment` - Mark major beats
- `register_character` - Add POV characters
- `log_fact` - Record world truths
- `log_knowledge` - Record when characters learn
- `dialogue` - Record conversations
- `create_take` - Branch for alternatives

### knowledge-query

**Purpose**: Fast character knowledge lookups

**Use when:**
- Before writing character POV
- Checking if character should know something
- Debugging knowledge issues

**Returns:**
- Facts character knows (with source and moment learned)
- Recent memories (dialogue, perceptions, thoughts, actions)
- Character traits and voice

## New Templates

### templates/state/KNOWLEDGE_TRACKING.md

Track facts, knowledge events, and takes.

| Section | Purpose |
|---------|---------|
| Characters | Registry of who's been set up |
| Moments | Timeline markers |
| Facts Registry | World truths |
| Knowledge Events | Who learned what, when, how |
| Takes | Alternate timelines |

### templates/state/STATE_MANAGEMENT_GUIDE.md

Complete workflow guide with examples for:
- Mystery/thriller clues
- Character revelations
- Unreliable narrators
- Branching scenarios

## Example: Murder Mystery

```
# Setup (state-manager)
create_moment("ch1_opening", sequence=1)
create_moment("ch3_discovery", sequence=10)
register_character("detective", "Detective Sarah")
register_character("suspect", "John Doe")
create_take()  # trunk

# Establish secret (ch1)
weapon_fact = log_fact(
    "Murder weapon hidden in garden shed",
    category="evidence",
    moment="ch1_opening"
)

# Suspect knows (was there)
log_knowledge("suspect", weapon_fact, "ch1_opening", 1, "witnessed")

# Before writing Detective POV (ch1)
detective_state = query_state("detective", "ch1_opening", 1)
# detective_state.facts = [] (doesn't know yet)

# Detective discovers it (ch3)
log_knowledge("detective", weapon_fact, "ch3_discovery", 1, "discovered")

# Before writing Detective POV (ch3)
detective_state = query_state("detective", "ch3_discovery", 1)
# detective_state.facts includes weapon location (just learned!)

# Suspect's state is unchanged - still knows from ch1
```

## Example: Exploring Alternatives

```
# Current story: Suspect doesn't confess until ch8

# Create alternate take
alt_take = create_take(
    parent=1,
    branch_point="ch4_interrogation",
    notes="What if suspect confesses early?"
)

# In alternate take, suspect reveals it
confession_fact = log_fact(
    "John confesses to the murder",
    category="confession",
    moment="ch4_interrogation"
)
log_knowledge("detective", confession_fact, "ch4_interrogation", alt_take, "told")

# Compare detective's knowledge
trunk_knowledge = query_state("detective", "ch5_investigation", take=1)
alt_knowledge = query_state("detective", "ch5_investigation", take=alt_take)

# Trunk: Detective still investigating, doesn't know
# Alt: Detective knows confession, different investigation path

# Choose which timeline to continue (or keep both for comparison)
```

## Architecture

```
┌─────────────────────────────────────────┐
│  phantom_scribe                         │
│  - story-orchestrator (beat planning)   │
│  - character-sketcher                   │
│  - canon-keeper                         │
└────────────────┬────────────────────────┘
                 │ enhanced with
┌────────────────▼────────────────────────┐
│  Phantom State Integration              │
│  - state-manager (knowledge tracking)   │
│  - knowledge-query (fast lookups)       │
└────────────────┬────────────────────────┘
                 │ uses MCP
┌────────────────▼────────────────────────┐
│  Phantom State Engine                   │
│  - Per-character memory isolation       │
│  - Temporal gating                      │
│  - Take branching                       │
│  - Vector similarity search             │
└─────────────────────────────────────────┘
```

## Workflow Integration

```
1. Story Planning (story-orchestrator)
   ↓
2. State Setup (state-manager)
   - Create moments for beats
   - Register characters
   - Create trunk take
   ↓
3. Chapter Writing Loop:

   For each chapter:
     a. Query character state (knowledge-query)
     b. Write chapter constrained to knowledge
     c. Log new facts/knowledge (state-manager)
     d. Optional: Create alternate take to explore

4. Canon Management (canon-keeper + state-manager)
   - Log canon facts
   - Track who knows what

5. Character Consistency (character-profiler + knowledge-query)
   - Check character knowledge at any moment
   - Ensure dialogue/actions match what they know
```

## Benefits

### For Mystery/Thriller Writers

- **Clue economy**: Track exactly who knows which clues
- **Fair play**: Ensure detective's deductions use only available knowledge
- **Suspense**: Control information revelation timing
- **Red herrings**: Different characters believe different things

### For Multi-POV Stories

- **Asymmetric knowledge**: Each POV character has different information
- **No leakage**: Character A can't "accidentally" know what Character B is thinking
- **Tension**: Build dramatic irony (reader knows, character doesn't)
- **Consistency**: Query historical states to check earlier scenes

### For Complex Worldbuilding

- **Rule discovery**: Characters learn world rules progressively
- **Unreliable narrators**: Track "believed falsehoods" as facts
- **Knowledge distribution**: Who knows which secrets
- **Timeline tracking**: What was known when

### For Revision/Editing

- **Knowledge audit**: Check if character should know something
- **Alternate takes**: Try different revelation timings
- **Continuity**: Query character state at any past moment
- **Debugging**: "Why did this character act like they knew X?"

## Best Practices

### 1. Moment Granularity

Create moments at beat boundaries, not every paragraph:
- ✓ One per chapter or major scene
- ✓ At key revelations/discoveries
- ✗ Not every action or line of dialogue

### 2. Fact vs Memory

- **Facts**: Discrete knowledge ("combination is 7-3-9")
- **Memories**: Experiential ("saw Bob nervously glance at safe")

Use facts for trackable knowledge, memories for context/vibes.

### 3. Source Tracking

Always specify HOW knowledge was acquired:
- `witnessed` - Directly observed
- `told` - Another character revealed it
- `inferred` - Deduced from available info
- `discovered` - Found through investigation

### 4. Query Before Writing

Make it a habit:
```
Before writing POV → query_state
During writing → stay bounded
After writing → log updates
```

### 5. Takes Are Cheap

Create branches liberally:
- Try different revelation timings
- Explore "what if" scenarios
- Keep both options until you decide
- Full history preserved in ancestry

### 6. Dialogue Auto-Embeds

Use the `dialogue` tool - it automatically:
- Embeds to speaker as 'said'
- Embeds to listeners as 'heard'
- Saves manual embed_memory calls

## Troubleshooting

### "Character knows something they shouldn't"

```
1. Query their state at that moment
2. Check facts and memories returned
3. If fact is there, trace when it was logged
4. If not there, don't let them reference it
```

### "Need to change when character learns something"

```
1. Create new take from branch point
2. Log knowledge at different moment in new take
3. Query states in both takes to compare
4. Choose which timeline to continue
```

### "Forgot to log knowledge event"

```
1. Can log retroactively (just specify past moment)
2. Character state will include it for all queries after that moment
3. Queries before that moment won't include it (temporal gating)
```

### "Want to explore alternate timeline"

```
1. Create take from branch point
2. Modify knowledge events in new take
3. Write scenes in new take
4. Compare outcomes
5. Set final choice to status='trunk'
```

## Performance

- **Embedding**: ~100-300ms per memory (local backend)
- **Queries**: Fast even with 10K+ memories per character
- **Database**: ~1KB per memory + 384 bytes for embedding
- **Takes**: No performance impact until 1000s of branches

## Advanced: Direct MCP Access

For custom workflows, call MCP tools directly:

```json
{
  "tool": "query_state",
  "arguments": {
    "character_id": "detective",
    "moment_id": "ch3_discovery",
    "take_id": 1,
    "query_text": "murder weapon",
    "fact_limit": 50,
    "memory_limit": 20
  }
}
```

See [MCP_USAGE.md](MCP_USAGE.md) for complete tool reference.

## Example Projects

### Mystery Novel

```
Moments: One per chapter (30 chapters)
Characters: Detective, Suspect, Witness, Victim (flashbacks)
Facts: Clues, alibis, evidence, revelations
Knowledge: Track who knows which clues
Takes: Try different revelation timings
```

### Multi-POV Thriller

```
Moments: One per scene (~60 scenes)
Characters: 4 POV characters
Facts: Plot points, secrets, dangers
Knowledge: Each POV has different info
Takes: Explore different knowledge distributions
```

### Unreliable Narrator

```
Moments: Per chapter
Characters: Narrator, other characters
Facts: Truth vs narrator's belief
Knowledge: Narrator has "false facts", reader learns truth later
Takes: Compare narrator's reality vs truth
```

## Resources

- [Phantom State Documentation](README.md)
- [MCP Usage Guide](MCP_USAGE.md)
- [UV Setup Guide](UV_SETUP.md)
- [phantom_scribe Templates](https://github.com/barnstorm/phantom_scribe)

## Support

Issues/questions:
- Phantom State: [phantom_state issues](https://github.com/yourusername/phantom_state/issues)
- phantom_scribe: [phantom_scribe issues](https://github.com/barnstorm/phantom_scribe/issues)
