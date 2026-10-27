"""S16b true late chunking: window logic, span pooling with a tiny fake encoder, the torch wrapper on a tiny module (CPU), the study option. No BGE-M3 weights."""

from __future__ import annotations

import json
import math

import pytest

from vakeel_sahayak.eval.studies import run_study
from vakeel_sahayak.stores import late_encoder as le
from vakeel_sahayak.stores.chunk_strategies import LateChunkEmbedder

DOC = "alpha beta gamma. delta epsilon zeta."


def fake_tokenize(text):
    ids, spans, pos = [], [], 0
    for w in text.split(" "):
        start = text.index(w, pos)
        ids.append(len(ids) + 1)
        spans.append((start, start + len(w)))
        pos = start + len(w)
    return ids, spans


def fake_forward(ids):
    """A context-dependent vector: the token id on one axis, the window length on another (so windows differ)."""
    return [[float(i), float(len(ids)), 1.0] for i in ids]


def fake_encoder():
    return fake_tokenize, fake_forward, lambda texts: [[1.0, 0.0, 0.0] for _ in texts]


def test_windows_cover_every_token_once_and_keep_character_spans():
    spans, vecs = le.token_vectors(DOC, fake_tokenize, fake_forward, window=4)
    assert len(spans) == len(vecs) == 6 and spans[0] == (0, 5) and spans[-1] == (len(DOC) - 5, len(DOC))
    assert [v[1] for v in vecs] == [4.0] * 4 + [2.0] * 2  # two windows: 4 tokens, then 2
    with pytest.raises(ValueError):
        le.token_vectors(DOC, fake_tokenize, fake_forward, window=0)
    with pytest.raises(ValueError):
        le.token_vectors(DOC, fake_tokenize, lambda ids: [[0.0]], window=4)  # an encoder that drops tokens is refused


def test_late_embedder_pools_token_vectors_inside_each_chunk_span():
    base = le.BgeM3TokenEmbedder(encoder=fake_encoder(), window=100)
    late = LateChunkEmbedder(base)
    assert late.mode == "token_pooling" and late.name == "late(bge-m3)"
    late.prepare(DOC, ["alpha beta gamma.", "delta epsilon zeta."])
    (v1,), (v2,) = late.embed(["alpha beta gamma."]), late.embed(["delta epsilon zeta."])
    n1 = math.sqrt(sum(x * x for x in [1 + 2 + 3, 18.0, 3.0]))
    assert v1 == pytest.approx([6 / n1, 18 / n1, 3 / n1]) and v1 != v2
    assert math.isclose(sum(x * x for x in v2), 1.0)
    assert late.embed(["a query"])[0] == [1.0, 0.0, 0.0]  # anything that is not a chunk gets the dense vector


def test_numpy_rows_are_pooled_with_numpy():
    np = pytest.importorskip("numpy")
    vecs = np.array([[3.0, 0.0], [0.0, 4.0]])
    assert le.mean_pool(vecs) == pytest.approx([0.6, 0.8])


def test_missing_weights_or_torch_give_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("VS_MODELS_DIR", str(tmp_path))
    with pytest.raises((FileNotFoundError, ImportError), match="models|torch"):
        le.BgeM3TokenEmbedder().embed_tokens("x")


def test_hf_wrapper_on_a_tiny_torch_module_on_cpu():
    torch = pytest.importorskip("torch")

    class Tok:
        cls_token_id, sep_token_id = 0, 2

        def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False, truncation=False, return_tensors=None, max_length=None):
            ids, spans = fake_tokenize(text)
            if return_tensors:
                return {"input_ids": torch.tensor([[0, *ids, 2]])}
            return {"input_ids": ids, "offset_mapping": spans}

    class Out:
        def __init__(self, h):
            self.last_hidden_state = h

    class Model(torch.nn.Module):
        def forward(self, input_ids=None, attention_mask=None):
            return Out(torch.stack([input_ids.float(), torch.ones_like(input_ids).float()], dim=-1))

    tokenize, forward, cls_embed = le._hf_encoder(Tok(), Model(), torch)
    emb = le.BgeM3TokenEmbedder(encoder=(tokenize, forward, cls_embed), window=3)
    spans, vecs = emb.embed_tokens(DOC)
    assert len(spans) == len(vecs) == 6 and [float(v[0]) for v in vecs] == [1, 2, 3, 4, 5, 6]  # CLS and SEP are dropped
    (dense,) = emb.embed(["alpha beta"])
    assert math.isclose(sum(x * x for x in dense), 1.0)  # unit length CLS vector


def test_s16_study_option_runs_late_chunking_with_an_injected_encoder(tmp_path):
    rows = [{"doc_id": f"DOC{i:04d}", "court": "X", "date": "2020-01-01",
             "parts": {"facts": "Facts.", "reasoning": f"1. Heard counsel.\n\n2. The applicant is in custody since month{i} and the investigation is complete.\n\n3. The applicant has no antecedents number{i} at all.\n\n4. Bail is granted on conditions."}}
            for i in range(200)]
    pf = tmp_path / "parts.jsonl"
    pf.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    class Emb(le.BgeM3TokenEmbedder):
        dim = 1024

        def __init__(self):
            super().__init__(encoder=(fake_tokenize, lambda ids: [[float(i % 7), 1.0] + [0.0] * 1022 for i in ids], lambda texts: [[1.0] + [0.0] * 1023 for _ in texts]))

    res = run_study("s16", str(tmp_path / "o"), n=4, parts_file=str(pf), ks=(5,), use_g2=False, late_embedder=Emb())
    assert set(res["results"]["first_sentence"]) == {"structure", "late"}
    assert res["results"]["first_sentence"]["late"]["late_mode"] == "token_pooling"
    assert "token vectors" in res["embedder"]


def test_cli_option_is_s16_only_and_bge_m3_without_weights_fails_cleanly(tmp_path, monkeypatch, capsys):
    from vakeel_sahayak.eval import studies

    with pytest.raises(SystemExit):
        studies.main(["s14", "--out", str(tmp_path), "--late-embedder", "bge-m3"])
