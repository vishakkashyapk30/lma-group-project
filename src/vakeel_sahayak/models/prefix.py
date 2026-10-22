"""Prefix-friendly prompts and the shared-prefix meter (variant S14d, `Switches.prefix_layout`; evaluation plan S14 (b)).

Papers (adapted, not reproduced): Zheng et al., "SGLang: Efficient Execution of Structured Language Model Programs", NeurIPS 2024,
https://proceedings.neurips.cc/paper_files/paper/2024/hash/724be4472168f31ba1c9ac630f15dec8-Abstract.html (RadixAttention keeps the KV cache of a prompt prefix in a
radix tree and reuses it for any later prompt that starts the same way); Pan et al., "KVFlow: Efficient Prefix Caching for Accelerating LLM-Based Multi-Agent
Workflows", NeurIPS 2025, https://papers.neurips.cc/paper_files/paper/2025/hash/b7971d31a7d5eb0f1eed2f8f6f368195-Abstract-Conference.html (an agent step graph decides
which prefixes to keep); Lin et al., "Parrot", OSDI 2024, https://www.usenix.org/conference/osdi24/presentation/lin-chaofan (shared prefixes found from the application's
request structure). The idea: a serving layer can only reuse a prefix that is byte-identical, so the application must keep shared text first.

What we took: put the text that is the same across cases first and the text that differs last, and measure how many tokens of each prompt are shared with an
earlier prompt of the same task. What we changed, and why: (1) we change only the prompt, not the engine: vLLM's automatic prefix caching is already on
(`models/vllm_client.py`, `enable_prefix_caching`), so this variant decides how much of each prompt it can reuse; KVFlow's eviction and prefetch and SGLang's runtime are not
used. (2) The prompt layout was already "system, task, instructions, schema, input"; the variant changes the INPUT block only: the public corpus data goes before
the case data (the corpus text is the larger and more often repeated part), the remaining top-level keys follow in sorted order, and every object's keys are sorted, so two
prompts that carry the same data always serialise it the same way. Meaning is unchanged (the input is a JSON object; `parse_prompt` reads it back the same).
(3) The measure is the longest common prefix, in estimated tokens (`models.base.approx_tokens`), between a prompt and the best of the last few prompts of the same task: a
lower bound on what a radix cache could reuse, not a measurement of a server.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from vakeel_sahayak.models.base import approx_tokens

KEEP = 8  # earlier prompts kept per task


def sorted_keys(value: Any) -> Any:
    """The value with every dict's keys in sorted order (lists keep their order)."""
    if isinstance(value, dict):
        return {k: sorted_keys(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, list):
        return [sorted_keys(v) for v in value]
    return value


def prefix_ordered(data: dict[str, Any]) -> dict[str, Any]:
    """The INPUT data in the prefix-friendly order: `corpus` first (public, shared across cases), the other keys sorted, `case` last (private, differs per case)."""
    rest = sorted(k for k in data if k not in ("corpus", "case"))
    order = [k for k in ("corpus", *rest, "case") if k in data]
    return {k: sorted_keys(data[k]) for k in order}


class PrefixMeter:
    """Counts how much of each prompt repeats an earlier prompt of the same task (the S14d signal `shared_prefix_tokens`)."""

    def __init__(self) -> None:
        self._recent: dict[str, list[str]] = {}
        self._lock = threading.Lock()
        self.calls = self.prompt_tokens = self.shared_prefix_tokens = 0

    def observe(self, task: str, prompt: str) -> int:
        """Record a prompt; returns the tokens of its longest prefix shared with an earlier prompt of the task (0 for the first)."""
        with self._lock:
            recent = self._recent.setdefault(task, [])
            best = max((len(os.path.commonprefix([prompt, p])) for p in recent), default=0)
            shared = approx_tokens(prompt[:best]) if best else 0
            total = approx_tokens(prompt)
            recent.append(prompt)
            del recent[:-KEEP]
            self.calls += 1
            self.prompt_tokens += total
            self.shared_prefix_tokens += shared
            return shared

    def stats(self) -> dict[str, float]:
        """calls, prompt_tokens, shared_prefix_tokens and their share (0.0 without calls)."""
        with self._lock:
            return {"calls": float(self.calls), "prompt_tokens": float(self.prompt_tokens), "shared_prefix_tokens": float(self.shared_prefix_tokens),
                    "shared_share": self.shared_prefix_tokens / self.prompt_tokens if self.prompt_tokens else 0.0}
