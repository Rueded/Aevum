"""Embedding provider abstraction, cosine similarity, and implementations for Aevum Core.

Provides provider-neutral text embedding interfaces, deterministic local FakeEmbeddingProvider
for tests and offline operation, and concrete GeminiEmbeddingProvider using the official google-genai SDK.
"""

from collections.abc import Sequence
import hashlib
import math
import re
from typing import Any, Protocol

from app.core.config import settings
from app.memory.models import EmbeddingResult


class EmbeddingError(Exception):
    """Base exception for embedding provider errors."""


class EmbeddingProviderNotConfiguredError(EmbeddingError):
    """Raised when an embedding provider is invoked without necessary configuration or API keys."""


class EmbeddingGenerationError(EmbeddingError):
    """Raised when an embedding provider fails during vector generation."""


def compute_cosine_similarity(
    vec_a: Sequence[float],
    vec_b: Sequence[float],
) -> float:
    """Compute cosine similarity between two numeric vectors.

    Formula: dot(a, b) / (||a|| * ||b||)

    Requirements:
    - Dimensions must match.
    - Zero vectors return 0.0.
    - NaN and Inf are rejected with ValueError.
    - Result is safely clamped to [-1.0, 1.0].
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector dimension mismatch: len(vec_a)={len(vec_a)} != len(vec_b)={len(vec_b)}"
        )
    if not vec_a:
        raise ValueError("Vectors must not be empty.")

    dot = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0

    for a, b in zip(vec_a, vec_b):
        if math.isnan(a) or math.isnan(b):
            raise ValueError("Vector components must not be NaN.")
        if math.isinf(a) or math.isinf(b):
            raise ValueError("Vector components must not be infinite.")
        dot += a * b
        norm_a_sq += a * a
        norm_b_sq += b * b

    if norm_a_sq == 0.0 or norm_b_sq == 0.0:
        return 0.0

    denom = math.sqrt(norm_a_sq) * math.sqrt(norm_b_sq)
    similarity = dot / denom
    return max(-1.0, min(1.0, float(similarity)))


class EmbeddingProvider(Protocol):
    """Protocol defining the provider-neutral embedding interface."""

    @property
    def provider_name(self) -> str:
        """Name of the embedding provider."""
        ...

    @property
    def model_name(self) -> str:
        """Identifier of the active embedding model."""
        ...

    async def embed_text(self, text: str) -> EmbeddingResult:
        """Generate an embedding vector for the provided text."""
        ...


class FakeEmbeddingProvider:
    """Deterministic, local fake embedding provider for unit tests and offline testing.

    Generates reproducible, normalized vectors by hashing word tokens into fixed-dimension bins.
    Texts sharing tokens yield positive cosine similarity; identical texts yield 1.0;
    disjoint vocabularies yield near-zero or zero similarity.
    """

    def __init__(
        self,
        dimensions: int = 16,
        model_name: str = "fake-embedding-v1",
        provider_name: str = "fake",
    ) -> None:
        if dimensions <= 0:
            raise ValueError("Dimensions must be positive.")
        self._dimensions = dimensions
        self._model_name = model_name
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_text(self, text: str) -> EmbeddingResult:
        """Deterministically map text into a normalized float vector."""
        if not text.strip():
            raise ValueError("Text to embed must not be empty or whitespace.")

        tokens = re.findall(r"(?u)\b\w+\b", text.lower())
        vec = [0.0] * self._dimensions

        if not tokens:
            # Fallback on raw character bytes
            tokens = [c for c in text.lower() if not c.isspace()]

        for token in tokens:
            # Deterministic hash to dimension index
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            dim_idx = h % self._dimensions
            vec[dim_idx] += 1.0


        # Compute L2 norm
        norm_sq = sum(v * v for v in vec)
        if norm_sq > 0.0:
            norm = math.sqrt(norm_sq)
            vec = [v / norm for v in vec]
        else:
            # Unit vector on first dimension if all zeros
            vec[0] = 1.0

        return EmbeddingResult(
            vector=tuple(round(v, 6) for v in vec),
            model=self._model_name,
            dimensions=self._dimensions,
            provider=self._provider_name,
        )


class GeminiEmbeddingProvider:
    """Google Gemini text embedding provider using the official google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model_name_val = model_name or settings.embedding_model or "text-embedding-004"
        self._client = client

        if self._client is None and self.api_key:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self.model_name_val

    async def embed_text(self, text: str) -> EmbeddingResult:
        """Generate text embedding using Google GenAI API."""
        if not text.strip():
            raise ValueError("Text to embed must not be empty or whitespace.")

        if self._client is None:
            raise EmbeddingProviderNotConfiguredError(
                "Gemini embedding client is not configured. GEMINI_API_KEY must be provided."
            )

        try:
            response = await self._client.aio.models.embed_content(
                model=self.model_name_val,
                contents=text,
            )
            if not response.embeddings or not response.embeddings[0].values:
                raise EmbeddingGenerationError("Gemini API returned an empty embedding response.")

            raw_values = tuple(float(v) for v in response.embeddings[0].values)
            return EmbeddingResult(
                vector=raw_values,
                model=self.model_name_val,
                dimensions=len(raw_values),
                provider="gemini",
            )
        except Exception as e:
            if isinstance(e, EmbeddingError):
                raise
            raise EmbeddingGenerationError(f"Gemini embedding request failed: {e}") from e


def get_embedding_provider() -> EmbeddingProvider | None:
    """Dependency provider returning the configured EmbeddingProvider instance, or None if unconfigured.

    Returns:
        EmbeddingProvider instance if configured (e.g. GeminiEmbeddingProvider or FakeEmbeddingProvider),
        or None if no API key or provider is available.
    """
    provider_name = (settings.embedding_provider or "gemini").lower()
    if provider_name == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiEmbeddingProvider()
    elif provider_name == "fake":
        return FakeEmbeddingProvider()
    return None

