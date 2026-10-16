"""Fetch a bounded Hindi test subset of Kathbath (AI4Bharat) straight from the official object store (plan §2 source 5, §15.2 T8).

The Hugging Face repo `ai4bharat/Kathbath` is gated and holds only train/valid. The benchmark's test sets are published, without
login, as tarballs on AI4Bharat's object store (links on https://github.com/AI4Bharat/IndicSUPERB):

    https://objectstore.e2enetworks.net/indic-superb/kathbath/clean/testkn_audio.tar     (3.6 GB, all 12 languages, m4a)
    https://objectstore.e2enetworks.net/indic-superb/kathbath/clean/transcripts_n2w.tar  (0.2 GB, all languages and splits)

The audio tar is one block of members per language (one member is about 0.1 MB). To avoid downloading 3.6 GB, this module finds the
first Hindi member by bisection on HTTP range probes, then streams from there and keeps the first `limit` Hindi members; the
transcripts tar is walked header by header (few members) and only the Hindi `test_known` transcript file is kept. Output:

    data/raw/kathbath/hindi/test_known/audio/<speaker-file>.m4a
    data/raw/kathbath/hindi/test_known/transcription_n2w.txt
    data/raw/kathbath/hindi/test_known/manifest.jsonl     {audio, bytes, sha256, transcript}  (utterances with a transcript)

    python -m vakeel_sahayak.pipelines.kathbath_fetch --out data/raw/kathbath --limit 1000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

BASE = "https://objectstore.e2enetworks.net/indic-superb/kathbath/clean"
AUDIO_TAR = f"{BASE}/testkn_audio.tar"
TRANSCRIPTS_TAR = f"{BASE}/transcripts_n2w.tar"
LANG = "hindi"
_NAME = re.compile(rb"kb_data_clean_m4a/([a-z_]+)/test_known/audio/")


def _get(session: Any, url: str, start: int, length: int, stream: bool = False) -> Any:
    for attempt in range(8):
        try:
            resp = session.get(url, headers={"Range": f"bytes={start}-{start + length - 1}"}, timeout=120, stream=stream)
            resp.raise_for_status()
            return resp
        except Exception:  # noqa: BLE001 - retried
            if attempt == 7:
                raise
            time.sleep(min(30, 2**attempt))
    raise RuntimeError("unreachable")


def language_at(session: Any, url: str, offset: int, window: int = 400_000) -> str | None:
    """Language of the first audio member header found at or after `offset` (None if the window holds none)."""
    data = _get(session, url, offset, window).content
    m = _NAME.search(data)
    return m.group(1).decode() if m else None


def find_language_start(session: Any, url: str, size: int, lang: str = LANG, step: int = 1 << 20) -> int:
    """Byte offset (512-aligned) of the first member of `lang` in the audio tar.

    Probes 16 evenly spaced offsets to bracket the language, bisects to `step` bytes, then finds the exact header.
    """
    from concurrent.futures import ThreadPoolExecutor

    offsets = [size * k // 16 for k in range(16)]
    with ThreadPoolExecutor(16) as pool:  # the object store gives about 30 KB/s per connection, so probe in parallel
        probes = list(zip(offsets, pool.map(lambda off: language_at(session, url, off), offsets), strict=True))
    hits = [off for off, name in probes if name == lang]
    if not hits:
        raise ValueError(f"no {lang} member found at the probe offsets")
    first_hit = min(hits)
    prior = [off for off, name in probes if off < first_hit]
    lo, hi = (max(prior) if prior else 0), first_hit  # the block starts in (lo, hi]
    while hi - lo > step:
        mid = (lo + hi) // 2
        if language_at(session, url, mid) == lang:
            hi = mid
        else:
            lo = mid
    window_start = max(0, lo - step)
    data = _get(session, url, window_start, hi - window_start + 2_000_000).content
    needle = f"kb_data_clean_m4a/{lang}/test_known/audio/".encode()
    idx = data.find(needle)
    while idx >= 0:
        start = window_start + idx
        # the first Hindi header is the one whose predecessor header names another language
        before = data[max(0, idx - 100_000) : idx]
        previous = _NAME.findall(before)
        if start % 512 == 0 and (not previous or previous[-1].decode() != lang):
            return start
        idx = data.find(needle, idx + 1)
    raise ValueError("could not align to the first Hindi header")


def _header(block: bytes) -> tuple[str, int] | None:
    if len(block) < 512 or block.count(b"\0") == 512:
        return None
    name = block[:100].split(b"\0", 1)[0].decode("utf-8", "replace")
    size = int(block[124:136].split(b"\0", 1)[0].strip() or b"0", 8)
    return name, size


def fetch_parallel(url: str, start: int, length: int, block: int = 2 << 20, workers: int = 24) -> bytes:
    """`length` bytes from `start` as parallel range requests (the object store is slow per connection)."""
    from concurrent.futures import ThreadPoolExecutor

    import requests

    spans = [(start + o, min(block, length - o)) for o in range(0, length, block)]
    local = __import__("threading").local()

    def one(span: tuple[int, int]) -> bytes:
        if not hasattr(local, "s"):
            local.s = requests.Session()
        return bytes(_get(local.s, url, span[0], span[1]).content)

    with ThreadPoolExecutor(workers) as pool:
        return b"".join(pool.map(one, spans))


def stream_members(session: Any, url: str, start: int, limit: int, lang: str = LANG, avg_member: int = 120_000) -> list[tuple[str, bytes]]:
    """Read up to `limit` consecutive audio members of `lang` starting at the header at `start`.

    The region expected to hold `limit` members is fetched in parallel blocks; a member that runs past it is completed serially.
    """
    out: list[tuple[str, bytes]] = []
    buffer = fetch_parallel(url, start, limit * avg_member)
    base = start
    while len(out) < limit:
        if len(buffer) < 512:
            buffer += _get(session, url, base + len(buffer), 8 << 20).content
        header = _header(buffer[:512])
        if header is None:
            break
        name, size = header
        if f"/{lang}/test_known/audio/" not in name:
            break
        total = 512 + ((size + 511) // 512) * 512
        while len(buffer) < total:
            buffer += _get(session, url, base + len(buffer), 8 << 20).content
        out.append((name, buffer[512 : 512 + size]))
        buffer = buffer[total:]
        base += total
    return out


def find_member(session: Any, url: str, suffix: str, size: int) -> tuple[int, int]:
    """Walk the tar header by header (jumping over contents) and return (data offset, size) of the member whose name ends with `suffix`."""
    pos = 0
    while pos < size:
        header = _header(_get(session, url, pos, 512).content)
        if header is None:
            break
        name, member_size = header
        if name.endswith(suffix):
            return pos + 512, member_size
        pos += 512 + ((member_size + 511) // 512) * 512
    raise ValueError(f"{suffix} not found in {url}")


def fetch(out_dir: str, limit: int = 1000) -> dict[str, Any]:
    """Download the Hindi test_known subset (first `limit` utterances) and its transcripts into `out_dir`; write a manifest."""
    import requests

    session = requests.Session()
    out = Path(out_dir) / LANG / "test_known"
    (out / "audio").mkdir(parents=True, exist_ok=True)
    audio_size = int(session.head(AUDIO_TAR, timeout=60).headers["content-length"])
    trans_size = int(session.head(TRANSCRIPTS_TAR, timeout=60).headers["content-length"])
    transcript_path = out / "transcription_n2w.txt"
    if not transcript_path.is_file():
        offset, length = find_member(session, TRANSCRIPTS_TAR, f"{LANG}/test_known/transcription_n2w.txt", trans_size)
        transcript_path.write_bytes(_get(session, TRANSCRIPTS_TAR, offset, length).content)
    transcripts: dict[str, str] = {}
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        key, _, text = line.partition("\t")  # "<speaker-file>.m4a<TAB><text>"
        if key.strip() and text.strip():
            transcripts[key.strip()] = text.strip()
    existing = sorted((out / "audio").glob("*.m4a"))
    if len(existing) < limit:
        start = find_language_start(session, AUDIO_TAR, audio_size)
        for name, data in stream_members(session, AUDIO_TAR, start, limit):
            (out / "audio" / Path(name).name).write_bytes(data)
    rows = []
    for path in sorted((out / "audio").glob("*.m4a")):
        text = transcripts.get(path.stem) or transcripts.get(path.name)
        if text:
            rows.append({"audio": f"audio/{path.name}", "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "transcript": text})
    (out / "manifest.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return {"audio_files": len(list((out / "audio").glob("*.m4a"))), "with_transcript": len(rows), "transcript_lines": len(transcripts), "audio_tar_bytes": audio_size}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Fetch a bounded Hindi Kathbath test_known subset.")
    parser.add_argument("--out", default="data/raw/kathbath")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)
    print(json.dumps(fetch(args.out, args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
