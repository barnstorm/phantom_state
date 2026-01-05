"""Phantom State - Narrative state engine for multi-agent dialogue generation."""

from phantom_state.models import (
    EngineConfig,
    Fact,
    Memory,
    CorpusChunk,
    CharacterState,
    Take,
)
from phantom_state.engine import NarrativeStateEngine

__version__ = "0.1.0"

__all__ = [
    "NarrativeStateEngine",
    "EngineConfig",
    "Fact",
    "Memory",
    "CorpusChunk",
    "CharacterState",
    "Take",
]
