"""Data models for Phantom State."""

from dataclasses import dataclass, field


@dataclass
class EngineConfig:
    """Configuration for NarrativeStateEngine."""

    db_path: str
    embedding_backend: str = "local"  # "local" | "openai" | "hash"
    embedding_model: str = "all-MiniLM-L6-v2"  # for local
    openai_model: str = "text-embedding-3-small"  # if backend="openai"
    chunk_granularity: str = "paragraph"  # "sentence" | "paragraph" | "beat" | "manual"
    vector_dimensions: int = 384  # matches model


@dataclass
class Fact:
    """A discrete piece of knowledge in the world."""

    id: int
    content: str
    category: str
    source: str  # how the character learned it
    moment_id: str


@dataclass
class Memory:
    """An experiential memory chunk."""

    id: int
    chunk: str
    chunk_type: str  # 'said', 'heard', 'internal', 'perceived', 'action'
    tags: dict
    moment_id: str


@dataclass
class CorpusChunk:
    """A chunk of shared reference material."""

    id: int
    content: str
    source: str
    section: str | None
    category: str | None
    version: str | None
    metadata: dict


@dataclass
class CharacterState:
    """Complete state of a character at a given moment."""

    character_id: str
    moment_id: str
    take_id: int
    facts: list[Fact] = field(default_factory=list)
    memories: list[Memory] = field(default_factory=list)
    corpus: list[CorpusChunk] = field(default_factory=list)
    traits: dict = field(default_factory=dict)
    voice: dict = field(default_factory=dict)


@dataclass
class Take:
    """A branch of narrative state."""

    id: int
    parent_take_id: int | None
    branch_point: str | None
    created_at: str
    status: str  # 'active', 'archived', 'trunk'
    notes: str | None
