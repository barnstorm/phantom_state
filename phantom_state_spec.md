
# Phantom State - Narrative State Engine — Specification

## Problem

LLMs simulating characters who "don't know" something fail. The knowledge exists in context; suppression leaks through word choice, question patterns, what gets skipped. Prompt-based instructions ("pretend you don't know X") are enforcement by honor system.

Authentic bounded cognition requires structural absence. If information isn't in retrieval context, it can't contaminate.

## What This Is

A state management engine for multi-agent dialogue generation. Characters are persistent agents with bounded memory. Each owns a separate store. Retrieval scoped to their table only. Temporal gating enforced by query, not prompt.

The engine doesn't know about story structure, genres, or narrative frameworks. It maintains character state with temporal bounds. Consumers decide what to do with the output.

---

## Core Concepts

**Character**: Persistent agent with identity (traits, voice) and memory (facts known, experiences had). Memory is private — no character can query another's store.

**Moment**: Abstract temporal marker. Could be scene, beat, timestamp, turn number. Provides ordering for gating.

**Memory**: Two types:
- Structured: hard facts, discrete knowledge events
- Experiential: embedded chunks (dialogue, perception, internal state)

**Take**: A branch of state. Run a scene, don't like it, branch and retry. Full history preserved. Enables "what if" exploration and curation across multiple runs.

**Orchestrator**: The entity that sets scenes and manages turns. Has read access to all character stores. Does not speak for characters.

---

## Configuration

```python
EngineConfig(
  db_path: str,
  embedding_backend: str = "local",  # "local" | "openai"
  embedding_model: str = "all-MiniLM-L6-v2",  # for local
  openai_model: str = "text-embedding-3-small",  # if backend="openai"
  chunk_granularity: str = "paragraph",  # "sentence" | "paragraph" | "beat" | "manual"
  vector_dimensions: int = 384,  # matches model
)
```

---

## Schema

### Temporal Structure

```sql
CREATE TABLE moments (
  id TEXT PRIMARY KEY,
  sequence INTEGER UNIQUE NOT NULL,
  label TEXT,
  metadata TEXT  -- JSON
);

CREATE INDEX idx_moments_sequence ON moments(sequence);
```

### Branching

```sql
CREATE TABLE takes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_take_id INTEGER REFERENCES takes(id),
  branch_point TEXT REFERENCES moments(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status TEXT DEFAULT 'active',  -- 'active', 'archived', 'trunk'
  notes TEXT
);

CREATE INDEX idx_takes_parent ON takes(parent_take_id);
CREATE INDEX idx_takes_status ON takes(status);
```

### Characters

```sql
CREATE TABLE characters (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  traits TEXT,  -- JSON: personality constraints
  voice TEXT    -- JSON: speech patterns, markers
);
```

### Structured Knowledge

```sql
CREATE TABLE facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content TEXT NOT NULL,
  category TEXT,
  created_at TEXT REFERENCES moments(id)
);

CREATE INDEX idx_facts_category ON facts(category);

CREATE TABLE knowledge_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id TEXT NOT NULL REFERENCES characters(id),
  fact_id INTEGER NOT NULL REFERENCES facts(id),
  moment_id TEXT NOT NULL REFERENCES moments(id),
  take_id INTEGER NOT NULL REFERENCES takes(id),
  source TEXT,  -- 'witnessed', 'told', 'inferred', 'discovered'
  UNIQUE(character_id, fact_id, take_id)
);

CREATE INDEX idx_knowledge_character ON knowledge_events(character_id);
CREATE INDEX idx_knowledge_take ON knowledge_events(take_id);
```

### Experiential Memory (Per-Character Vector Tables)

Created dynamically on character registration. Using sqlite-vec.

```sql
-- Template: {character_id}_memory
CREATE TABLE {character_id}_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk TEXT NOT NULL,
  embedding FLOAT[{dimensions}],  -- from config
  moment_id TEXT NOT NULL REFERENCES moments(id),
  take_id INTEGER NOT NULL REFERENCES takes(id),
  chunk_type TEXT NOT NULL,  -- 'said', 'heard', 'internal', 'perceived', 'action'
  tags TEXT  -- JSON
);

CREATE INDEX idx_{character_id}_memory_moment ON {character_id}_memory(moment_id);
CREATE INDEX idx_{character_id}_memory_take ON {character_id}_memory(take_id);
CREATE INDEX idx_{character_id}_memory_type ON {character_id}_memory(chunk_type);
```

### Corpus (Shared Canon)

Foundational material accessible to all entities without temporal or character gating.

```sql
-- Shared reference material
CREATE TABLE IF NOT EXISTS corpus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source TEXT,              -- origin file/doc name
    section TEXT,             -- location within source
    category TEXT,            -- 'spec', 'canon', 'reference', 'draft', etc.
    version TEXT,             -- document version
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT             -- JSON
);

CREATE INDEX IF NOT EXISTS idx_corpus_source ON corpus(source);
CREATE INDEX IF NOT EXISTS idx_corpus_category ON corpus(category);
CREATE INDEX IF NOT EXISTS idx_corpus_version ON corpus(version);

-- Shared vector table for corpus
CREATE VIRTUAL TABLE IF NOT EXISTS corpus_vec
USING vec0(embedding float[{dimensions}]);
```

---

## Take Ancestry

Recursive query to get full lineage of a take:

```sql
WITH RECURSIVE ancestry(id) AS (
  SELECT :take_id
  UNION ALL
  SELECT t.parent_take_id
  FROM takes t
  JOIN ancestry a ON t.id = a.id
  WHERE t.parent_take_id IS NOT NULL
)
SELECT id FROM ancestry;
```

All queries filter by `take_id IN (ancestry)` to include memories from current branch plus all ancestors.

---

## Queries

### Character Facts at Moment

```sql
SELECT f.content, f.category, ke.source, ke.moment_id
FROM facts f
JOIN knowledge_events ke ON f.id = ke.fact_id
JOIN moments m ON ke.moment_id = m.id
WHERE ke.character_id = :character_id
  AND ke.take_id IN (SELECT id FROM take_ancestry(:take_id))
  AND m.sequence <= (SELECT sequence FROM moments WHERE id = :moment_id)
ORDER BY m.sequence;
```

### Character Memory at Moment (Vector Similarity)

```sql
SELECT chunk, chunk_type, tags, moment_id
FROM {character_id}_memory
WHERE take_id IN (SELECT id FROM take_ancestry(:take_id))
  AND moment_id IN (
    SELECT id FROM moments 
    WHERE sequence <= (SELECT sequence FROM moments WHERE id = :moment_id)
  )
ORDER BY vec_distance(embedding, :query_vector)
LIMIT :k;
```

### Character Memory at Moment (All, No Similarity)

```sql
SELECT chunk, chunk_type, tags, moment_id
FROM {character_id}_memory m
JOIN moments mo ON m.moment_id = mo.id
WHERE m.take_id IN (SELECT id FROM take_ancestry(:take_id))
  AND mo.sequence <= (SELECT sequence FROM moments WHERE id = :moment_id)
ORDER BY mo.sequence;
```

### Corpus Query (Vector Similarity)

```sql
SELECT c.id, c.content, c.source, c.section, c.category, c.version, c.metadata
FROM corpus_vec cv
JOIN corpus c ON cv.rowid = c.id
WHERE cv.embedding MATCH :query_vector
  AND k = :limit
  AND (:category IS NULL OR c.category = :category)
  AND (:version IS NULL OR c.version = :version)
  AND (:source IS NULL OR c.source = :source)
ORDER BY cv.distance;
```

---

## Three-Tier Retrieval Model

```
┌─────────────────────────────────────────────────────────────┐
│  CORPUS (ungated)                                           │
│  - Shared by all entities                                   │
│  - No temporal restrictions                                 │
│  - Versioned for document evolution                         │
│  - The "ground truth" reference layer                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FACTS + KNOWLEDGE_EVENTS (character + temporal gated)      │
│  - World truths exist independently                         │
│  - Characters learn facts at specific moments               │
│  - Query filters by: character_id, moment.sequence, take    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  MEMORIES (character + temporal + take gated)               │
│  - Experiential chunks (said/heard/internal/perceived)      │
│  - Fully isolated per character                             │
│  - Branch-aware via take ancestry                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Embedding Pipeline

```
Input: text chunk + metadata
    ↓
Embedding model (local or API) → vector
    ↓
INSERT INTO {character_id}_memory (
  chunk, embedding, moment_id, take_id, chunk_type, tags
)
```

### Backend Abstraction

```python
class EmbeddingBackend(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

class LocalEmbedding(EmbeddingBackend):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
    
    def embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()

class OpenAIEmbedding(EmbeddingBackend):
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.client = OpenAI()
    
    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in response.data]
```

Latency target: <500ms from text to stored.

---

## Core Operations

### Engine Initialization

```python
class NarrativeStateEngine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.db = sqlite3.connect(config.db_path)
        self._load_sqlite_vec()
        self._init_schema()
        self._init_embedding_backend()
```

### Create Moment

```python
def create_moment(
    self,
    id: str,
    sequence: int,
    label: str = None,
    metadata: dict = None
) -> str:
    """
    Create a temporal marker.
    Sequence must be unique and determines ordering.
    Returns moment id.
    """
```

### Create Take

```python
def create_take(
    self,
    parent_take_id: int = None,
    branch_point: str = None,
    notes: str = None
) -> int:
    """
    Create a new take (branch).
    If no parent, creates root take.
    Returns take id.
    """
```

### Register Character

```python
def register_character(
    self,
    id: str,
    name: str,
    traits: dict = None,
    voice: dict = None
) -> str:
    """
    Register a character and create their memory table.
    Tables created eagerly on registration.
    Returns character id.
    """
```

### Log Fact

```python
def log_fact(
    self,
    content: str,
    category: str,
    moment_id: str
) -> int:
    """
    Record a fact in the world.
    Facts exist independent of who knows them.
    Returns fact id.
    """
```

### Log Knowledge

```python
def log_knowledge(
    self,
    character_id: str,
    fact_id: int,
    moment_id: str,
    take_id: int,
    source: str = None
) -> int:
    """
    Record that a character learned a fact.
    Source: 'witnessed', 'told', 'inferred', 'discovered'
    Returns knowledge_event id.
    """
```

### Embed Memory (Primitive)

```python
def embed_memory(
    self,
    character_id: str,
    chunk: str,
    moment_id: str,
    take_id: int,
    chunk_type: str,
    tags: dict = None
) -> int:
    """
    Embed experiential memory for a character.
    chunk_type: 'said', 'heard', 'internal', 'perceived', 'action'
    Returns memory id.
    """
```

### Dialogue (Convenience)

```python
def dialogue(
    self,
    speaker: str,
    content: str,
    moment_id: str,
    take_id: int,
    listeners: list[str] = None,
    speaker_tags: dict = None,
    listener_tags: dict = None
) -> dict:
    """
    Convenience method for dialogue.
    Embeds to speaker as 'said', to each listener as 'heard'.
    Returns {speaker_memory_id, listener_memory_ids: []}.
    """
```

### Query Character State

```python
def query_state(
    self,
    character_id: str,
    moment_id: str,
    take_id: int,
    query_text: str = None,
    fact_limit: int = 50,
    memory_limit: int = 20,
    include_corpus: bool = True,
    corpus_limit: int = 20,
    corpus_category: str | None = None,
    corpus_version: str | None = None,
) -> CharacterState:
    """
    Get everything a character knows/has experienced up to moment.

    Three retrieval tiers:
    1. Corpus (shared, ungated) — foundational reference material
    2. Facts (character + temporal gated) — learned discrete knowledge
    3. Memories (character + temporal + take gated) — experiential chunks

    If query_text provided, all tiers use vector similarity.
    Otherwise facts/memories return chronologically, corpus by recency.

    Returns:
        CharacterState(
            facts: list[Fact],
            memories: list[Memory],
            corpus: list[CorpusChunk],
            traits: dict,
            voice: dict
        )
    """
```

### Branch

```python
def branch(
    self,
    parent_take_id: int,
    branch_point: str,
    notes: str = None
) -> int:
    """
    Create a new take branching from parent at branch_point.
    Subsequent writes use new take_id.
    Queries see parent history plus new writes.
    Returns new take id.
    """
```

### List Takes

```python
def list_takes(
    self,
    status: str = None,
    moment_id: str = None
) -> list[Take]:
    """
    List takes, optionally filtered by status or branch point.
    """
```

### Set Take Status

```python
def set_take_status(
    self,
    take_id: int,
    status: str
) -> None:
    """
    Update take status: 'active', 'archived', 'trunk'
    Manual management only — no automatic GC.
    """
```

### Get Take Ancestry

```python
def get_ancestry(
    self,
    take_id: int
) -> list[int]:
    """
    Get full lineage of take ids from root to given take.
    """
```

---

## Corpus Operations

### Load Corpus Chunk

```python
def load_corpus_chunk(
    self,
    content: str,
    source: str,
    section: str | None = None,
    category: str | None = None,
    version: str | None = None,
    metadata: dict | None = None,
) -> int:
    """
    Load a single chunk into shared corpus.

    Args:
        content: The text content
        source: Origin document name/path
        section: Location within source (chapter, page, etc.)
        category: Type of content ('spec', 'canon', 'reference', 'draft')
        version: Document version
        metadata: Additional JSON metadata

    Returns:
        The corpus chunk id
    """
```

### Load Document

```python
def load_document(
    self,
    filepath: str,
    source: str,
    category: str,
    version: str | None = None,
    chunker: str | None = None,  # defaults to config.chunk_granularity
    metadata: dict | None = None,
) -> list[int]:
    """
    Load and vectorize a document into corpus.

    Reads file, splits into chunks, embeds each, stores in corpus.

    Args:
        filepath: Path to document
        source: Name to store as source
        category: Category for all chunks
        version: Version tag for all chunks
        chunker: Override chunk granularity ('sentence', 'paragraph', 'page')
        metadata: Additional metadata applied to all chunks

    Returns:
        List of corpus chunk ids created
    """
```

### Query Corpus

```python
def query_corpus(
    self,
    query_text: str,
    category: str | None = None,
    version: str | None = None,
    source: str | None = None,
    limit: int = 20,
) -> list[CorpusChunk]:
    """
    Query corpus by vector similarity with optional filters.

    Args:
        query_text: Text to find similar chunks for
        category: Filter by category
        version: Filter by version
        source: Filter by source document
        limit: Max chunks to return

    Returns:
        List of CorpusChunk ordered by similarity
    """
```

### Delete Corpus Version

```python
def delete_corpus_version(
    self,
    source: str,
    version: str,
) -> int:
    """
    Delete all corpus chunks for a source/version.

    Use when replacing a document version.

    Returns:
        Number of chunks deleted
    """
```

---

## Data Classes

```python
@dataclass
class EngineConfig:
    db_path: str
    embedding_backend: str = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    openai_model: str = "text-embedding-3-small"
    chunk_granularity: str = "paragraph"
    vector_dimensions: int = 384

@dataclass
class Fact:
    id: int
    content: str
    category: str
    source: str
    moment_id: str

@dataclass
class Memory:
    id: int
    chunk: str
    chunk_type: str
    tags: dict
    moment_id: str

@dataclass
class CorpusChunk:
    id: int
    content: str
    source: str
    section: str | None
    category: str | None
    version: str | None
    metadata: dict

@dataclass
class CharacterState:
    character_id: str
    moment_id: str
    take_id: int
    facts: list[Fact]
    memories: list[Memory]
    corpus: list[CorpusChunk]  # shared reference material
    traits: dict
    voice: dict

@dataclass
class Take:
    id: int
    parent_take_id: int
    branch_point: str
    created_at: str
    status: str
    notes: str
```

---

## Usage Example

```python
from narrative_state_engine import NarrativeStateEngine, EngineConfig

# Initialize
config = EngineConfig(db_path="story.db")
engine = NarrativeStateEngine(config)

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

# Scene loop
alex_state = engine.query_state("alex", "scene1_start", take)
# → alex_state.facts is empty — Alex doesn't know about the experiment

webb_state = engine.query_state("webb", "scene1_start", take)
# → webb_state.facts contains the experiment fact

# Generate dialogue (pseudo-code for LLM calls)
webb_line = generate_response(webb_state, scene_context)
# "I've been researching what happened at PSU in 1980."

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

alex_line = generate_response(alex_state, scene_context + webb_line)
# "I don't know what you're talking about."

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

# Rerun scene — new memories go to take2
# Original take untouched
```

---

## File Structure

```
narrative_state_engine/
├── src/
│   ├── __init__.py
│   ├── engine.py          # NarrativeStateEngine class
│   ├── schema.sql         # table definitions
│   ├── queries.py         # SQL builders
│   ├── embedding.py       # backend abstraction
│   ├── models.py          # dataclasses
│   └── config.py          # EngineConfig
├── tests/
│   ├── __init__.py
│   ├── test_schema.py
│   ├── test_branching.py
│   ├── test_queries.py
│   ├── test_embedding.py
│   └── test_two_agents.py  # validation test
├── examples/
│   └── basic_dialogue.py
├── requirements.txt
└── README.md
```

---

## Dependencies

```
# requirements.txt
sqlite-vec>=0.1.0
sentence-transformers>=2.2.0  # for local embeddings
openai>=1.0.0                 # optional, for API embeddings
```

- Python 3.10+
- sqlite3 (stdlib)
- sqlite-vec extension (vector similarity)
- sentence-transformers (local embedding default)
- openai (optional, if using API embeddings)

---

## Validation Test

Before building full system, prove the core premise:

```python
def test_bounded_knowledge():
    """
    Two characters, divergent knowledge.
    Verify retrieval returns only appropriate state.
    """
    engine = NarrativeStateEngine(EngineConfig(db_path=":memory:"))
    
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
```

Then test with actual LLM generation:

1. Same scene setup for both characters
2. Each gets separate API call with only their `query_state` result
3. Observe:
   - Does A reference the secret naturally?
   - Does B genuinely not know (not suppressing — absent)?
   - Does dialogue differ from single-agent generation?

If bounded retrieval produces noticeably different behavior, proceed. If not, architecture is wrong.

---

## Out of Scope

- Story structure (beats, acts, chapters)
- Plot management
- Narrative frameworks
- Agent prompt engineering
- LLM selection / API calls
- Output formatting
- Automatic chunking of large text

The engine maintains state. What consumers do with that state is their concern.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chunk granularity | Configurable | Optimal size varies by use case |
| Embedding backend | Local default, API optional | No external dependency for basic use |
| Memory tables | Eager creation | Predictable schema, no runtime surprises |
| Cross-character experience | Primitives + convenience | Maximum control, less boilerplate for common case |
| Take garbage collection | Manual only | Caller knows what to preserve |
| Take ancestry | Recursive CTE | Clean, single query, SQL-native |
| Single corpus table | Shared, not per-entity | Canon is universal ground truth |
| Corpus version field | String, not incrementing | Supports semantic versions, draft names |
| Corpus category filter | Optional on query | Different entity types may need different subsets |
| No temporal gating for corpus | By design | Corpus is reference, not narrative state |
| Corpus separate from facts | Facts are learned, corpus is given | Different access patterns |

---

## Open Questions

**Chunk extraction**: Engine accepts chunks. Should it provide optional utilities for extracting chunks from larger text based on `chunk_granularity` setting?

**Memory deduplication**: If same content embedded twice (e.g., correction), keep both or dedupe?

**Moment validation**: Enforce that moment_id exists before allowing knowledge/memory writes, or allow dangling references?

**Vector index**: sqlite-vec handles small-medium scale. At what point does a dedicated vector DB become necessary?

---

## Future Considerations

Not in v1, but potential additions:

- **Semantic fact merging**: Detect when new fact supersedes old fact
- **Memory decay**: Weight older memories lower in retrieval
- **Character relationships**: Explicit modeling of how characters perceive each other
- **Scene context**: Formal model for "who is present" to automate listener distribution
- **Export/import**: Serialize engine state for backup or transfer
- **MCP server**: Expose operations as tool calls for external agents
