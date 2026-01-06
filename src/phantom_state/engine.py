"""Narrative State Engine - Core implementation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from phantom_state.models import (
    EngineConfig,
    Fact,
    Memory,
    CorpusChunk,
    CharacterState,
    Take,
)
from phantom_state.embedding import (
    EmbeddingBackend,
    LocalEmbedding,
    OpenAIEmbedding,
    HashEmbedding,
    serialize_vector,
)
from phantom_state.queries import (
    build_facts_query,
    build_memory_query_chronological,
    build_memory_query_similarity,
    build_vec_table_ddl,
    build_corpus_vec_ddl,
    build_corpus_query_chronological,
    build_corpus_query_filtered_similarity,
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

        # Create corpus vector table
        corpus_vec_ddl = build_corpus_vec_ddl(self.config.vector_dimensions)
        self.db.execute(corpus_vec_ddl)

        self.db.commit()

    def _init_embedding_backend(self) -> None:
        """Initialize the embedding backend."""
        if self.config.embedding_backend == "openai":
            self._embedding: EmbeddingBackend = OpenAIEmbedding(
                model=self.config.openai_model
            )
        elif self.config.embedding_backend == "hash":
            self._embedding = HashEmbedding(dimensions=self.config.vector_dimensions)
        else:
            self._embedding = LocalEmbedding(model_name=self.config.embedding_model)

        if self._embedding.dimensions != self.config.vector_dimensions:
            raise ValueError(
                "Embedding dimensions mismatch: "
                f"backend={self._embedding.dimensions} config={self.config.vector_dimensions}"
            )

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
        sequence: float | int,
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

    def list_characters(self) -> list[dict]:
        """List all registered characters.

        Returns:
            List of character dicts with id, name, traits, voice
        """
        rows = self.db.execute("SELECT * FROM characters").fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "traits": json.loads(row["traits"]) if row["traits"] else {},
                "voice": json.loads(row["voice"]) if row["voice"] else {},
            }
            for row in rows
        ]

    def update_character(
        self,
        id: str,
        name: str | None = None,
        traits: dict | None = None,
        voice: dict | None = None,
    ) -> bool:
        """Update an existing character.

        Args:
            id: Character ID to update
            name: New display name (None to keep existing)
            traits: New traits (None to keep existing)
            voice: New voice (None to keep existing)

        Returns:
            True if updated, False if character not found
        """
        existing = self.get_character(id)
        if existing is None:
            return False

        new_name = name if name is not None else existing["name"]
        new_traits = traits if traits is not None else existing["traits"]
        new_voice = voice if voice is not None else existing["voice"]

        self.db.execute(
            """
            UPDATE characters SET name = ?, traits = ?, voice = ?
            WHERE id = ?
            """,
            (
                new_name,
                json.dumps(new_traits) if new_traits else None,
                json.dumps(new_voice) if new_voice else None,
                id,
            ),
        )
        self.db.commit()
        return True

    def delete_character(self, character_id: str) -> bool:
        """Delete a character and their memories.

        WARNING: This also deletes all memories for this character.

        Args:
            character_id: Character to delete

        Returns:
            True if deleted, False if not found
        """
        existing = self.get_character(character_id)
        if existing is None:
            return False

        # Delete from knowledge_events
        self.db.execute(
            "DELETE FROM knowledge_events WHERE character_id = ?",
            (character_id,),
        )

        # Delete from memory_metadata
        self.db.execute(
            "DELETE FROM memory_metadata WHERE character_id = ?",
            (character_id,),
        )

        # Drop vector table
        safe_id = sanitize_table_name(character_id)
        self.db.execute(f"DROP TABLE IF EXISTS {safe_id}_vec")

        # Delete character
        self.db.execute("DELETE FROM characters WHERE id = ?", (character_id,))

        self.db.commit()
        return True

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

    def get_fact(self, fact_id: int) -> dict | None:
        """Get a specific fact by ID.

        Returns:
            Fact dict or None if not found
        """
        row = self.db.execute(
            "SELECT * FROM facts WHERE id = ?", (fact_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "content": row["content"],
            "category": row["category"],
            "moment_id": row["created_at"],
        }

    def get_facts(self, fact_ids: list[int]) -> list[dict]:
        """Get multiple facts by ID.

        Returns:
            List of fact dicts (missing IDs are skipped)
        """
        if not fact_ids:
            return []
        placeholders = ",".join("?" * len(fact_ids))
        rows = self.db.execute(
            f"SELECT * FROM facts WHERE id IN ({placeholders})",
            fact_ids,
        ).fetchall()
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "category": row["category"],
                "moment_id": row["created_at"],
            }
            for row in rows
        ]

    def list_facts(
        self,
        category: str | None = None,
        moment_id: str | None = None,
    ) -> list[dict]:
        """List all facts, optionally filtered.

        Args:
            category: Filter by category
            moment_id: Filter by creation moment

        Returns:
            List of fact dicts
        """
        query = "SELECT * FROM facts WHERE 1=1"
        params = []

        if category is not None:
            query += " AND category = ?"
            params.append(category)

        if moment_id is not None:
            query += " AND created_at = ?"
            params.append(moment_id)

        query += " ORDER BY id"

        rows = self.db.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "category": row["category"],
                "moment_id": row["created_at"],
            }
            for row in rows
        ]

    def update_fact(
        self,
        fact_id: int,
        content: str | None = None,
        category: str | None = None,
    ) -> bool:
        """Update an existing fact.

        Args:
            fact_id: Fact ID to update
            content: New content (None to keep existing)
            category: New category (None to keep existing)

        Returns:
            True if updated, False if not found
        """
        row = self.db.execute(
            "SELECT * FROM facts WHERE id = ?", (fact_id,)
        ).fetchone()
        if row is None:
            return False

        new_content = content if content is not None else row["content"]
        new_category = category if category is not None else row["category"]

        self.db.execute(
            "UPDATE facts SET content = ?, category = ? WHERE id = ?",
            (new_content, new_category, fact_id),
        )
        self.db.commit()
        return True

    def delete_fact(self, fact_id: int) -> bool:
        """Delete a fact and associated knowledge events.

        Args:
            fact_id: Fact to delete

        Returns:
            True if deleted, False if not found
        """
        row = self.db.execute(
            "SELECT id FROM facts WHERE id = ?", (fact_id,)
        ).fetchone()
        if row is None:
            return False

        # Delete knowledge events referencing this fact
        self.db.execute(
            "DELETE FROM knowledge_events WHERE fact_id = ?", (fact_id,)
        )

        # Delete the fact
        self.db.execute("DELETE FROM facts WHERE id = ?", (fact_id,))

        self.db.commit()
        return True

    def list_moments(self) -> list[dict]:
        """List all moments in sequence order.

        Returns:
            List of moment dicts with id, sequence, label, metadata
        """
        rows = self.db.execute(
            "SELECT * FROM moments ORDER BY sequence"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "sequence": row["sequence"],
                "label": row["label"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }
            for row in rows
        ]

    def update_moment(
        self,
        id: str,
        sequence: float | int | None = None,
        label: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Update an existing moment.

        Args:
            id: Moment ID to update
            sequence: New sequence (None to keep existing)
            label: New label (None to keep existing)
            metadata: New metadata (None to keep existing)

        Returns:
            True if updated, False if not found
        """
        row = self.db.execute(
            "SELECT * FROM moments WHERE id = ?", (id,)
        ).fetchone()
        if row is None:
            return False

        new_sequence = sequence if sequence is not None else row["sequence"]
        new_label = label if label is not None else row["label"]
        new_metadata = metadata if metadata is not None else (
            json.loads(row["metadata"]) if row["metadata"] else None
        )

        self.db.execute(
            "UPDATE moments SET sequence = ?, label = ?, metadata = ? WHERE id = ?",
            (
                new_sequence,
                new_label,
                json.dumps(new_metadata) if new_metadata else None,
                id,
            ),
        )
        self.db.commit()
        return True

    def delete_moment(self, moment_id: str) -> bool:
        """Delete a moment.

        WARNING: This may orphan facts, knowledge events, and memories
        that reference this moment.

        Args:
            moment_id: Moment to delete

        Returns:
            True if deleted, False if not found
        """
        row = self.db.execute(
            "SELECT id FROM moments WHERE id = ?", (moment_id,)
        ).fetchone()
        if row is None:
            return False

        self.db.execute("DELETE FROM moments WHERE id = ?", (moment_id,))
        self.db.commit()
        return True

    def log_facts_batch(
        self,
        facts: list[dict],
    ) -> list[int]:
        """Log multiple facts at once.

        Args:
            facts: List of dicts with 'content', 'category', 'moment_id'

        Returns:
            List of fact IDs created
        """
        ids = []
        for fact in facts:
            cursor = self.db.execute(
                """
                INSERT INTO facts (content, category, created_at)
                VALUES (?, ?, ?)
                """,
                (fact["content"], fact["category"], fact["moment_id"]),
            )
            ids.append(cursor.lastrowid)
        self.db.commit()
        return ids

    def log_knowledge_batch(
        self,
        events: list[dict],
    ) -> list[int]:
        """Log multiple knowledge events at once.

        Args:
            events: List of dicts with 'character_id', 'fact_id', 'moment_id',
                    'take_id', and optional 'source'

        Returns:
            List of knowledge_event IDs created
        """
        ids = []
        for event in events:
            cursor = self.db.execute(
                """
                INSERT INTO knowledge_events (character_id, fact_id, moment_id, take_id, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event["character_id"],
                    event["fact_id"],
                    event["moment_id"],
                    event["take_id"],
                    event.get("source"),
                ),
            )
            ids.append(cursor.lastrowid)
        self.db.commit()
        return ids

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

    def embed_memory_batch(
        self,
        memories: list[dict],
    ) -> list[int]:
        """Embed multiple memories at once.

        Args:
            memories: List of dicts with 'character_id', 'chunk', 'moment_id',
                      'take_id', 'chunk_type', and optional 'tags'

        Returns:
            List of memory IDs created
        """
        ids = []
        for mem in memories:
            memory_id = self.embed_memory(
                character_id=mem["character_id"],
                chunk=mem["chunk"],
                moment_id=mem["moment_id"],
                take_id=mem["take_id"],
                chunk_type=mem["chunk_type"],
                tags=mem.get("tags"),
            )
            ids.append(memory_id)
        return ids

    def archive_memory(
        self,
        memory_id: int,
        superseded_by: int | None = None,
    ) -> bool:
        """Mark a memory as archived/superseded.

        Sets 'archived': true and optionally 'superseded_by' in tags.
        The memory remains in the database but can be filtered out.

        Args:
            memory_id: Memory to archive
            superseded_by: ID of the memory that replaces this one

        Returns:
            True if archived, False if not found
        """
        row = self.db.execute(
            "SELECT tags FROM memory_metadata WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False

        tags = json.loads(row["tags"]) if row["tags"] else {}
        tags["archived"] = True
        if superseded_by is not None:
            tags["superseded_by"] = superseded_by

        self.db.execute(
            "UPDATE memory_metadata SET tags = ? WHERE id = ?",
            (json.dumps(tags), memory_id),
        )
        self.db.commit()
        return True

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory completely.

        Args:
            memory_id: Memory to delete

        Returns:
            True if deleted, False if not found
        """
        row = self.db.execute(
            "SELECT character_id FROM memory_metadata WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False

        character_id = row["character_id"]
        safe_id = sanitize_table_name(character_id)

        # Delete from vector table
        self.db.execute(f"DELETE FROM {safe_id}_vec WHERE rowid = ?", (memory_id,))

        # Delete from metadata
        self.db.execute("DELETE FROM memory_metadata WHERE id = ?", (memory_id,))

        self.db.commit()
        return True

    def get_memory(self, memory_id: int) -> dict | None:
        """Get a specific memory by ID.

        Returns:
            Memory dict or None if not found
        """
        row = self.db.execute(
            "SELECT * FROM memory_metadata WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "character_id": row["character_id"],
            "chunk": row["chunk"],
            "moment_id": row["moment_id"],
            "take_id": row["take_id"],
            "chunk_type": row["chunk_type"],
            "tags": json.loads(row["tags"]) if row["tags"] else {},
        }

    def get_memories(self, memory_ids: list[int]) -> list[dict]:
        """Get multiple memories by ID.

        Returns:
            List of memory dicts (missing IDs are skipped)
        """
        if not memory_ids:
            return []
        placeholders = ",".join("?" * len(memory_ids))
        rows = self.db.execute(
            f"SELECT * FROM memory_metadata WHERE id IN ({placeholders})",
            memory_ids,
        ).fetchall()
        return [
            {
                "id": row["id"],
                "character_id": row["character_id"],
                "chunk": row["chunk"],
                "moment_id": row["moment_id"],
                "take_id": row["take_id"],
                "chunk_type": row["chunk_type"],
                "tags": json.loads(row["tags"]) if row["tags"] else {},
            }
            for row in rows
        ]

    def list_memories(
        self,
        character_id: str,
        include_archived: bool = False,
    ) -> list[dict]:
        """List all memories for a character.

        Args:
            character_id: Character whose memories to list
            include_archived: Whether to include archived memories

        Returns:
            List of memory dicts
        """
        query = """
            SELECT id, chunk, moment_id, take_id, chunk_type, tags
            FROM memory_metadata
            WHERE character_id = ?
        """
        params = [character_id]

        if not include_archived:
            query += " AND (tags IS NULL OR json_extract(tags, '$.archived') IS NOT TRUE)"

        query += " ORDER BY id"

        rows = self.db.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "chunk": row["chunk"],
                "moment_id": row["moment_id"],
                "take_id": row["take_id"],
                "chunk_type": row["chunk_type"],
                "tags": json.loads(row["tags"]) if row["tags"] else {},
            }
            for row in rows
        ]

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
    # Corpus Operations
    # -------------------------------------------------------------------------

    def load_corpus_chunk(
        self,
        content: str,
        source: str,
        section: str | None = None,
        category: str | None = None,
        version: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Load a single chunk into shared corpus.

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
        cursor = self.db.execute(
            """
            INSERT INTO corpus (content, source, section, category, version, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                content,
                source,
                section,
                category,
                version,
                json.dumps(metadata) if metadata else None,
            ),
        )
        corpus_id = cursor.lastrowid

        # Generate embedding and insert into vector table
        embedding = self._embedding.embed(content)
        self.db.execute(
            "INSERT INTO corpus_vec (rowid, embedding) VALUES (?, ?)",
            (corpus_id, serialize_vector(embedding)),
        )

        self.db.commit()
        return corpus_id

    def load_document(
        self,
        filepath: str,
        source: str,
        category: str,
        version: str | None = None,
        chunker: str | None = None,
        metadata: dict | None = None,
    ) -> list[int]:
        """Load and vectorize a document into corpus.

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
        # Read file content
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {filepath}")

        content = path.read_text(encoding="utf-8")

        # Determine chunk granularity
        granularity = chunker or self.config.chunk_granularity

        # Split into chunks
        chunks = self._chunk_text(content, granularity)

        # Load each chunk
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            chunk_id = self.load_corpus_chunk(
                content=chunk,
                source=source,
                section=f"chunk_{i}",
                category=category,
                version=version,
                metadata=metadata,
            )
            chunk_ids.append(chunk_id)

        return chunk_ids

    def _chunk_text(self, text: str, granularity: str) -> list[str]:
        """Split text into chunks based on granularity.

        Args:
            text: The text to chunk
            granularity: 'sentence', 'paragraph', 'page', or 'manual'

        Returns:
            List of text chunks
        """
        if granularity == "sentence":
            # Simple sentence splitting (not perfect but functional)
            import re
            sentences = re.split(r'(?<=[.!?])\s+', text)
            return [s.strip() for s in sentences if s.strip()]
        elif granularity == "paragraph":
            # Split on double newlines
            paragraphs = text.split("\n\n")
            return [p.strip() for p in paragraphs if p.strip()]
        elif granularity == "page":
            # Split on form feed or ~3000 chars
            if "\f" in text:
                pages = text.split("\f")
            else:
                # Approximate page by character count
                pages = []
                for i in range(0, len(text), 3000):
                    pages.append(text[i:i+3000])
            return [p.strip() for p in pages if p.strip()]
        else:  # manual or unknown - return as single chunk
            return [text]

    def query_corpus(
        self,
        query_text: str,
        category: str | None = None,
        version: str | None = None,
        source: str | None = None,
        limit: int = 20,
    ) -> list[CorpusChunk]:
        """Query corpus by vector similarity with optional filters.

        Args:
            query_text: Text to find similar chunks for
            category: Filter by category
            version: Filter by version
            source: Filter by source document
            limit: Max chunks to return

        Returns:
            List of CorpusChunk ordered by similarity
        """
        query_embedding = self._embedding.embed(query_text)

        rows = self.db.execute(
            build_corpus_query_filtered_similarity(),
            {
                "query_vector": serialize_vector(query_embedding),
                "limit": limit,
                "category": category,
                "version": version,
                "source": source,
            },
        ).fetchall()

        return [
            CorpusChunk(
                id=row["id"],
                content=row["content"],
                source=row["source"],
                section=row["section"],
                category=row["category"],
                version=row["version"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    def delete_corpus_version(
        self,
        source: str,
        version: str,
    ) -> int:
        """Delete all corpus chunks for a source/version.

        Use when replacing a document version.

        Returns:
            Number of chunks deleted
        """
        # Get IDs to delete from vector table
        rows = self.db.execute(
            "SELECT id FROM corpus WHERE source = ? AND version = ?",
            (source, version),
        ).fetchall()

        if not rows:
            return 0

        ids = [row["id"] for row in rows]

        # Delete from vector table
        for id_ in ids:
            self.db.execute("DELETE FROM corpus_vec WHERE rowid = ?", (id_,))

        # Delete from corpus table
        cursor = self.db.execute(
            "DELETE FROM corpus WHERE source = ? AND version = ?",
            (source, version),
        )

        self.db.commit()
        return cursor.rowcount

    def _query_corpus_chronological(
        self,
        category: str | None = None,
        version: str | None = None,
        source: str | None = None,
        limit: int = 20,
    ) -> list[CorpusChunk]:
        """Query corpus in chronological order (most recent first)."""
        rows = self.db.execute(
            build_corpus_query_chronological(),
            {
                "category": category,
                "version": version,
                "source": source,
                "limit": limit,
            },
        ).fetchall()

        return [
            CorpusChunk(
                id=row["id"],
                content=row["content"],
                source=row["source"],
                section=row["section"],
                category=row["category"],
                version=row["version"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

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
        include_corpus: bool = True,
        corpus_limit: int = 20,
        corpus_category: str | None = None,
        corpus_version: str | None = None,
    ) -> CharacterState:
        """Get everything a character knows/has experienced up to moment.

        Three retrieval tiers:
        1. Corpus (shared, ungated) — foundational reference material
        2. Facts (character + temporal gated) — learned discrete knowledge
        3. Memories (character + temporal + take gated) — experiential chunks

        Args:
            character_id: Which character
            moment_id: Up to which moment
            take_id: In which take lineage
            query_text: If provided, all tiers use vector similarity
            fact_limit: Max facts to return
            memory_limit: Max memories to return
            include_corpus: Whether to include corpus in results
            corpus_limit: Max corpus chunks to return
            corpus_category: Filter corpus by category
            corpus_version: Filter corpus by version

        Returns:
            CharacterState with facts, memories, corpus, traits, and voice
        """
        # Get character info
        char_data = self.get_character(character_id)
        if char_data is None:
            raise ValueError(f"Character not found: {character_id}")

        # Get corpus (ungated, shared reference material)
        corpus: list[CorpusChunk] = []
        if include_corpus:
            if query_text:
                corpus = self.query_corpus(
                    query_text=query_text,
                    category=corpus_category,
                    version=corpus_version,
                    limit=corpus_limit,
                )
            else:
                corpus = self._query_corpus_chronological(
                    category=corpus_category,
                    version=corpus_version,
                    limit=corpus_limit,
                )

        # Get facts (character + temporal gated)
        facts = self._query_facts(character_id, moment_id, take_id, fact_limit)

        # Get memories (character + temporal + take gated)
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
            corpus=corpus,
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
