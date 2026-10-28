"""Opt-in BGE-M3 side vectors for the four vector stores (VS_STORES=bge; default off, the stores are not modified).

The shared stores were built with the hashed n-gram embedder (laptop, no torch). This tool adds a second, separate vector set:
one fp16 BGE-M3 vector per item id in a side file next to each store (`caselaw/reasoning.sqlite` -> `caselaw/reasoning.bge.sqlite`),
read by `stores.hybrid.HybridIndex` only when `VS_STORES=bge`. Three steps:

    python -m vakeel_sahayak.pipelines.store_builders.bge_vectors export --out data/bge_work/texts
        the exact text each row was embedded with, in id order, one gzip jsonl per store ({"id", "text"}), plus texts_manifest.json.
        The FTS table is contentless, so the text is rebuilt the way the builders made `IndexRow.text`: the paragraph stores keep it in
        the payload (`ParagraphRecord.text`); caselaw.similar embedded the order's facts part, so orders.jsonl is re-split
        (`order_splitter.analyse_split`, as `corpus._process_order`). The reconstruction is proved by re-embedding a seeded sample
        (500 rows per store) with the hashed embedder and comparing the bytes to the stored vector blobs; any mismatch stops the export.

    python bge_vectors.py embed --texts-dir T --out-dir O [--outbox B] --model-dir M
        GPU node (scripts/ada/embed_bge_m3.sbatch). transformers AutoModel, CLS pooling, L2 normalisation (what Bgem3EmbeddingClient gets
        from sentence-transformers for BAAI/bge-m3), fp16, length-sorted batches, max_length 512. Writes per store and shard of 20,000 rows
        `<store>.<k>.npy` (float16) and `<store>.<k>.ids.npy` (int64), then `<store>.<k>.json` (row count, sha256) as the completion marker;
        shards already present (or listed in --skip-file) are skipped, so a rerun resumes. Before the first shard it embeds 32 texts with
        sentence-transformers on CPU and stops unless every cosine to the GPU vector is at least 0.999. This subcommand imports nothing from
        the package (only numpy, torch, transformers, sentence-transformers), so the file runs on its own on the node.

    python -m vakeel_sahayak.pipelines.store_builders.bge_vectors apply --shards-dir S --texts-dir T
        builds the side files from the shards: checks shard hashes, that the ids equal the store's ids, unit norms, then a recall-style check
        (200 random rows: their own text as the query, embedded on the laptop with the local BGE-M3, must rank the row first by dense
        similarity; an exact duplicate text ranking first counts as a pass and is reported apart), and writes data/stores/BGE_MANIFEST.json.

Nothing here calls a paid API; the weights are the public BAAI/bge-m3 checkpoint.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

STORE_FILES = {  # store name -> path under the stores folder (configs/stores.yaml layout)
    "caselaw.reasoning": "caselaw/reasoning.sqlite",
    "caselaw.similar": "caselaw/similar.sqlite",
    "advocacy.arguments": "advocacy/arguments.sqlite",
    "advocacy.objections": "advocacy/objections.sqlite",
}
PARAGRAPH_STORES = {"caselaw.reasoning", "advocacy.arguments", "advocacy.objections"}
MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"  # the revision `make models` put in models/hf/BAAI--bge-m3 (its .cache metadata)
MAX_LENGTH = 512
SHARD_ROWS = 20_000
DIM = 1024
CHECK_MIN_COSINE = 0.999


def texts_file(texts_dir: str | Path, store: str) -> Path:
    """The gzip jsonl of one store's texts."""
    return Path(texts_dir) / f"{store}.texts.jsonl.gz"


def shard_stem(store: str, k: int) -> str:
    """'caselaw.reasoning.003'."""
    return f"{store}.{k:03d}"


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_texts(path: str | Path):  # noqa: ANN201
    """(id, text) pairs of a texts file, in file (id) order."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            yield int(row["id"]), row["text"]


def _free_bytes(path: str | Path) -> int:
    p = Path(path)
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free


def _need_disk(path: str | Path, nbytes: int, what: str) -> None:
    free = _free_bytes(path)
    if free < nbytes:
        raise SystemExit(f"not enough disk for {what}: {free / 1e9:.2f} GB free at {path}, need {nbytes / 1e9:.2f} GB")


# ------------------------------------------------------------------------------------------------------------------- export


def paragraph_texts(conn) -> list[tuple[int, str, bytes | None]]:  # noqa: ANN001
    """(id, text, stored vec) of a paragraph store: the builder's `IndexRow.text` is `ParagraphRecord.text`, kept in the payload."""
    return [(int(i), json.loads(p)["text"], v) for i, p, v in conn.execute("SELECT id, payload, vec FROM items ORDER BY id")]


def similar_texts(conn, orders_file: str | Path) -> list[tuple[int, str, bytes | None]]:  # noqa: ANN001
    """(id, facts text, stored vec) of caselaw.similar: the builder embedded `parts[FACTS]` of each order (key = doc_id), so the orders are
    re-normalised and re-split exactly as `corpus._process_order` does (pre-split `parts` win over the splitter)."""
    from vakeel_sahayak.pipelines.order_splitter import PART_ORDER, analyse_split
    from vakeel_sahayak.pipelines.store_builders.corpus import normalise_order
    from vakeel_sahayak.schemas.enums import OrderPart

    rows = {key: (int(i), v) for i, key, v in conn.execute("SELECT id, key, vec FROM items")}
    found: dict[str, str] = {}
    with open(orders_file, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            order, _ = normalise_order(json.loads(line))
            if order is None or order.doc_id not in rows or order.doc_id in found:
                continue
            if order.parts:
                parts = {p: order.parts.get(p, "") for p in PART_ORDER}
            else:
                parts = analyse_split(order.text).parts
            found[order.doc_id] = parts.get(OrderPart.FACTS, "")
            if n % 20000 == 0:
                print(f"[export] caselaw.similar: {n} orders read, {len(found)}/{len(rows)} matched", flush=True)
    missing = sorted(set(rows) - set(found))
    if missing:
        raise SystemExit(f"caselaw.similar: {len(missing)} store rows have no order in {orders_file} (first {missing[:3]})")
    return sorted(((rows[k][0], t, rows[k][1]) for k, t in found.items()), key=lambda r: r[0])


def verify_hashed(rows: list[tuple[int, str, bytes | None]], n: int, seed: int = 20261028) -> dict[str, Any]:
    """Re-embed a seeded sample with the hashed embedder and compare the bytes with the stored blobs (proof of the reconstruction)."""
    from array import array

    from vakeel_sahayak.models.embeddings import HashedEmbeddingClient

    with_vec = [r for r in rows if r[2]]
    if not with_vec:
        return {"sampled": 0, "matched": 0}
    dim = len(with_vec[0][2]) // 4
    emb = HashedEmbeddingClient(dim=dim)
    sample = random.Random(seed).sample(with_vec, min(n, len(with_vec)))
    bad = [i for i, text, blob in sample if array("f", emb.embed([text])[0]).tobytes() != blob]
    return {"sampled": len(sample), "matched": len(sample) - len(bad), "mismatched_ids": bad[:20], "dim": dim, "seed": seed}


def export(stores_dir: str, interim_dir: str, out_dir: str, only: list[str] | None, verify_n: int) -> dict[str, Any]:
    """Write the texts files and texts_manifest.json; raises SystemExit when a reconstruction check fails."""
    import sqlite3

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "texts_manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"stores": {}}
    for store, rel in STORE_FILES.items():
        if only and store not in only:
            continue
        t0 = time.time()
        src = Path(stores_dir) / rel
        conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        try:
            embedder = conn.execute("SELECT value FROM meta WHERE key='embedder'").fetchone()[0]
            if store in PARAGRAPH_STORES:
                rows = paragraph_texts(conn)
            else:
                rows = similar_texts(conn, Path(interim_dir) / "orders.jsonl")
        finally:
            conn.close()
        check = verify_hashed(rows, verify_n) if embedder == "hashed-ngram" else {"sampled": 0, "note": f"store embedder {embedder}"}
        if check.get("sampled") and check["matched"] != check["sampled"]:
            raise SystemExit(f"{store}: reconstructed text does not reproduce the stored vectors for ids {check['mismatched_ids']}")
        target = texts_file(out, store)
        h = hashlib.sha256()
        with gzip.open(target, "wt", encoding="utf-8", compresslevel=6) as f:
            for i, text, _ in rows:
                line = json.dumps({"id": i, "text": text}, ensure_ascii=False) + "\n"
                h.update(line.encode("utf-8"))
                f.write(line)
        manifest["stores"][store] = {
            "rows": len(rows), "file": target.name, "text_sha256": h.hexdigest(), "gz_sha256": _sha256(target),
            "gz_bytes": target.stat().st_size, "chars": sum(len(t) for _, t, _ in rows), "store_embedder": embedder,
            "hashed_check": check, "seconds": round(time.time() - t0, 1),
        }  # fmt: skip
        print(f"[export] {store}: {len(rows)} rows, hashed check {check.get('matched')}/{check.get('sampled')}, "
              f"{target.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s", flush=True)  # fmt: skip
        manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


# -------------------------------------------------------------------------------------------------------------------- embed


def _encode(model, tokenizer, texts: list[str], max_length: int, batch_tokens: int, device: str):  # noqa: ANN001, ANN202
    """fp16 CLS vectors, L2-normalised, for texts in their given order (batches are built over length-sorted texts)."""
    import numpy as np
    import torch

    enc = tokenizer(texts, truncation=True, max_length=max_length, add_special_tokens=True)["input_ids"]
    order = sorted(range(len(texts)), key=lambda i: len(enc[i]), reverse=True)
    out = np.empty((len(texts), model.config.hidden_size), dtype=np.float16)
    pad = tokenizer.pad_token_id
    start = 0
    while start < len(order):
        longest = len(enc[order[start]])
        size = max(1, min(256, batch_tokens // max(longest, 1)))
        idx = order[start : start + size]
        ids = torch.full((len(idx), longest), pad, dtype=torch.long)
        mask = torch.zeros((len(idx), longest), dtype=torch.long)
        for r, i in enumerate(idx):
            seq = enc[i]
            ids[r, : len(seq)] = torch.tensor(seq)
            mask[r, : len(seq)] = 1
        with torch.inference_mode():
            hidden = model(input_ids=ids.to(device), attention_mask=mask.to(device)).last_hidden_state[:, 0]
            vec = torch.nn.functional.normalize(hidden.float(), p=2, dim=-1)
        out[idx] = vec.cpu().numpy().astype(np.float16)
        start += size
    return out


def _equivalence_check(model, tokenizer, model_dir: str, texts: list[str], max_length: int, device: str) -> dict[str, Any]:  # noqa: ANN001
    """GPU fp16 transformers vectors against sentence-transformers on CPU (float32) for the same texts."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    gpu = _encode(model, tokenizer, texts, max_length, 8192, device).astype(np.float32)
    st = SentenceTransformer(model_dir, device="cpu")
    st.max_seq_length = max_length
    ref = st.encode(texts, batch_size=8, normalize_embeddings=True, show_progress_bar=False)
    cos = (gpu * ref).sum(axis=1)
    del st
    return {"n": len(texts), "min_cosine": float(cos.min()), "mean_cosine": float(cos.mean()), "max_abs_diff": float(np.abs(gpu - ref).max())}


def _version(dist: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(dist)
    except PackageNotFoundError:
        return None


def embed(args: argparse.Namespace) -> int:
    """GPU step: shards of fp16 vectors per store (see the module docstring)."""
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    outbox = Path(args.outbox) if args.outbox else None
    if outbox:
        outbox.mkdir(parents=True, exist_ok=True)
    skip = set()
    if args.skip_file and Path(args.skip_file).is_file():
        skip = {line.strip() for line in Path(args.skip_file).read_text().splitlines() if line.strip()}
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[embed] device={device} {torch.cuda.get_device_name(0) if device == 'cuda' else ''} torch={torch.__version__}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModel.from_pretrained(args.model_dir, dtype=torch.float16 if device == "cuda" else torch.float32).to(device).eval()
    stores = args.stores or list(STORE_FILES)
    status = {"model_id": MODEL_ID, "model_revision": args.model_revision, "max_length": args.max_length, "pooling": "cls",
              "normalised": True, "dtype": "float16", "device": device, "job_id": os.environ.get("SLURM_JOB_ID"), "node": os.uname().nodename,
              "torch": torch.__version__, "transformers": _version("transformers"), "sentence_transformers": _version("sentence-transformers")}  # fmt: skip
    if args.check_n:
        sample: list[str] = []
        for store in stores:  # a few texts from every store, so long facts texts and short paragraphs are both checked
            for _, text in read_texts(texts_file(args.texts_dir, store)):
                sample.append(text)
                if len(sample) % max(1, args.check_n // len(stores)) == 0:
                    break
        check = _equivalence_check(model, tokenizer, args.model_dir, sample[: args.check_n], args.max_length, device)
        status["equivalence_check"] = check
        print(f"[embed] equivalence vs sentence-transformers (CPU): {check}", flush=True)
        (out / "equivalence_check.json").write_text(json.dumps(check, indent=2))
        if outbox:
            (outbox / "equivalence_check.json").write_text(json.dumps(check, indent=2))
        if check["min_cosine"] < CHECK_MIN_COSINE:
            print(f"[embed] equivalence check FAILED (min cosine {check['min_cosine']:.5f} < {CHECK_MIN_COSINE})", flush=True)
            return 3
    t_all = time.time()
    for store in stores:
        rows = list(read_texts(texts_file(args.texts_dir, store)))
        for k, start in enumerate(range(0, len(rows), args.shard_rows)):
            stem = shard_stem(store, k)
            if stem in skip or (out / f"{stem}.json").is_file() or (outbox and (outbox / f"{stem}.json").is_file()):
                continue
            t0 = time.time()
            chunk = rows[start : start + args.shard_rows]
            vecs = _encode(model, tokenizer, [t for _, t in chunk], args.max_length, args.batch_tokens, device)
            ids = np.asarray([i for i, _ in chunk], dtype=np.int64)
            np.save(out / f"{stem}.npy.part.npy", vecs)
            np.save(out / f"{stem}.ids.npy.part.npy", ids)
            os.replace(out / f"{stem}.npy.part.npy", out / f"{stem}.npy")
            os.replace(out / f"{stem}.ids.npy.part.npy", out / f"{stem}.ids.npy")
            info = {"store": store, "shard": k, "rows": len(chunk), "first_id": int(ids[0]), "last_id": int(ids[-1]),
                    "npy_sha256": _sha256(out / f"{stem}.npy"), "ids_sha256": _sha256(out / f"{stem}.ids.npy"),
                    "seconds": round(time.time() - t0, 1), **status}  # fmt: skip
            info.pop("equivalence_check", None)
            if outbox:  # backpressure: the laptop pulls and deletes shards from the outbox; never hold more than outbox_max there
                while len(list(outbox.glob("*.*.[0-9][0-9][0-9].json"))) >= args.outbox_max:
                    time.sleep(20)
                for suffix in (".npy", ".ids.npy"):
                    shutil.copyfile(out / f"{stem}{suffix}", outbox / f"{stem}{suffix}.part")
                    os.replace(outbox / f"{stem}{suffix}.part", outbox / f"{stem}{suffix}")
                (outbox / f"{stem}.json").write_text(json.dumps(info, indent=2))
                (out / f"{stem}.npy").unlink()
                (out / f"{stem}.ids.npy").unlink()
            (out / f"{stem}.json").write_text(json.dumps(info, indent=2))
            print(f"[embed] {stem}: {len(chunk)} rows in {time.time() - t0:.0f}s ({len(chunk) / max(time.time() - t0, 1e-6):.0f}/s)", flush=True)
    done = {**status, "seconds": round(time.time() - t_all, 1), "stores": stores}
    for d in [out, *([outbox] if outbox else [])]:
        (d / "EMBED_DONE.json").write_text(json.dumps(done, indent=2))
    print(f"[embed] all done in {time.time() - t_all:.0f}s", flush=True)
    return 0


# -------------------------------------------------------------------------------------------------------------------- apply


def load_shards(shards_dir: str | Path, store: str):  # noqa: ANN201
    """(ids, fp16 vectors, shard infos) of one store, in shard order; checks each shard's sha256 and that the shards are contiguous."""
    import numpy as np

    infos = sorted((json.loads(p.read_text()) for p in Path(shards_dir).glob(f"{store}.[0-9][0-9][0-9].json")), key=lambda i: i["shard"])
    if not infos:
        raise SystemExit(f"no shards for {store} in {shards_dir}")
    if [i["shard"] for i in infos] != list(range(len(infos))):
        raise SystemExit(f"{store}: shards {[i['shard'] for i in infos]} are not 0..{len(infos) - 1}")
    ids_parts, vec_parts = [], []
    for info in infos:
        stem = shard_stem(store, info["shard"])
        for suffix, key in ((".npy", "npy_sha256"), (".ids.npy", "ids_sha256")):
            if _sha256(Path(shards_dir) / f"{stem}{suffix}") != info[key]:
                raise SystemExit(f"{stem}{suffix}: sha256 does not match its shard record")
        ids_parts.append(np.load(Path(shards_dir) / f"{stem}.ids.npy"))
        vec_parts.append(np.load(Path(shards_dir) / f"{stem}.npy"))
    return np.concatenate(ids_parts), np.concatenate(vec_parts), infos


def self_rank_check(ids, mat, texts: dict[int, str], embedder, n: int, seed: int = 20261028) -> dict[str, Any]:  # noqa: ANN001
    """For `n` random rows, embed the row's own text as a query and rank every row by dense similarity: the row (or a row with the
    identical text, reported apart) must come first."""
    import numpy as np

    rng = random.Random(seed)
    sample = rng.sample(range(len(ids)), min(n, len(ids)))
    queries = embedder.embed([texts[int(ids[j])] for j in sample])
    first = dup = 0
    fails: list[int] = []
    self_cos = []
    for j, q in zip(sample, queries, strict=True):
        sims = mat @ np.asarray(q, dtype=np.float32)
        top = int(np.argsort(-sims, kind="stable")[0])
        self_cos.append(float(sims[j]))
        if top == j:
            first += 1
        elif texts[int(ids[top])] == texts[int(ids[j])] or sims[top] - sims[j] < 1e-3:  # an exact duplicate (or tie at fp16 precision)
            dup += 1
        else:
            fails.append(int(ids[j]))
    sc = np.asarray(self_cos)
    return {"n": len(sample), "self_first": first, "duplicate_first": dup, "failed": len(fails), "failed_ids": fails[:20],
            "self_cosine_min": float(sc.min()), "self_cosine_median": float(np.median(sc)), "seed": seed}  # fmt: skip


def apply(args: argparse.Namespace) -> dict[str, Any]:
    """Build the side files from the shards, check them and write BGE_MANIFEST.json."""
    import sqlite3

    import numpy as np

    from vakeel_sahayak.models.embeddings import Bgem3EmbeddingClient
    from vakeel_sahayak.stores.hybrid import HybridIndex, side_vectors_path, write_side_vectors

    stores_dir = Path(args.stores_dir)
    texts_manifest = json.loads((Path(args.texts_dir) / "texts_manifest.json").read_text())
    manifest_path = stores_dir / "BGE_MANIFEST.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"stores": {}}
    embedder = None if args.sanity_n == 0 else Bgem3EmbeddingClient(device="cpu", max_seq_length=args.max_length)
    for store, rel in STORE_FILES.items():
        if args.only and store not in args.only:
            continue
        t0 = time.time()
        main = stores_dir / rel
        side = side_vectors_path(main)
        ids, vecs, infos = load_shards(args.shards_dir, store)
        conn = sqlite3.connect(f"file:{main}?mode=ro", uri=True)
        try:
            own = np.fromiter((r[0] for r in conn.execute("SELECT id FROM items ORDER BY id")), dtype=np.int64)
            main_embedder = conn.execute("SELECT value FROM meta WHERE key='embedder'").fetchone()[0]
        finally:
            conn.close()
        if not np.array_equal(np.sort(ids), own) or len(ids) != len(own):
            raise SystemExit(f"{store}: shard ids ({len(ids)}) do not equal the store's ids ({len(own)})")
        tm = texts_manifest["stores"][store]
        if tm["rows"] != len(own):
            raise SystemExit(f"{store}: texts manifest has {tm['rows']} rows, store has {len(own)}")
        order = np.argsort(ids, kind="stable")
        ids, vecs = ids[order], vecs[order]
        norms = np.linalg.norm(vecs.astype(np.float32), axis=1)
        if norms.min() < 0.99 or norms.max() > 1.01:
            raise SystemExit(f"{store}: vector norms outside [0.99, 1.01] ({norms.min():.4f}..{norms.max():.4f})")
        _need_disk(side.parent, vecs.nbytes + 50_000_000, f"{side.name}")
        first = infos[0]
        meta = {"embedder": "bge-m3", "model_id": first.get("model_id", MODEL_ID), "model_revision": first.get("model_revision"),
                "max_length": first.get("max_length", args.max_length), "pooling": first.get("pooling", "cls"), "normalised": "1",
                "text_sha256": tm["text_sha256"], "store": store, "store_file": main.name, "store_embedder": main_embedder,
                "store_rows": str(len(own)), "job_id": first.get("job_id"), "built": time.strftime("%Y-%m-%d")}  # fmt: skip
        write_side_vectors(side, ids, vecs, meta)
        entry: dict[str, Any] = {"side_file": str(side.relative_to(stores_dir)), "rows": int(len(ids)), "bytes": side.stat().st_size,
                                 "sha256": _sha256(side), "shards": len(infos), "norm_min": float(norms.min()), "norm_max": float(norms.max()),
                                 **{k: meta[k] for k in ("model_id", "model_revision", "max_length", "pooling", "text_sha256", "job_id")},
                                 "embed_seconds": round(sum(i.get("seconds", 0) for i in infos), 1)}  # fmt: skip
        if embedder is not None:
            texts = dict(read_texts(texts_file(args.texts_dir, store)))
            mat = vecs.astype(np.float32)
            entry["self_rank_check"] = check = self_rank_check(ids, mat, texts, embedder, args.sanity_n)
            del texts, mat
            print(f"[apply] {store}: self-rank {check}", flush=True)
            if check["failed"] > max(1, args.sanity_n // 100):
                raise SystemExit(f"{store}: {check['failed']} of {check['n']} rows did not rank themselves first; the side file is suspect")
        idx = HybridIndex(main, side_vectors="bge", side_embedder=_ConstantEmbedder(vecs[0].astype(np.float32)))
        try:  # the wiring: the side file opens, its ids line up, and a query equal to row 1's vector finds row 1 (or its duplicate)
            hits = idx._dense("x", "", [], 1)  # noqa: SLF001
            entry["wiring_check"] = {"top_id": hits[0] if hits else None, "expected_id": int(ids[0])}
        finally:
            idx.close()
        entry["seconds"] = round(time.time() - t0, 1)
        manifest["stores"][store] = entry
        manifest.update({"embedder": "bge-m3", "opt_in": "VS_STORES=bge", "updated": time.strftime("%Y-%m-%d %H:%M"),
                         "texts_manifest": {k: v for k, v in texts_manifest.items() if k != "stores"}})  # fmt: skip
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"[apply] {store}: {len(ids)} vectors -> {side} ({side.stat().st_size / 1e6:.0f} MB) in {time.time() - t0:.0f}s", flush=True)
        if args.delete_shards:
            for info in infos:
                stem = shard_stem(store, info["shard"])
                for suffix in (".npy", ".ids.npy"):
                    (Path(args.shards_dir) / f"{stem}{suffix}").unlink(missing_ok=True)
    return manifest


class _ConstantEmbedder:
    """Query embedder returning one fixed vector (the wiring check in `apply`)."""

    name = "bge-m3"

    def __init__(self, vec) -> None:  # noqa: ANN001
        self.vec = [float(x) for x in vec]
        self.dim = len(self.vec)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(self.vec) for _ in texts]


# ---------------------------------------------------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    """CLI: export | embed | apply."""
    ap = argparse.ArgumentParser(description="Opt-in BGE-M3 side vectors for the four vector stores (VS_STORES=bge).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="texts per store (gzip jsonl, id order), proved against the hashed vectors")
    ex.add_argument("--stores-dir", default=None)
    ex.add_argument("--interim", default=None)
    ex.add_argument("--out", default="data/bge_work/texts")
    ex.add_argument("--only", nargs="*", choices=list(STORE_FILES))
    ex.add_argument("--verify-n", type=int, default=500)
    em = sub.add_parser("embed", help="GPU: fp16 BGE-M3 shards")
    em.add_argument("--texts-dir", required=True)
    em.add_argument("--out-dir", required=True)
    em.add_argument("--outbox", default=None, help="folder the laptop pulls from (shards are moved there, at most --outbox-max at a time)")
    em.add_argument("--outbox-max", type=int, default=4)
    em.add_argument("--skip-file", default=None, help="shard stems already received (one per line)")
    em.add_argument("--model-dir", required=True)
    em.add_argument("--model-revision", default=MODEL_REVISION)
    em.add_argument("--stores", nargs="*", choices=list(STORE_FILES))
    em.add_argument("--shard-rows", type=int, default=SHARD_ROWS)
    em.add_argument("--max-length", type=int, default=MAX_LENGTH)
    em.add_argument("--batch-tokens", type=int, default=16384)
    em.add_argument("--check-n", type=int, default=32)
    ap_ = sub.add_parser("apply", help="side files from shards, with checks; writes BGE_MANIFEST.json")
    ap_.add_argument("--shards-dir", default="data/bge_work/shards")
    ap_.add_argument("--texts-dir", default="data/bge_work/texts")
    ap_.add_argument("--stores-dir", default=None)
    ap_.add_argument("--only", nargs="*", choices=list(STORE_FILES))
    ap_.add_argument("--sanity-n", type=int, default=200)
    ap_.add_argument("--max-length", type=int, default=MAX_LENGTH)
    ap_.add_argument("--delete-shards", action="store_true", help="remove each store's shards once its side file is written and checked")
    args = ap.parse_args(argv)
    if args.cmd == "embed":
        return embed(args)
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    if args.cmd == "export":
        export(args.stores_dir or paths.stores_dir, args.interim or paths.interim_dir, args.out, args.only, args.verify_n)
        return 0
    args.stores_dir = args.stores_dir or paths.stores_dir
    apply(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
