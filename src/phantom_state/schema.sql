-- Phantom State Schema
-- Core tables for narrative state management

-- Temporal Structure
CREATE TABLE IF NOT EXISTS moments (
    id TEXT PRIMARY KEY,
    sequence INTEGER UNIQUE NOT NULL,
    label TEXT,
    metadata TEXT  -- JSON
);

CREATE INDEX IF NOT EXISTS idx_moments_sequence ON moments(sequence);

-- Branching
CREATE TABLE IF NOT EXISTS takes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_take_id INTEGER REFERENCES takes(id),
    branch_point TEXT REFERENCES moments(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',  -- 'active', 'archived', 'trunk'
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_takes_parent ON takes(parent_take_id);
CREATE INDEX IF NOT EXISTS idx_takes_status ON takes(status);

-- Characters
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    traits TEXT,  -- JSON: personality constraints
    voice TEXT    -- JSON: speech patterns, markers
);

-- World Facts (independent of who knows them)
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT,
    created_at TEXT REFERENCES moments(id)
);

CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);

-- Knowledge Events (who learned what when)
CREATE TABLE IF NOT EXISTS knowledge_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL REFERENCES characters(id),
    fact_id INTEGER NOT NULL REFERENCES facts(id),
    moment_id TEXT NOT NULL REFERENCES moments(id),
    take_id INTEGER NOT NULL REFERENCES takes(id),
    source TEXT,  -- 'witnessed', 'told', 'inferred', 'discovered'
    UNIQUE(character_id, fact_id, take_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_character ON knowledge_events(character_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_take ON knowledge_events(take_id);

-- Memory metadata table (stores non-vector data for character memories)
-- This pairs with per-character vec0 virtual tables for embeddings
CREATE TABLE IF NOT EXISTS memory_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL REFERENCES characters(id),
    chunk TEXT NOT NULL,
    moment_id TEXT NOT NULL REFERENCES moments(id),
    take_id INTEGER NOT NULL REFERENCES takes(id),
    chunk_type TEXT NOT NULL,  -- 'said', 'heard', 'internal', 'perceived', 'action'
    tags TEXT  -- JSON
);

CREATE INDEX IF NOT EXISTS idx_memory_character ON memory_metadata(character_id);
CREATE INDEX IF NOT EXISTS idx_memory_moment ON memory_metadata(moment_id);
CREATE INDEX IF NOT EXISTS idx_memory_take ON memory_metadata(take_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_metadata(chunk_type);
