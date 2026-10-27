"""S16b true late chunking: BGE-M3 token vectors for `stores.chunk_strategies.LateChunkEmbedder` (opt-in, never used by default).

Gunther, Mohr, Williams, Wang and Xiao, "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models", arXiv 2409.04701 (2024): embed the whole
long text once with a long-context encoder (here BGE-M3, 8192 tokens), then mean-pool the token vectors inside each chunk's span, so every chunk vector has seen the whole order.

`BgeM3TokenEmbedder` has the three things `LateChunkEmbedder` and `HybridIndex` need: `name`, `dim`, `embed(texts)` (the usual BGE-M3 dense vector: CLS, unit length, for queries and
plain chunks) and `embed_tokens(text) -> (spans, vectors)` (one vector per non-special token and its character span). A text longer than the window is cut into consecutive windows, each
encoded with its own context (the paper's long-late-chunking variant would overlap them; not done here). The weights come from `models/hf/BAAI--bge-m3` (`make models`), the encoder needs
torch and transformers (guarded: the error names what is missing); on CPU a 300-token chunk-free order takes a second or two, a 8192-token window about a minute, so run it on a sample.

The window logic (`token_vectors`) takes the tokeniser and the forward pass as callables, so it is tested with a tiny fake encoder and no weights.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

Spans = list[tuple[int, int]]
Tokenize = Callable[[str], tuple[list[int], Spans]]  # text -> (token ids WITHOUT special tokens, character span of each)
Forward = Callable[[list[int]], Sequence[Sequence[float]]]  # ids of one window -> one vector per id (special tokens already removed)


def token_vectors(text: str, tokenize: Tokenize, forward: Forward, window: int = 8190) -> tuple[Spans, list[Any]]:
    """Token spans and vectors of `text`: tokenised once, encoded in consecutive windows of at most `window` tokens (8190 + CLS + SEP = BGE-M3's 8192).

    Returns:
        `(spans, vectors)` with one entry per token; a span is `(start_char, end_char)` of that token in `text`.
    """
    if window < 1:
        raise ValueError("window must be at least 1 token")
    ids, spans = tokenize(text)
    vectors: list[Any] = []
    for i in range(0, len(ids), window):
        out = forward(ids[i : i + window])
        if len(out) != len(ids[i : i + window]):
            raise ValueError(f"the encoder returned {len(out)} vectors for {len(ids[i : i + window])} tokens")
        vectors.extend(out)
    return list(spans), vectors


class BgeM3TokenEmbedder:
    """BGE-M3 with token vectors (see the module docstring). Loaded lazily on the first call; `encoder=(tokenize, forward, cls_embed)` injects a fake for tests."""

    name = "bge-m3"  # the same name as the dense client: a late-chunked index is a different index only through `late(bge-m3)`
    dim = 1024

    def __init__(self, model_path: str | None = None, window: int = 8190, device: str = "cpu",
                 encoder: tuple[Tokenize, Forward, Callable[[list[str]], list[list[float]]]] | None = None) -> None:
        self.model_path, self.window, self.device = model_path, window, device
        self._enc = encoder

    def _load(self) -> tuple[Tokenize, Forward, Callable[[list[str]], list[list[float]]]]:
        if self._enc is not None:
            return self._enc
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError("true late chunking needs torch and transformers: pip install torch transformers (the venv's torch is CPU only, which is enough for a sample)") from exc
        path = self.model_path
        if path is None:
            from vakeel_sahayak.models.nli import local_checkpoint

            path = local_checkpoint("BAAI/bge-m3")
        if not path:
            raise FileNotFoundError("BGE-M3 weights not found at models/hf/BAAI--bge-m3: run `make models` (about 2 GB)")
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModel.from_pretrained(path).to(self.device).eval()
        self._enc = _hf_encoder(tok, model, torch)
        return self._enc

    def embed_tokens(self, text: str) -> tuple[Spans, list[Any]]:
        """One contextual vector (full-document context, per window) and character span per token of `text`."""
        tokenize, forward, _ = self._load()
        return token_vectors(text, tokenize, forward, self.window)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """The dense BGE-M3 vector of each text (CLS, unit length), the way `Bgem3EmbeddingClient` makes it."""
        if not texts:
            return []
        return self._load()[2](list(texts))


def _hf_encoder(tok: Any, model: Any, torch: Any) -> tuple[Tokenize, Forward, Callable[[list[str]], list[list[float]]]]:
    """The three callables over a HF tokenizer (fast, with offsets) and model; `model(...).last_hidden_state` is `[1, tokens, dim]`."""
    cls_id, sep_id = tok.cls_token_id, tok.sep_token_id

    def tokenize(text: str) -> tuple[list[int], Spans]:
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
        return list(enc["input_ids"]), [(int(a), int(b)) for a, b in enc["offset_mapping"]]

    def forward(ids: list[int]) -> list[list[float]]:
        batch = torch.tensor([[cls_id, *ids, sep_id]], dtype=torch.long)
        with torch.no_grad():
            hidden = model(input_ids=batch, attention_mask=torch.ones_like(batch)).last_hidden_state[0]
        return hidden[1:-1].float().cpu().numpy()  # drop CLS and SEP; an ndarray: pooling stays fast

    def cls_embed(texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            enc = tok(t, return_tensors="pt", truncation=True, max_length=8192)
            with torch.no_grad():
                vec = model(**enc).last_hidden_state[0, 0].float()
            vec = vec / (vec.norm() or 1.0)
            out.append([float(x) for x in vec.cpu().tolist()])
        return out

    return tokenize, forward, cls_embed


def mean_pool(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Unit-length mean of vectors (numpy rows or lists)."""
    try:
        import numpy as np

        total = np.asarray(vectors, dtype="float64").sum(axis=0)
        norm = float(np.linalg.norm(total))
        return (total / norm if norm else total).tolist()
    except ImportError:  # pragma: no cover
        total = [sum(col) for col in zip(*vectors, strict=False)]
        norm = math.sqrt(sum(v * v for v in total))
        return [v / norm for v in total] if norm else total
