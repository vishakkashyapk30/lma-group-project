"""Built-in concordance seed so the law tools work offline: only rows the plan states (plan §2, §5.4).

- IPC 420 <-> BNS 318(4): the plan's recodification example (§5.4) and the dossier example (§7.1).
- The ten-row CrPC <-> BNSS bail table is read from configs/bail_sections.yaml (see crpc_bnss_table.py).

The IPC <-> BNS edge type is SAME (carried over unchanged) because §5.4 says a BNS 318(4) case retrieves IPC 420
precedents; that reading and the bail-table edge types still need the week-0 check against the bare acts.
"""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import ConcordanceEdgeType
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge

SEED_IPC_BNS_EDGES: list[ConcordanceEdge] = [
    ConcordanceEdge(old_ref="IPC 420", new_ref="BNS 318(4)", type=ConcordanceEdgeType.SAME, text_diff=None),
]
