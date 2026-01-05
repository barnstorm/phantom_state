"""SQL query builders for Phantom State."""


def build_ancestry_cte(take_id: int) -> str:
    """Build recursive CTE for take ancestry."""
    return f"""
    WITH RECURSIVE ancestry(id) AS (
        SELECT {take_id}
        UNION ALL
        SELECT t.parent_take_id
        FROM takes t
        JOIN ancestry a ON t.id = a.id
        WHERE t.parent_take_id IS NOT NULL
    )
    SELECT id FROM ancestry
    """


def build_facts_query() -> str:
    """Build query for character facts at a moment."""
    return """
    WITH RECURSIVE ancestry(id) AS (
        SELECT :take_id
        UNION ALL
        SELECT t.parent_take_id
        FROM takes t
        JOIN ancestry a ON t.id = a.id
        WHERE t.parent_take_id IS NOT NULL
    )
    SELECT f.id, f.content, f.category, ke.source, ke.moment_id
    FROM facts f
    JOIN knowledge_events ke ON f.id = ke.fact_id
    JOIN moments m ON ke.moment_id = m.id
    WHERE ke.character_id = :character_id
      AND ke.take_id IN (SELECT id FROM ancestry)
      AND m.sequence <= (SELECT sequence FROM moments WHERE id = :moment_id)
    ORDER BY m.sequence
    LIMIT :limit
    """


def build_memory_query_chronological() -> str:
    """Build query for character memories in chronological order."""
    return """
    WITH RECURSIVE ancestry(id) AS (
        SELECT :take_id
        UNION ALL
        SELECT t.parent_take_id
        FROM takes t
        JOIN ancestry a ON t.id = a.id
        WHERE t.parent_take_id IS NOT NULL
    )
    SELECT mm.id, mm.chunk, mm.chunk_type, mm.tags, mm.moment_id
    FROM memory_metadata mm
    JOIN moments mo ON mm.moment_id = mo.id
    WHERE mm.character_id = :character_id
      AND mm.take_id IN (SELECT id FROM ancestry)
      AND mo.sequence <= (SELECT sequence FROM moments WHERE id = :moment_id)
    ORDER BY mo.sequence
    LIMIT :limit
    """


def build_memory_query_similarity(character_id: str) -> str:
    """Build query for character memories with vector similarity.

    Uses sqlite-vec virtual table for KNN search.
    """
    # Sanitize character_id for table name
    safe_id = sanitize_table_name(character_id)
    return f"""
    WITH RECURSIVE ancestry(id) AS (
        SELECT :take_id
        UNION ALL
        SELECT t.parent_take_id
        FROM takes t
        JOIN ancestry a ON t.id = a.id
        WHERE t.parent_take_id IS NOT NULL
    )
    SELECT mm.id, mm.chunk, mm.chunk_type, mm.tags, mm.moment_id, mv.distance
    FROM {safe_id}_vec mv
    JOIN memory_metadata mm ON mv.rowid = mm.id
    JOIN moments mo ON mm.moment_id = mo.id
    WHERE mv.embedding MATCH :query_vector
      AND k = :limit
      AND mm.character_id = :character_id
      AND mm.take_id IN (SELECT id FROM ancestry)
      AND mo.sequence <= (SELECT sequence FROM moments WHERE id = :moment_id)
    ORDER BY mv.distance
    """


def sanitize_table_name(name: str) -> str:
    """Sanitize a string for use as a table name.

    Only allows alphanumeric characters and underscores.
    """
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


def build_vec_table_ddl(character_id: str, dimensions: int) -> str:
    """Build DDL for creating a character's vector table."""
    safe_id = sanitize_table_name(character_id)
    return f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS {safe_id}_vec
    USING vec0(embedding float[{dimensions}])
    """
