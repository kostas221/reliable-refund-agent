"""The frozen held-out sets the final runner may name, and what judges each: its quality targets, its predictions, and
whether it has a target at all. The final runner (refund_agent/evaluation/final.py) runs a set by its name and records
the name in the run's manifest; the report (refund_agent/evaluation/report.py) reads the name back, so a run is judged
by its own set's targets, or by none."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from refund_agent.policy import REPO_ROOT


@dataclass(frozen=True)
class HeldOutSet:
    split: str  # the scenarios' split, refund_agent.scenarios.SPLIT_DIRS
    targets: Path  # the quality targets, committed before the run
    predictions: Path  # the predictions, committed before the run
    prefix: str  # of the run's folder
    spent: str = ""  # why the set may no longer run, if it may not
    targeted: bool = True  # False: run and reported apart, with no target
    configurations: str = "final"  # which group of configurations runs it (refund_agent/evaluation/final.py)


SETS = {
    "held_out": HeldOutSet(
        "held_out",
        REPO_ROOT / "docs" / "quality-targets.md",
        REPO_ROOT / "docs" / "final" / "predictions.md",
        "final",
        spent="v1's held-out set is spent: its final evaluation ran on 2026-10-19 (runs/final-20261019T201207Z)",
    ),
    "held_out_v1_1": HeldOutSet(
        "held_out_v1_1",
        REPO_ROOT / "docs" / "held-out-v1.1" / "quality-targets.md",
        REPO_ROOT / "docs" / "held-out-v1.1" / "predictions.md",
        "final-v1.1",
        spent="v1.1's held-out set is spent: its final evaluation ran on 2026-10-26 (runs/final-v1.1-20261026T125831Z)",
    ),
    # v1.2: the 19 held-out scenarios, and the stress scenarios run beside them and reported apart, with no target
    # (plan change log, 2026-10-30). One file holds the targets and one the predictions of both.
    "held_out_v1_2": HeldOutSet(
        "held_out_v1_2",
        REPO_ROOT / "docs" / "held-out-v1.2" / "quality-targets.md",
        REPO_ROOT / "docs" / "held-out-v1.2" / "predictions.md",
        "final-v1.2",
        spent="v1.2's held-out set is spent: its final evaluation ran on 2026-10-30 (runs/final-v1.2-20261030T170445Z)",
    ),
    "stress_v1_2": HeldOutSet(
        "stress_v1_2",
        REPO_ROOT / "docs" / "held-out-v1.2" / "quality-targets.md",
        REPO_ROOT / "docs" / "held-out-v1.2" / "predictions.md",
        "stress-v1.2",
        targeted=False,
        spent="v1.2's stress set is spent: it ran on 2026-10-30 (runs/stress-v1.2-20261030T174734Z)",
    ),
    # v1.3: the 39 scenarios that compare the product's model with an Anthropic model (docs/held-out-v1.3/protocol.md),
    # run by the comparison's two configurations, not the final evaluations' three. Spent since its copies D90 to D128
    # joined development (plan change log, 2026-11-04).
    "held_out_v1_3": HeldOutSet(
        "held_out_v1_3",
        REPO_ROOT / "docs" / "held-out-v1.3" / "quality-targets.md",
        REPO_ROOT / "docs" / "held-out-v1.3" / "predictions.md",
        "comparison-v1.3",
        spent="v1.3's comparison set is spent: it ran on 2026-11-03 (runs/comparison-v1.3-20261103T155348Z)",
        configurations="comparison",
    ),
}
# v1's final run of 2026-10-19 recorded no set name in its manifest: it ran v1's held-out set.
UNNAMED = "held_out"
