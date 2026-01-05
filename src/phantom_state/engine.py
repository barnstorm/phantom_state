"""Narrative State Engine - Core implementation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from phantom_state.models import (
    EngineConfig,
    Fact,
    Memory,
    CharacterState,
    Take,
)
from phantom_state.embedding import (
    EmbeddingBackend,
    LocalEmbedding,
    OpenAIEmbedding,
    serialize_vector,
)
from phantom_state.queries import (
    build_facts_query,
    build_memory_query_chronological,
    build_memory_query_similarity,
    build_vec_table_ddl,
    sanitize_table_name,
)


class NarrativeStateEngine:
    """Engine for managing narrative state with bounded character knowledge."""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.db = sqlite3.connect(config.db_path)
        self.db.row_factory = sqlite3.Row
        self._load_sqlite_vec()
        self._init_schema()
        self._init_embedding_backend()

    def _load_sqlite_vec(self) -> None:
        """Load the sqlite-vec extension."""
        import sqlite_vec

        # Enable extension loading (disabled by default for security)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)

    def _init_schema(self) -> None:
        """Initialize database schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            schema = f.read()
        self.db.executescript(schema)
        self.db.commit()

    def _init_embedding_backend(self) -> None:
        """Initialize the embedding backend."""
        if self.config.embedding_backend == "openai":
            self._embedding: EmbeddingBackend = OpenAIEmbedding(
                model=self.config.openai_model
            )
        else:
            self._embedding = LocalEmbedding(model_name=self.config.embedding_model)

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def __enter__(self) -> NarrativeStateEngine:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # Moment Operations
    # -------------------------------------------------------------------------

    def create_moment(
        self,
        id: str,
        sequence: int,
        label: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Create a temporal marker.

        Args:
            id: Unique identifier for the moment
            sequence: Ordering number (must be unique)
            label: Human-readable label
            metadata: Additional JSON metadata

        Returns:
            The moment id
        """
        self.db.execute(
            """
            INSERT INTO moments (id, sequence, label, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (id, sequence, label, json.dumps(metadata) if metadata else None),
        )
        self.db.commit()
        return id

    def get_moment_sequence(self, moment_id: str) -> int:
        """Get the sequence number for a moment."""
        row = self.db.execute(
            "SELECT sequence FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Moment not found: {moment_id}")
        return row["sequence"]

    # -------------------------------------------------------------------------
    # Take Operations
    # -------------------------------------------------------------------------

    def create_take(
        self,
        parent_take_id: int | None = None,
        branch_point: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Create a new take (branch).

        Args:
            parent_take_id: ID of parent take (None for root)
            branch_point: Moment ID where branch occurs
            notes: Human-readable notes

        Returns:
            The new take id
        """
        cursor = self.db.execute(
            """
            INSERT INTO takes (parent_take_id, branch_point, notes)
            VALUES (?, ?, ?)
            """,
            (parent_take_id, branch_point, notes),
        )
        self.db.commit()
        return cursor.lastrowid

    def branch(
        self,
        parent_take_id: int,
        branch_point: str,
        notes: str | None = None,
    ) -> int:
        """Create a new take branching from parent at branch_point.

        Args:
            parent_take_id: ID of parent take
            branch_point: Moment ID where branch occurs
            notes: Human-readable notes

        Returns:
            The new take id
        """
        return self.create_take(parent_take_id, branch_point, notes)

    def list_takes(
        self,
        status: str | None = None,
        moment_id: str | None = None,
    ) -> list[Take]:
        """List takes, optionally filtered.

        Args:
            status: Filter by status ('active', 'archived', 'trunk')
            moment_id: Filter by branch point

        Returns:
            List of Take objects
        """
        query = "SELECT * FROM takes WHERE 1=1"
        params = []

        if status is not None:
            query += " AND status = ?"
            params.append(status)

        if moment_id is not None:
            query += " AND branch_point = ?"
            params.append(moment_id)

        rows = self.db.execute(query, params).fetchall()
        return [
            Take(
                id=row["id"],
                parent_take_id=row["parent_take_id"],
                branch_point=row["branch_point"],
                created_at=row["created_at"],
                status=row["status"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def set_take_status(self, take_id: int, status: str) -> None:
        """Update take status.

        Args:
            take_id: ID of take to update
            status: New status ('active', 'archived', 'trunk')
        """
        if status not in ("active", "archived", "trunk"):
            raise ValueError(f"Invalid status: {status}")

        self.db.execute(
            "UPDATE takes SET status = ? WHERE id = ?",
            (status, take_id),
        )
        self.db.commit()

    def get_ancestry(self, take_id: int) -> list[int]:
        """Get full lineage of take ids from root to given take.

        Args:
            take_id: ID of take

        Returns:
            List of take IDs in ancestry (including the given take)
        """
        rows = self.db.execute(
            """
            WITH RECURSIVE ancestry(id) AS (
                SELECT ?
                UNION ALL
                SELECT t.parent_take_id
                FROM takes t
                JOIN ancestry a ON t.id = a.id
                WHERE t.parent_take_id IS NOT NULL
            )
            SELECT id FROM ancestry
            """,
            (take_id,),
        ).fetchall()
        return [row["id"] for row in rows]

    # -------------------------------------------------------------------------
    # Character Operations
    # -------------------------------------------------------------------------

    def register_character(
        self,
        id: str,
        name: str,
        traits: dict | None = None,
        voice: dict | None = None,
    ) -> str:
        """Register a character and create their memory table.

        Args:
            id: Unique identifier for the character
            name: Display name
            traits: JSON personality constraints
            voice: JSON speech patterns/markers

        Returns:
            The character id
        """
        self.db.execute(
            """
            INSERT INTO characters (id, name, traits, voice)
            VALUES (?, ?, ?, ?)
            """,
            (
                id,
                name,
                json.dumps(traits) if traits else None,
                json.dumps(voice) if voice else None,
            ),
        )

        # Create vector table for character's experiential memories
        vec_ddl = build_vec_table_ddl(id, self.config.vector_dimensions)
        self.db.execute(vec_ddl)

        self.db.commit()
        return id

    def get_character(self, character_id: str) -> dict | None:
        """Get character data."""
        row = self.db.execute(
            "SELECT * FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "traits": json.loads(row["traits"]) if row["traits"] else {},
            "voice": json.loads(row["voice"]) if row["voice"] else {},
        }

    # -------------------------------------------------------------------------
    # Fact Operations
    # -------------------------------------------------------------------------

    def log_fact(
        self,
        content: str,
        category: str,
        moment_id: str,
    ) -> int:
        """Record a fact in the world.

        Args:
            content: The fact text
            category: Category label
            moment_id: When the fact was established

        Returns:
            The fact id
        """
        cursor = self.db.execute(
            """
            INSERT INTO facts (content, category, created_at)
            VALUES (?, ?, ?)
            """,
            (content, category, moment_id),
        )
        self.db.commit()
        return cursor.lastrowid

    def log_knowledge(
        self,
        character_id: str,
        fact_id: int,
        moment_id: str,
        take_id: int,
        source: str | None = None,
    ) -> int:
        """Record that a character learned a fact.

        Args:
            character_id: Who learned the fact
            fact_id: Which fact was learned
            moment_id: When they learned it
            take_id: In which take
            source: How they learned it ('witnessed', 'told', 'inferred', 'discovered')

        Returns:
            The knowledge_event id
        """
        cursor = self.db.execute(
            """
            INSERT INTO knowledge_events (character_id, fact_id, moment_id, take_id, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (character_id, fact_id, moment_id, take_id, source),
        )
        self.db.commit()
        return cursor.lastrowid

    # -------------------------------------------------------------------------
    # Memory Operations
    # -------------------------------------------------------------------------

    def embed_memory(
        self,
        character_id: str,
        chunk: str,
        moment_id: str,
        take_id: int,
        chunk_type: str,
        tags: dict | None = None,
    ) -> int:
        """Embed experiential memory for a character.

        Args:
            character_id: Whose memory this is
            chunk: The text content
            moment_id: When it occurred
            take_id: In which take
            chunk_type: Type ('said', 'heard', 'internal', 'perceived', 'action')
            tags: Additional JSON tags

        Returns:
            The memory id
        """
        # Insert metadata
        cursor = self.db.execute(
            """
            INSERT INTO memory_metadata (character_id, chunk, moment_id, take_id, chunk_type, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                chunk,
                moment_id,
                take_id,
                chunk_type,
                json.dumps(tags) if tags else None,
            ),
        )
        memory_id = cursor.lastrowid

        # Generate embedding and insert into vector table
        embedding = self._embedding.embed(chunk)
        safe_id = sanitize_table_name(character_id)

        self.db.execute(
            f"INSERT INTO {safe_id}_vec (rowid, embedding) VALUES (?, ?)",
            (memory_id, serialize_vector(embedding)),
        )

        self.db.commit()
        return memory_id

    def dialogue(
        self,
        speaker: str,
        content: str,
        moment_id: str,
        take_id: int,
        listeners: list[str] | None = None,
        speaker_tags: dict | None = None,
        listener_tags: dict | None = None,
    ) -> dict:
        """Convenience method for dialogue.

        Embeds to speaker as 'said', to each listener as 'heard'.

        Args:
            speaker: Character ID of speaker
            content: What was said
            moment_id: When it was said
            take_id: In which take
            listeners: List of character IDs who heard it
            speaker_tags: Additional tags for speaker's memory
            listener_tags: Additional tags for listeners' memories

        Returns:
            Dict with speaker_memory_id and listener_memory_ids
        """
        speaker_memory_id = self.embed_memory(
            character_id=speaker,
            chunk=content,
            moment_id=moment_id,
            take_id=take_id,
            chunk_type="said",
            tags=speaker_tags,
        )

        listener_memory_ids = []
        if listeners:
            for listener in listeners:
                mid = self.embed_memory(
                    character_id=listener,
                    chunk=content,
                    moment_id=moment_id,
                    take_id=take_id,
                    chunk_type="heard",
                    tags=listener_tags,
                )
                listener_memory_ids.append(mid)

        return {
            "speaker_memory_id": speaker_memory_id,
            "listener_memory_ids": listener_memory_ids,
        }

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def query_state(
        self,
        character_id: str,
        moment_id: str,
        take_id: int,
        query_text: str | None = None,
        fact_limit: int = 50,
        memory_limit: int = 20,
    ) -> CharacterState:
        """Get everything a character knows/has experienced up to moment.

        Args:
            character_id: Which character
            moment_id: Up to which moment
            take_id: In which take lineage
            query_text: If provided, orders memories by similarity
            fact_limit: Max facts to return
            memory_limit: Max memories to return

        Returns:
            CharacterState with facts, memories, traits, and voice
        """
        # Get character info
        char_data = self.get_character(character_id)
        if char_data is None:
            raise ValueError(f"Character not found: {character_id}")

        # Get facts
        facts = self._query_facts(character_id, moment_id, take_id, fact_limit)

        # Get memories
        if query_text:
            memories = self._query_memories_similarity(
                character_id, moment_id, take_id, query_text, memory_limit
            )
        else:
            memories = self._query_memories_chronological(
                character_id, moment_id, take_id, memory_limit
            )

        return CharacterState(
            character_id=character_id,
            moment_id=moment_id,
            take_id=take_id,
            facts=facts,
            memories=memories,
            traits=char_data["traits"],
            voice=char_data["voice"],
        )

    def _query_facts(
        self,
        character_id: str,
        moment_id: str,
        take_id: int,
        limit: int,
    ) -> list[Fact]:
        """Query facts known by a character at a moment."""
        rows = self.db.execute(
            build_facts_query(),
            {
                "character_id": character_id,
                "moment_id": moment_id,
                "take_id": take_id,
                "limit": limit,
            },
        ).fetchall()

        return [
            Fact(
                id=row["id"],
                content=row["content"],
                category=row["category"],
                source=row["source"],
                moment_id=row["moment_id"],
            )
            for row in rows
        ]

    def _query_memories_chronological(
        self,
        character_id: str,
        moment_id: str,
        take_id: int,
        limit: int,
    ) -> list[Memory]:
        """Query memories in chronological order."""
        rows = self.db.execute(
            build_memory_query_chronological(),
            {
                "character_id": character_id,
                "moment_id": moment_id,
                "take_id": take_id,
                "limit": limit,
            },
        ).fetchall()

        return [
            Memory(
                id=row["id"],
                chunk=row["chunk"],
                chunk_type=row["chunk_type"],
                tags=json.loads(row["tags"]) if row["tags"] else {},
                moment_id=row["moment_id"],
            )
            for row in rows
        ]

    def _query_memories_similarity(
        self,
        character_id: str,
        moment_id: str,
        take_id: int,
        query_text: str,
        limit: int,
    ) -> list[Memory]:
        """Query memories by vector similarity."""
        query_embedding = self._embedding.embed(query_text)

        rows = self.db.execute(
            build_memory_query_similarity(character_id),
            {
                "character_id": character_id,
                "moment_id": moment_id,
                "take_id": take_id,
                "query_vector": serialize_vector(query_embedding),
                "limit": limit,
            },
        ).fetchall()

        return [
            Memory(
                id=row["id"],
                chunk=row["chunk"],
                chunk_type=row["chunk_type"],
                tags=json.loads(row["tags"]) if row["tags"] else {},
                moment_id=row["moment_id"],
            )
            for row in rows
        ]
