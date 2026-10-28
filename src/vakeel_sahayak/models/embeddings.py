"""Embedding clients (plan §5.5, §12): BGE-M3 when installed, and a deterministic offline fallback.

`Embedder` is the protocol the stores depend on. `HashedEmbeddingClient` needs no model and no extra package, so the
whole system builds and runs on a laptop without torch; its quality is lexical (hashed word and character n-grams), so
BM25 stays the main signal. `Bgem3EmbeddingClient` imports its libraries lazily and is selected by `get_embedder`.
"""

from __future__ import annotations

import importlib.util
import math
import os
import re
import zlib
from collections import Counter
from functools import lru_cache
from typing import Protocol

from vakeel_sahayak.models.base import EmbeddingClient

HASHED_NAME = "hashed-ngram"
BGE_M3_NAME = "bge-m3"
_WORD = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """What the stores need from an embedder: a stable name, a dimension and a batch `embed`."""

    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Unit-length vectors, one per text."""
        ...


class HashedEmbeddingClient(EmbeddingClient):
    """Deterministic hashed n-gram embedder: word unigrams and bigrams plus character trigrams, signed feature hashing.

    The same text always gives the same vector on every machine (CRC32, no random state). Vectors are L2-normalised, so
    the dot product is cosine similarity.
    """

    name = HASHED_NAME

    def __init__(self, dim: int = 384) -> None:
        """Create the embedder.

        Args:
            dim: vector length (feature buckets)
        """
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed.

        Args:
            texts: see behaviour

        Returns:
            Unit-length vectors (all zeros for a text with no word characters).
        """
        return [self._one(t) for t in texts]

    def _features(self, text: str) -> Counter[str]:
        """Feature counts of one text."""
        words = _WORD.findall(text.lower())
        feats: Counter[str] = Counter(f"w:{w}" for w in words)
        feats.update(f"b:{a}_{b}" for a, b in zip(words, words[1:], strict=False))
        for w in words:
            padded = f"^{w}$"
            feats.update(f"c:{padded[i : i + 3]}" for i in range(len(padded) - 2))
        return feats

    def _one(self, text: str) -> list[float]:
        """Hash features into `dim` signed buckets with sublinear term frequency, then normalise."""
        vec = [0.0] * self.dim
        for feat, count in self._features(text).items():
            h = zlib.crc32(feat.encode("utf-8"))
            weight = (1.0 + math.log(count)) * (0.5 if feat[0] == "c" else 1.0)
            vec[h % self.dim] += weight if (h >> 16) & 1 else -weight
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


class Bgem3EmbeddingClient(EmbeddingClient):
    """BGE-M3 embeddings (plan §12); dense vectors of 1024 dimensions, loaded lazily on the first call.

    Needs the `models` extra (`sentence-transformers`, or `FlagEmbedding`). Raises ImportError with the install hint when
    neither is available, never silently falling back (an index records which embedder built it).
    """

    name = BGE_M3_NAME
    dim = 1024

    def __init__(
        self, model_name: str = "BAAI/bge-m3", batch_size: int = 16, device: str | None = None, max_seq_length: int | None = None
    ) -> None:
        """Create the client; nothing is loaded yet.

        Args:
            model_name: Hugging Face model id (configs/models.yaml `embeddings.model`)
            batch_size: texts per forward pass
            device: 'cpu', 'cuda' or None for the library default
            max_seq_length: token limit per text; None keeps the model's own (8192). The opt-in BGE-M3 store vectors were
                embedded at 512 tokens, so their queries use 512 too (`stores.hybrid`)
        """
        self.model_name, self.batch_size, self.device, self.max_seq_length = model_name, batch_size, device, max_seq_length
        self._model = None

    def _load(self):  # noqa: ANN202
        """Import and load the model on first use."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "BGE-M3 needs the 'models' extra: pip install 'vakeel_sahayak[models]' (sentence-transformers)"
                ) from exc
            from vakeel_sahayak.models.nli import local_checkpoint

            # the copy `make models` put under models/hf wins over a second download into the Hugging Face cache
            self._model = SentenceTransformer(local_checkpoint(self.model_name) or self.model_name, device=self.device)
            if self.max_seq_length:
                self._model.max_seq_length = self.max_seq_length
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed.

        Args:
            texts: see behaviour

        Returns:
            Unit-length vectors.
        """
        if not texts:
            return []
        vectors = self._load().encode(texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False)
        return [[float(x) for x in v] for v in vectors]


def bge_m3_available() -> bool:
    """True when a library that can load BGE-M3 is installed (checked without importing it)."""
    return importlib.util.find_spec("sentence_transformers") is not None


@lru_cache(maxsize=4)
def get_embedder(name: str | None = None) -> Embedder:
    """The embedder for a name: 'hashed-ngram', 'bge-m3' or 'auto'.

    `auto` (the default; override with `VS_EMBEDDER`) uses BGE-M3 when installed and the hashed fallback otherwise.

    Args:
        name: embedder name; None reads `VS_EMBEDDER`, default 'auto'

    Returns:
        A cached embedder instance.

    Raises:
        ValueError: for an unknown name.
    """
    choice = (name or os.environ.get("VS_EMBEDDER") or "auto").lower()
    if choice == "auto":
        choice = BGE_M3_NAME if bge_m3_available() else HASHED_NAME
    if choice in (HASHED_NAME, "hashed"):
        return HashedEmbeddingClient()
    if choice in (BGE_M3_NAME, "bgem3", "bge_m3"):
        return Bgem3EmbeddingClient()
    raise ValueError(f"unknown embedder {choice!r}: use 'hashed-ngram', 'bge-m3' or 'auto'")
