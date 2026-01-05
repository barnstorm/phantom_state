"""MCP server for Phantom State narrative engine.

Exposes the engine's API through Model Context Protocol tools.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)

from phantom_state.engine import NarrativeStateEngine
from phantom_state.models import EngineConfig

# Global engine instance (initialized on first connection)
_engine: NarrativeStateEngine | None = None


def get_engine() -> NarrativeStateEngine:
    """Get or initialize the engine instance."""
    global _engine
    if _engine is None:
        # Load config from environment or use defaults
        db_path = os.getenv("PHANTOM_DB_PATH", "narrative.db")
        embedding_backend = os.getenv("PHANTOM_EMBEDDING_BACKEND", "local")
        embedding_model = os.getenv(
            "PHANTOM_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
        )
        openai_model = os.getenv(
            "PHANTOM_OPENAI_MODEL", "text-embedding-3-small"
        )
        vector_dimensions = int(os.getenv("PHANTOM_VECTOR_DIMENSIONS", "384"))

        config = EngineConfig(
            db_path=db_path,
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
            openai_model=openai_model,
            vector_dimensions=vector_dimensions,
        )
        _engine = NarrativeStateEngine(config)
    return _engine


# Initialize server
server = Server("phantom_state")


# -------------------------------------------------------------------------
# Tool Definitions
# -------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="create_moment",
        description="Create a temporal marker for ordering events",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique identifier"},
                "sequence": {
                    "type": "number",
                    "description": "Ordering number (can be float for insertion, must be unique)",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable label",
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional JSON metadata",
                },
            },
            "required": ["id", "sequence"],
        },
    ),
    Tool(
        name="create_take",
        description="Create a new take (branch) in the narrative",
        inputSchema={
            "type": "object",
            "properties": {
                "parent_take_id": {
                    "type": ["integer", "null"],
                    "description": "ID of parent take (null/omit for root)",
                },
                "branch_point": {
                    "type": ["string", "null"],
                    "description": "Moment ID where branch occurs",
                },
                "notes": {"type": ["string", "null"], "description": "Human-readable notes"},
            },
        },
    ),
    Tool(
        name="list_takes",
        description="List takes, optionally filtered by status or branch point",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "archived", "trunk"],
                    "description": "Filter by status",
                },
                "moment_id": {
                    "type": "string",
                    "description": "Filter by branch point",
                },
            },
        },
    ),
    Tool(
        name="set_take_status",
        description="Update take status (active/archived/trunk)",
        inputSchema={
            "type": "object",
            "properties": {
                "take_id": {"type": "integer", "description": "ID of take"},
                "status": {
                    "type": "string",
                    "enum": ["active", "archived", "trunk"],
                },
            },
            "required": ["take_id", "status"],
        },
    ),
    Tool(
        name="register_character",
        description="Register a character and create their memory table",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique identifier"},
                "name": {"type": "string", "description": "Display name"},
                "traits": {
                    "type": "object",
                    "description": "JSON personality constraints",
                },
                "voice": {
                    "type": "object",
                    "description": "JSON speech patterns/markers",
                },
            },
            "required": ["id", "name"],
        },
    ),
    Tool(
        name="get_character",
        description="Get character data",
        inputSchema={
            "type": "object",
            "properties": {
                "character_id": {"type": "string"},
            },
            "required": ["character_id"],
        },
    ),
    Tool(
        name="log_fact",
        description="Record a fact in the world",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The fact text"},
                "category": {"type": "string", "description": "Category label"},
                "moment_id": {
                    "type": "string",
                    "description": "When the fact was established",
                },
            },
            "required": ["content", "category", "moment_id"],
        },
    ),
    Tool(
        name="log_knowledge",
        description="Record that a character learned a fact",
        inputSchema={
            "type": "object",
            "properties": {
                "character_id": {"type": "string"},
                "fact_id": {"type": "integer"},
                "moment_id": {"type": "string"},
                "take_id": {"type": "integer"},
                "source": {
                    "type": "string",
                    "enum": ["witnessed", "told", "inferred", "discovered"],
                    "description": "How they learned it",
                },
            },
            "required": ["character_id", "fact_id", "moment_id", "take_id"],
        },
    ),
    Tool(
        name="embed_memory",
        description="Store experiential memory for a character",
        inputSchema={
            "type": "object",
            "properties": {
                "character_id": {"type": "string"},
                "chunk": {"type": "string", "description": "The text content"},
                "moment_id": {"type": "string"},
                "take_id": {"type": "integer"},
                "chunk_type": {
                    "type": "string",
                    "enum": ["said", "heard", "internal", "perceived", "action"],
                },
                "tags": {"type": "object", "description": "Additional JSON tags"},
            },
            "required": [
                "character_id",
                "chunk",
                "moment_id",
                "take_id",
                "chunk_type",
            ],
        },
    ),
    Tool(
        name="dialogue",
        description="Record dialogue exchange (embeds to speaker as 'said', listeners as 'heard')",
        inputSchema={
            "type": "object",
            "properties": {
                "speaker": {"type": "string", "description": "Character ID"},
                "content": {"type": "string", "description": "What was said"},
                "moment_id": {"type": "string"},
                "take_id": {"type": "integer"},
                "listeners": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Character IDs who heard it",
                },
                "speaker_tags": {
                    "type": "object",
                    "description": "Tags for speaker's memory",
                },
                "listener_tags": {
                    "type": "object",
                    "description": "Tags for listeners' memories",
                },
            },
            "required": ["speaker", "content", "moment_id", "take_id"],
        },
    ),
    Tool(
        name="query_state",
        description="Get everything a character knows/has experienced up to a moment (corpus + facts + memories)",
        inputSchema={
            "type": "object",
            "properties": {
                "character_id": {"type": "string"},
                "moment_id": {"type": "string"},
                "take_id": {"type": "integer"},
                "query_text": {
                    "type": "string",
                    "description": "If provided, orders all tiers by similarity",
                },
                "fact_limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Max facts to return",
                },
                "memory_limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Max memories to return",
                },
                "include_corpus": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include corpus chunks",
                },
                "corpus_limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Max corpus chunks to return",
                },
                "corpus_category": {
                    "type": "string",
                    "description": "Filter corpus by category",
                },
                "corpus_version": {
                    "type": "string",
                    "description": "Filter corpus by version",
                },
            },
            "required": ["character_id", "moment_id", "take_id"],
        },
    ),
    Tool(
        name="get_ancestry",
        description="Get full lineage of take IDs from root to given take",
        inputSchema={
            "type": "object",
            "properties": {
                "take_id": {"type": "integer"},
            },
            "required": ["take_id"],
        },
    ),
    # Get operations
    Tool(
        name="get_fact",
        description="Get a specific fact by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "fact_id": {"type": "integer"},
            },
            "required": ["fact_id"],
        },
    ),
    Tool(
        name="get_facts",
        description="Get multiple facts by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "fact_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of fact IDs to retrieve",
                },
            },
            "required": ["fact_ids"],
        },
    ),
    Tool(
        name="get_memory",
        description="Get a specific memory by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer"},
            },
            "required": ["memory_id"],
        },
    ),
    Tool(
        name="get_memories",
        description="Get multiple memories by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of memory IDs to retrieve",
                },
            },
            "required": ["memory_ids"],
        },
    ),
    # List operations
    Tool(
        name="list_characters",
        description="List all registered characters",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_facts",
        description="List all facts, optionally filtered",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category"},
                "moment_id": {"type": "string", "description": "Filter by creation moment"},
            },
        },
    ),
    Tool(
        name="list_moments",
        description="List all moments in sequence order",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_memories",
        description="List all memories for a character",
        inputSchema={
            "type": "object",
            "properties": {
                "character_id": {"type": "string"},
                "include_archived": {"type": "boolean", "default": False},
            },
            "required": ["character_id"],
        },
    ),
    # Update operations
    Tool(
        name="update_character",
        description="Update an existing character",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Character ID to update"},
                "name": {"type": "string", "description": "New display name"},
                "traits": {"type": "object", "description": "New traits"},
                "voice": {"type": "object", "description": "New voice"},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="update_fact",
        description="Update an existing fact",
        inputSchema={
            "type": "object",
            "properties": {
                "fact_id": {"type": "integer"},
                "content": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["fact_id"],
        },
    ),
    Tool(
        name="update_moment",
        description="Update an existing moment",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "sequence": {"type": "number"},
                "label": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["id"],
        },
    ),
    # Delete operations
    Tool(
        name="delete_character",
        description="Delete a character and their memories",
        inputSchema={
            "type": "object",
            "properties": {
                "character_id": {"type": "string"},
            },
            "required": ["character_id"],
        },
    ),
    Tool(
        name="delete_fact",
        description="Delete a fact and associated knowledge events",
        inputSchema={
            "type": "object",
            "properties": {
                "fact_id": {"type": "integer"},
            },
            "required": ["fact_id"],
        },
    ),
    Tool(
        name="delete_moment",
        description="Delete a moment (may orphan references)",
        inputSchema={
            "type": "object",
            "properties": {
                "moment_id": {"type": "string"},
            },
            "required": ["moment_id"],
        },
    ),
    Tool(
        name="delete_memory",
        description="Delete a memory completely",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer"},
            },
            "required": ["memory_id"],
        },
    ),
    Tool(
        name="archive_memory",
        description="Mark a memory as archived/superseded",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer"},
                "superseded_by": {"type": ["integer", "null"], "description": "ID of replacement memory"},
            },
            "required": ["memory_id"],
        },
    ),
    # Batch operations
    Tool(
        name="log_facts_batch",
        description="Log multiple facts at once",
        inputSchema={
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "category": {"type": "string"},
                            "moment_id": {"type": "string"},
                        },
                        "required": ["content", "category", "moment_id"],
                    },
                },
            },
            "required": ["facts"],
        },
    ),
    Tool(
        name="log_knowledge_batch",
        description="Log multiple knowledge events at once",
        inputSchema={
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "character_id": {"type": "string"},
                            "fact_id": {"type": "integer"},
                            "moment_id": {"type": "string"},
                            "take_id": {"type": "integer"},
                            "source": {"type": "string"},
                        },
                        "required": ["character_id", "fact_id", "moment_id", "take_id"],
                    },
                },
            },
            "required": ["events"],
        },
    ),
    Tool(
        name="embed_memory_batch",
        description="Embed multiple memories at once",
        inputSchema={
            "type": "object",
            "properties": {
                "memories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "character_id": {"type": "string"},
                            "chunk": {"type": "string"},
                            "moment_id": {"type": "string"},
                            "take_id": {"type": "integer"},
                            "chunk_type": {"type": "string"},
                            "tags": {"type": "object"},
                        },
                        "required": ["character_id", "chunk", "moment_id", "take_id", "chunk_type"],
                    },
                },
            },
            "required": ["memories"],
        },
    ),
    # Corpus operations
    Tool(
        name="load_corpus_chunk",
        description="Load a single chunk into shared corpus",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The text content"},
                "source": {"type": "string", "description": "Origin document name"},
                "section": {"type": "string", "description": "Location within source"},
                "category": {"type": "string", "description": "Type: spec, canon, reference, draft"},
                "version": {"type": "string", "description": "Document version"},
                "metadata": {"type": "object"},
            },
            "required": ["content", "source"],
        },
    ),
    Tool(
        name="query_corpus",
        description="Query corpus by vector similarity",
        inputSchema={
            "type": "object",
            "properties": {
                "query_text": {"type": "string"},
                "category": {"type": "string"},
                "version": {"type": "string"},
                "source": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query_text"],
        },
    ),
    Tool(
        name="load_document",
        description="Load and vectorize a document into corpus",
        inputSchema={
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "source": {"type": "string"},
                "category": {"type": "string"},
                "version": {"type": "string"},
                "chunker": {"type": "string", "enum": ["sentence", "paragraph", "page"]},
                "metadata": {"type": "object"},
            },
            "required": ["filepath", "source", "category"],
        },
    ),
    Tool(
        name="delete_corpus_version",
        description="Delete all corpus chunks for a source/version",
        inputSchema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "version": {"type": "string"},
            },
            "required": ["source", "version"],
        },
    ),
]


# -------------------------------------------------------------------------
# MCP Handlers
# -------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    engine = get_engine()

    try:
        # Route to appropriate engine method
        if name == "create_moment":
            result = engine.create_moment(
                id=arguments["id"],
                sequence=arguments["sequence"],
                label=arguments.get("label"),
                metadata=arguments.get("metadata"),
            )
            return [TextContent(type="text", text=f"Created moment: {result}")]

        elif name == "create_take":
            result = engine.create_take(
                parent_take_id=arguments.get("parent_take_id"),
                branch_point=arguments.get("branch_point"),
                notes=arguments.get("notes"),
            )
            return [TextContent(type="text", text=f"Created take: {result}")]

        elif name == "list_takes":
            takes = engine.list_takes(
                status=arguments.get("status"),
                moment_id=arguments.get("moment_id"),
            )
            result = [
                {
                    "id": t.id,
                    "parent_take_id": t.parent_take_id,
                    "branch_point": t.branch_point,
                    "created_at": t.created_at,
                    "status": t.status,
                    "notes": t.notes,
                }
                for t in takes
            ]
            return [
                TextContent(
                    type="text", text=json.dumps(result, indent=2)
                )
            ]

        elif name == "set_take_status":
            engine.set_take_status(
                take_id=arguments["take_id"],
                status=arguments["status"],
            )
            return [
                TextContent(
                    type="text",
                    text=f"Set take {arguments['take_id']} status to {arguments['status']}",
                )
            ]

        elif name == "register_character":
            result = engine.register_character(
                id=arguments["id"],
                name=arguments["name"],
                traits=arguments.get("traits"),
                voice=arguments.get("voice"),
            )
            return [
                TextContent(type="text", text=f"Registered character: {result}")
            ]

        elif name == "get_character":
            result = engine.get_character(arguments["character_id"])
            if result is None:
                return [
                    TextContent(
                        type="text",
                        text=f"Character not found: {arguments['character_id']}",
                    )
                ]
            return [
                TextContent(
                    type="text", text=json.dumps(result, indent=2)
                )
            ]

        elif name == "log_fact":
            result = engine.log_fact(
                content=arguments["content"],
                category=arguments["category"],
                moment_id=arguments["moment_id"],
            )
            return [TextContent(type="text", text=f"Logged fact: {result}")]

        elif name == "log_knowledge":
            result = engine.log_knowledge(
                character_id=arguments["character_id"],
                fact_id=arguments["fact_id"],
                moment_id=arguments["moment_id"],
                take_id=arguments["take_id"],
                source=arguments.get("source"),
            )
            return [
                TextContent(type="text", text=f"Logged knowledge: {result}")
            ]

        elif name == "embed_memory":
            result = engine.embed_memory(
                character_id=arguments["character_id"],
                chunk=arguments["chunk"],
                moment_id=arguments["moment_id"],
                take_id=arguments["take_id"],
                chunk_type=arguments["chunk_type"],
                tags=arguments.get("tags"),
            )
            return [
                TextContent(type="text", text=f"Embedded memory: {result}")
            ]

        elif name == "dialogue":
            result = engine.dialogue(
                speaker=arguments["speaker"],
                content=arguments["content"],
                moment_id=arguments["moment_id"],
                take_id=arguments["take_id"],
                listeners=arguments.get("listeners"),
                speaker_tags=arguments.get("speaker_tags"),
                listener_tags=arguments.get("listener_tags"),
            )
            return [
                TextContent(
                    type="text", text=json.dumps(result, indent=2)
                )
            ]

        elif name == "query_state":
            state = engine.query_state(
                character_id=arguments["character_id"],
                moment_id=arguments["moment_id"],
                take_id=arguments["take_id"],
                query_text=arguments.get("query_text"),
                fact_limit=arguments.get("fact_limit", 50),
                memory_limit=arguments.get("memory_limit", 20),
                include_corpus=arguments.get("include_corpus", True),
                corpus_limit=arguments.get("corpus_limit", 20),
                corpus_category=arguments.get("corpus_category"),
                corpus_version=arguments.get("corpus_version"),
            )
            # Convert to dict for JSON serialization
            result = {
                "character_id": state.character_id,
                "moment_id": state.moment_id,
                "take_id": state.take_id,
                "traits": state.traits,
                "voice": state.voice,
                "corpus": [
                    {
                        "id": c.id,
                        "content": c.content,
                        "source": c.source,
                        "section": c.section,
                        "category": c.category,
                        "version": c.version,
                        "metadata": c.metadata,
                    }
                    for c in state.corpus
                ],
                "facts": [
                    {
                        "id": f.id,
                        "content": f.content,
                        "category": f.category,
                        "source": f.source,
                        "moment_id": f.moment_id,
                    }
                    for f in state.facts
                ],
                "memories": [
                    {
                        "id": m.id,
                        "chunk": m.chunk,
                        "chunk_type": m.chunk_type,
                        "tags": m.tags,
                        "moment_id": m.moment_id,
                    }
                    for m in state.memories
                ],
            }
            return [
                TextContent(
                    type="text", text=json.dumps(result, indent=2)
                )
            ]

        elif name == "get_ancestry":
            result = engine.get_ancestry(arguments["take_id"])
            return [
                TextContent(
                    type="text", text=json.dumps(result)
                )
            ]

        # Get operations
        elif name == "get_fact":
            result = engine.get_fact(arguments["fact_id"])
            if result is None:
                return [TextContent(type="text", text=f"Fact not found: {arguments['fact_id']}")]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_facts":
            result = engine.get_facts(arguments["fact_ids"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_memory":
            result = engine.get_memory(arguments["memory_id"])
            if result is None:
                return [TextContent(type="text", text=f"Memory not found: {arguments['memory_id']}")]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_memories":
            result = engine.get_memories(arguments["memory_ids"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # List operations
        elif name == "list_characters":
            result = engine.list_characters()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_facts":
            result = engine.list_facts(
                category=arguments.get("category"),
                moment_id=arguments.get("moment_id"),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_moments":
            result = engine.list_moments()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_memories":
            result = engine.list_memories(
                character_id=arguments["character_id"],
                include_archived=arguments.get("include_archived", False),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Update operations
        elif name == "update_character":
            success = engine.update_character(
                id=arguments["id"],
                name=arguments.get("name"),
                traits=arguments.get("traits"),
                voice=arguments.get("voice"),
            )
            if success:
                return [TextContent(type="text", text=f"Updated character: {arguments['id']}")]
            return [TextContent(type="text", text=f"Character not found: {arguments['id']}")]

        elif name == "update_fact":
            success = engine.update_fact(
                fact_id=arguments["fact_id"],
                content=arguments.get("content"),
                category=arguments.get("category"),
            )
            if success:
                return [TextContent(type="text", text=f"Updated fact: {arguments['fact_id']}")]
            return [TextContent(type="text", text=f"Fact not found: {arguments['fact_id']}")]

        elif name == "update_moment":
            success = engine.update_moment(
                id=arguments["id"],
                sequence=arguments.get("sequence"),
                label=arguments.get("label"),
                metadata=arguments.get("metadata"),
            )
            if success:
                return [TextContent(type="text", text=f"Updated moment: {arguments['id']}")]
            return [TextContent(type="text", text=f"Moment not found: {arguments['id']}")]

        # Delete operations
        elif name == "delete_character":
            success = engine.delete_character(arguments["character_id"])
            if success:
                return [TextContent(type="text", text=f"Deleted character: {arguments['character_id']}")]
            return [TextContent(type="text", text=f"Character not found: {arguments['character_id']}")]

        elif name == "delete_fact":
            success = engine.delete_fact(arguments["fact_id"])
            if success:
                return [TextContent(type="text", text=f"Deleted fact: {arguments['fact_id']}")]
            return [TextContent(type="text", text=f"Fact not found: {arguments['fact_id']}")]

        elif name == "delete_moment":
            success = engine.delete_moment(arguments["moment_id"])
            if success:
                return [TextContent(type="text", text=f"Deleted moment: {arguments['moment_id']}")]
            return [TextContent(type="text", text=f"Moment not found: {arguments['moment_id']}")]

        elif name == "delete_memory":
            success = engine.delete_memory(arguments["memory_id"])
            if success:
                return [TextContent(type="text", text=f"Deleted memory: {arguments['memory_id']}")]
            return [TextContent(type="text", text=f"Memory not found: {arguments['memory_id']}")]

        elif name == "archive_memory":
            success = engine.archive_memory(
                memory_id=arguments["memory_id"],
                superseded_by=arguments.get("superseded_by"),
            )
            if success:
                return [TextContent(type="text", text=f"Archived memory: {arguments['memory_id']}")]
            return [TextContent(type="text", text=f"Memory not found: {arguments['memory_id']}")]

        # Batch operations
        elif name == "log_facts_batch":
            ids = engine.log_facts_batch(arguments["facts"])
            return [TextContent(type="text", text=f"Created {len(ids)} facts: {json.dumps(ids)}")]

        elif name == "log_knowledge_batch":
            ids = engine.log_knowledge_batch(arguments["events"])
            return [TextContent(type="text", text=f"Created {len(ids)} knowledge events: {json.dumps(ids)}")]

        elif name == "embed_memory_batch":
            ids = engine.embed_memory_batch(arguments["memories"])
            return [TextContent(type="text", text=f"Created {len(ids)} memories: {json.dumps(ids)}")]

        # Corpus operations
        elif name == "load_corpus_chunk":
            result = engine.load_corpus_chunk(
                content=arguments["content"],
                source=arguments["source"],
                section=arguments.get("section"),
                category=arguments.get("category"),
                version=arguments.get("version"),
                metadata=arguments.get("metadata"),
            )
            return [TextContent(type="text", text=f"Loaded corpus chunk: {result}")]

        elif name == "query_corpus":
            chunks = engine.query_corpus(
                query_text=arguments["query_text"],
                category=arguments.get("category"),
                version=arguments.get("version"),
                source=arguments.get("source"),
                limit=arguments.get("limit", 20),
            )
            result = [
                {
                    "id": c.id,
                    "content": c.content,
                    "source": c.source,
                    "section": c.section,
                    "category": c.category,
                    "version": c.version,
                    "metadata": c.metadata,
                }
                for c in chunks
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "load_document":
            ids = engine.load_document(
                filepath=arguments["filepath"],
                source=arguments["source"],
                category=arguments["category"],
                version=arguments.get("version"),
                chunker=arguments.get("chunker"),
                metadata=arguments.get("metadata"),
            )
            return [TextContent(type="text", text=f"Loaded {len(ids)} chunks: {json.dumps(ids)}")]

        elif name == "delete_corpus_version":
            count = engine.delete_corpus_version(
                source=arguments["source"],
                version=arguments["version"],
            )
            return [TextContent(type="text", text=f"Deleted {count} corpus chunks")]

        else:
            return [
                TextContent(
                    type="text", text=f"Unknown tool: {name}"
                )
            ]

    except Exception as e:
        return [
            TextContent(
                type="text", text=f"Error: {str(e)}"
            )
        ]


# -------------------------------------------------------------------------
# Main Entry Point
# -------------------------------------------------------------------------


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
