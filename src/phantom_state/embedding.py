"""Embedding backend abstraction for Phantom State."""

from typing import Protocol
import json


class EmbeddingBackend(Protocol):
    """Protocol for embedding backends."""

    def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the dimensionality of embeddings."""
        ...


class LocalEmbedding:
    """Local embedding using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self._dimensions = self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return self.model.encode(texts).tolist()

    @property
    def dimensions(self) -> int:
        """Return the dimensionality of embeddings."""
        return self._dimensions


class OpenAIEmbedding:
    """OpenAI API embedding backend."""

    # Known dimensions for OpenAI models
    _MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI

        self.model = model
        self.client = OpenAI()
        self._dimensions = self._MODEL_DIMENSIONS.get(model, 1536)

    def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        response = self.client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in response.data]

    @property
    def dimensions(self) -> int:
        """Return the dimensionality of embeddings."""
        return self._dimensions


def serialize_vector(vec: list[float]) -> str:
    """Serialize a vector to JSON for sqlite-vec."""
    return json.dumps(vec)
