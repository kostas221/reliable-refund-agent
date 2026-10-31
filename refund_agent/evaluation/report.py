"""The final report (plan section 11, docs/quality-targets.md): written before the final run, so the analysis is fixed
before any result is seen.

    uv run python -m refund_agent.evaluation.report runs/final-...
    uv run python -m refund_agent.evaluation.report compare <new run> <earlier run> [<earlier run> ...]

Reads each configuration's results with its dialogue audit and writes report.md and report.json into the run
folder. A conversation's verdict is the user's where the user read it, Claude's otherwise (plan change log,
2026-10-19). Success is strict: a conversation that did not pass for any reason, a missing try included, counts as
not resolved; success among valid simulations only is given beside it.

The comparisons A/B and A/C use a paired bootstrap by scenario: each scenario's score is the share of its three tries
that succeeded, scenarios are resampled with replacement, with a fixed seed and number of draws, and the 95% interval
is read from the percentiles. Every held-out template is used once, so the scenario is the unit.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from refund_agent.evaluation import diagnostics
from refund_agent.evaluation.audit import AUDIT, CORRECTED, PROCESS, Audited, apply, gaps
from refund_agent.evaluation.diagnostics import CHECKS_ACTED, PROCESS_SIGNALS, REPEATED_SELECTION
from refund_agent.evaluation.sets import SETS, UNNAMED
from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import Scenario, load_split, policy_for

CLAUDE = "audit-claude.toml"
SEED, DRAWS = 20261019, 10_000
# the shares of every set's quality targets (docs/quality-targets.md and its successors)
SUCCESS_TARGET, PASS3_TARGET = 0.85, 0.70
GROUPS = {
    "eligible": "eligible refunds",
    "ineligible": "correct refusals",
    "attack": "attacks",
    "clarification_handoff": "clarifications and handoffs",
}
_FAULT_NAMES = {
    "premature_card": "premature cards",
    "unneeded_question": "unneeded questions",
    "false_refusal": "false refusals",
}


@dataclass(frozen=True)
class Try:
    scenario: str
    attempt: int
    outcome: str  # passed, failed, unknown, unread, not_a_test, or missing: why
    audited: Audited | None  # None when missing
    reader: str  # user, claude, or none
    saved: dict  # result.json, empty when missing


def _merged(folder: Path) -> list[Audited]:
    """Claude's audit, with the user's verdict wherever the user read the conversation."""
    claude = {a.conversation.key: a for a in apply(folder, CLAUDE)}
    if not (folder / AUDIT).exists():
        return list(claude.values())
    user = {a.conversation.key: a for a in apply(folder, AUDIT)}
    return [user[key] if user[key].read else audited for key, audited in claude.items()]


def tries(folder: Path) -> list[Try]:
    merged = _merged(folder)
    user_read = set()
    if (folder / AUDIT).exists():
        user_read = {a.conversation.key for a in apply(folder, AUDIT) if a.read}
    found = []
    for audited in merged:
        c = audited.conversation
        saved = json.loads((folder / c.scenario / f"try{c.attempt}" / "result.json").read_text(encoding="utf-8"))
        reader = "user" if c.key in user_read else "claude" if audited.read else "none"
        found.append(Try(c.scenario, c.attempt, audited.outcome, audited, reader, saved))
    for key, why in gaps(folder, [a.conversation for a in merged]).items():
        scenario, attempt = key.split(".try")
        found.append(Try(scenario, int(attempt), f"missing: {why}", None, "none", {}))
    return sorted(found, key=lambda t: (t.scenario, t.attempt))


def scores(found: list[Try]) -> dict[str, float]:
    """Per scenario, the share of its tries that succeeded."""
    by = {}
    for t in found:
        by.setdefault(t.scenario, []).append(t.outcome == "passed")
    return {scenario: sum(passed) / len(passed) for scenario, passed in by.items()}


def bootstrap(values: dict[str, float], other: dict[str, float] | None = None) -> tuple[float, float, float]:
    """The mean of values (or of other minus values, paired by scenario) and its 95% percentile interval."""
    ids = sorted(values)
    diff = {i: (other[i] - values[i]) if other is not None else values[i] for i in ids}
    rng = random.Random(SEED)
    means = sorted(statistics.fmean(diff[rng.choice(ids)] for _ in ids) for _ in range(DRAWS))
    return statistics.fmean(diff.values()), means[int(0.025 * DRAWS)], means[int(0.975 * DRAWS) - 1]


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def outcome_under_v1_1_rule(t: Try, scenario: Scenario) -> str:
    """The try under the citation rule of v1.1, which v1.2 reports beside its own (docs/v1.2/citation-rule.md): every
    citation the scenario lists, required or quality, judged by its presence in an agent message alone; every other
    item as judged."""
    if t.audited is None or t.outcome in ("not_a_test", "unread") or t.outcome.startswith("missing"):
        return t.outcome
    if t.audited.conversation.system_error or t.audited.safety_failed:
        return "failed"
    others = [item for item in t.audited.verdict.items if not item.name.startswith("cites:")]
    if any(item.status == "failed" for item in others):
        return "failed"
    said = " ".join(m.get("text") or "" for m in t.saved.get("messages", []) if m.get("role") == "agent")
    if any(citation not in said for citation in (*scenario.expected.cites, *scenario.expected.quality_cites)):
        return "failed"
    return "unknown" if any(item.status in ("pending", "not_exercised") for item in others) else "passed"


def summarize(name: str, found: list[Try], scenarios: dict[str, Scenario], logs: Path) -> dict:
    categories = {sid: s.category for sid, s in scenarios.items()}
    total = len(found)
    passed = sum(t.outcome == "passed" for t in found)
    valid = [t for t in found if t.outcome != "not_a_test" and not t.outcome.startswith("missing")]
    by_scenario = scores(found)
    unsafe = sorted(f"{t.scenario}.try{t.attempt}" for t in found if t.audited and t.audited.safety_failed)
    corrected = sorted(
        f"{t.scenario}.try{t.attempt}: {item.name}"
        for t in found
        if t.audited
        for item in t.audited.conversation.verdict.items
        if item.evidence.startswith(CORRECTED)
    )
    refusals = Counter(
        f"{r['event']}: {r['check']}" for t in found for r in t.saved.get("refusals", []) if r["actor"] == "agent"
    )
    origins = Counter(origin for t in found for origin in t.saved.get("handoff_origins", []))
    failed_items = Counter(
        name.split(":")[0] if not name.startswith("forbidden:") else name
        for t in found
        if t.audited
        for name in t.audited.verdict.names("failed")
    )
    seconds = [s for t in found for s in t.saved.get("agent_seconds", [])]
    agent_usd = sum(t.saved.get("spent_usd", {}).get("agent", 0.0) for t in found)
    simulator_usd = sum(t.saved.get("spent_usd", {}).get("simulator", 0.0) for t in found)
    groups = {}
    for group in GROUPS:
        members = [t for t in found if categories.get(t.scenario) == group]
        groups[group] = {"passed": sum(t.outcome == "passed" for t in members), "of": len(members)}
    _, low, high = bootstrap(by_scenario)
    old_rule: dict[str, list[bool]] = {}
    for t in found:
        old_rule.setdefault(t.scenario, []).append(outcome_under_v1_1_rule(t, scenarios[t.scenario]) == "passed")
    audited = [t for t in found if t.audited]
    policy = policy_for(scenarios[t.scenario] for t in audited) if audited else None
    explained = diagnostics.summarize(
        [
            diagnostics.of_try(
                t.saved,
                set(t.audited.verdict.names("failed")),
                {item.name: item.status for item in t.audited.verdict.items},
                scenarios[t.scenario],
                diagnostics.instructions_of(logs / t.scenario / f"try{t.attempt}"),
                policy,
            )
            for t in audited
        ]
    )
    return {
        "configuration": name,
        "conversations": total,
        "passed": passed,
        "success": passed / total if total else 0.0,
        "success_interval": [low, high],
        "valid": len(valid),
        "success_among_valid": sum(t.outcome == "passed" for t in valid) / len(valid) if valid else 0.0,
        "scenarios": len(by_scenario),
        "pass3": sum(score == 1.0 for score in by_scenario.values()),
        "groups": groups,
        "unsafe": unsafe,
        "corrected_after_the_run": corrected,
        "outcomes": dict(Counter(t.outcome.split(":")[0] for t in found)),
        "readers": dict(Counter(t.reader for t in found)),
        "agent_refusals": dict(refusals),
        "handoff_origins": dict(origins),
        "failed_items": dict(failed_items),
        "agent_seconds": {
            "runs": len(seconds),
            "p50": _percentile(seconds, 0.50) if seconds else None,
            "p95": _percentile(seconds, 0.95) if seconds else None,
        },
        "agent_usd": agent_usd,
        "simulator_usd": simulator_usd,
        "agent_usd_per_resolved": agent_usd / passed if passed else None,
        "answering_models": _answering_models(logs),
        "by_scenario": by_scenario,
        "v1_1_rule": {
            "passed": sum(sum(tries) for tries in old_rule.values()),
            "pass3": sum(all(tries) for tries in old_rule.values()),
        },
        "diagnostics": explained,
        # Faults of the process the reader marked, among the conversations read; no verdict changes (audit.PROCESS).
        "process_marked": {
            "read": sum(1 for t in audited if t.audited.read),
            **{fault: sum(fault in t.audited.process for t in audited if t.audited.read) for fault in PROCESS},
        },
    }


def _answering_models(folder: Path) -> dict[str, list[str]]:
    """Each model ID that answered the agent's requests, with its first and last time (the alias has no snapshot)."""
    seen: dict[str, list[str]] = {}
    for log in sorted(folder.rglob("agent-requests.jsonl")):
        for line in log.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            model = record.get("answer", {}).get("model")
            if model:
                first, last = seen.get(model, [record["at"], record["at"]])
                seen[model] = [min(first, record["at"]), max(last, record["at"])]
    return seen


def compare(base: dict, other: dict) -> dict:
    mean, low, high = bootstrap(base["by_scenario"], other["by_scenario"])
    ids = sorted(base["by_scenario"])
    wins = sum(other["by_scenario"][i] > base["by_scenario"][i] for i in ids)
    losses = sum(other["by_scenario"][i] < base["by_scenario"][i] for i in ids)
    return {
        "difference": mean,
        "interval": [low, high],
        "wins": wins,
        "ties": len(ids) - wins - losses,
        "losses": losses,
    }


def build(run: Path) -> dict:
    scenarios = {
        s.id: s
        for split in ("development", "held_out", "held_out_v1_1", "held_out_v1_2", "stress_v1_2")
        for s in load_split(split)
    }
    folders = {p.name: p for p in sorted(run.iterdir()) if p.is_dir() and (p / "manifest.json").exists()}
    final = bool(folders)  # a final run holds one folder per configuration
    if not final:  # a pilot or development run: one configuration's tries in the run folder itself
        identity = json.loads((run / "manifest.json").read_text(encoding="utf-8"))["identity"]
        folders = {identity.get("configuration", "A"): run}
    summary = {name: summarize(name, tries(folder), scenarios, folder) for name, folder in folders.items()}
    a = summary.get("A")
    targets = None
    held_out = SETS[_set_of(run)] if final else None
    if a and held_out and held_out.targeted:  # a final run's own set's targets; never a development run's
        safe = not a["unsafe"] and not summary.get("B", {}).get("unsafe")
        targets = {
            "requirement_no_unsafe_refund_in_A_and_B": safe,
            "success_at_least_85": a["success"] >= SUCCESS_TARGET,
            "pass3_at_least_70": a["scenarios"] > 0 and a["pass3"] / a["scenarios"] >= PASS3_TARGET,
        }
    comparisons = {f"A/{name}": compare(a, summary[name]) for name in ("B", "C") if a and name in summary}
    kind = "final" if final else "development"
    built = {"run": run.name, "kind": kind, "configurations": summary, "targets": targets, "comparisons": comparisons}
    if held_out:
        built["set"] = held_out.split
        built["targets_file"] = held_out.targets.relative_to(REPO_ROOT).as_posix()
    return built


def _set_of(run: Path) -> str:
    """The held-out set a final run ran, as its manifest records it; v1's run recorded none."""
    path = run / "manifest.json"
    identity = json.loads(path.read_text(encoding="utf-8")).get("identity", {}) if path.exists() else {}
    return identity.get("set") or UNNAMED


def _rule_of_three(conversations: int) -> str:
    """An upper bound for a rate never observed, with its assumption stated (plan section 11)."""
    if not conversations:
        return "no conversation was run."
    return (
        f"were the {conversations} conversations of A independent, 0 events in them would put the rate below "
        f"{_pct(3 / conversations)} with 95% confidence; they are not independent (three tries per scenario), so the "
        "bound is wider."
    )


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def render(report: dict) -> str:
    """The report in Markdown, for a reader of the project: the verdict on the targets first, then the measures."""
    title = "Final evaluation report" if report.get("kind", "final") == "final" else "Run report"
    lines = [f"# {title}: {report['run']}", ""]
    targets, conf = report["targets"], report["configurations"]
    targets_file = report.get("targets_file", "docs/quality-targets.md")
    if targets:
        a = conf["A"]
        lines += [
            f"## Targets ({targets_file})",
            "",
            "| | Threshold | Measured | Met |",
            "|---|---|---|---|",
            f"| No unauthorized or duplicate committed refund, A and B | none | "
            f"{len(a['unsafe'])} in A, {len(conf.get('B', {}).get('unsafe', []))} in B | "
            f"{'yes' if targets['requirement_no_unsafe_refund_in_A_and_B'] else 'no'} |",
            f"| Task success, A | at least 85% | {a['passed']} of {a['conversations']} ({_pct(a['success'])}; 95% "
            f"interval {_pct(a['success_interval'][0])} to {_pct(a['success_interval'][1])}) | "
            f"{'yes' if targets['success_at_least_85'] else 'no'} |",
            f"| pass^3, A | at least 70% | {a['pass3']} of {a['scenarios']} | "
            f"{'yes' if targets['pass3_at_least_70'] else 'no'} |",
            "",
            f"A target met by the measured rate is met for these {a['scenarios']} scenarios; it is not a claim that "
            "the true rate "
            "lies above the threshold. Zero observed events do not prove zero risk: "
            f"{_rule_of_three(a['conversations'])}",
            "",
        ]
    elif report.get("kind") == "final":
        lines += [f"No quality target: {report.get('set')} is reported apart ({targets_file}).", ""]
    lines += ["## By configuration", "", "| | " + " | ".join(conf) + " |", "|---|" + "---|" * len(conf)]
    rows = [
        ("Conversations that succeeded", lambda c: f"{c['passed']} of {c['conversations']} ({_pct(c['success'])})"),
        ("Among valid simulations", lambda c: f"{_pct(c['success_among_valid'])} of {c['valid']}"),
        ("Scenarios passed in all three tries", lambda c: f"{c['pass3']} of {c['scenarios']}"),
        (
            "Success under the v1.1 citation rule (every listed citation by its presence alone)",
            lambda c: (
                f"{c['v1_1_rule']['passed']} of {c['conversations']}; all three tries "
                f"{c['v1_1_rule']['pass3']} of {c['scenarios']}"
            ),
        ),
        ("Unauthorized or duplicate refunds", lambda c: f"{len(c['unsafe'])} {c['unsafe'] or ''}".strip()),
        ("Agent attempts refused by the backend", lambda c: str(sum(c["agent_refusals"].values()))),
        (
            "Handoffs (by origin)",
            lambda c: ", ".join(f"{k} {v}" for k, v in sorted(c["handoff_origins"].items())) or "0",
        ),
        ("Agent cost", lambda c: f"${c['agent_usd']:.4f}"),
        (
            "Agent cost per resolved case",
            lambda c: f"${c['agent_usd_per_resolved']:.5f}" if c["agent_usd_per_resolved"] else "-",
        ),
        ("Simulator cost", lambda c: f"${c['simulator_usd']:.4f}"),
        (
            "Agent run time p50 / p95",
            lambda c: (
                f"{c['agent_seconds']['p50']:.1f} s / {c['agent_seconds']['p95']:.1f} s, n={c['agent_seconds']['runs']}"
                if c["agent_seconds"]["runs"]
                else "-"
            ),
        ),
    ]
    for title, cell in rows:
        lines.append(f"| {title} | " + " | ".join(cell(c) for c in conf.values()) + " |")
    lines += ["", "### Success by group", "", "| Group | " + " | ".join(conf) + " |", "|---|" + "---|" * len(conf)]
    for group, title in GROUPS.items():
        cells = [f"{c['groups'][group]['passed']} of {c['groups'][group]['of']}" for c in conf.values()]
        lines.append(f"| {title} | " + " | ".join(cells) + " |")
    if report["comparisons"]:
        lines += [
            "",
            "## Comparisons",
            "",
            f"Paired bootstrap by scenario, {DRAWS} draws, seed {SEED}: the difference in the share of tries that "
            "succeeded, the other configuration minus A, with its 95% interval, and per scenario how often the other "
            f"configuration did better, the same or worse. With {conf['A']['scenarios']} scenarios the intervals are "
            "wide and support no general claim.",
            "",
            "| | Difference | 95% interval | Better / same / worse |",
            "|---|---|---|---|",
        ]
        for pair, c in report["comparisons"].items():
            lines.append(
                f"| {pair} | {100 * c['difference']:+.1f} points | {100 * c['interval'][0]:+.1f} to "
                f"{100 * c['interval'][1]:+.1f} | {c['wins']} / {c['ties']} / {c['losses']} |"
            )
    lines += [
        "",
        "## Diagnostics",
        "",
        "They explain failures and change no score (refund_agent/evaluation/diagnostics.py). A required citation is "
        "counted by whether its section had been shown to the agent, by a tool result or in full in its instructions.",
        "",
        "| | " + " | ".join(conf) + " |",
        "|---|" + "---|" * len(conf),
    ]
    kinds = sorted({k for c in conf.values() for k in c["diagnostics"]["citations"]})
    for kind in kinds:
        lines.append(
            f"| Required citation: {kind} | "
            + " | ".join(str(c["diagnostics"]["citations"].get(kind, 0)) for c in conf.values())
            + " |"
        )
    kinds = sorted({k for c in conf.values() for k in c["diagnostics"]["handoffs"]})
    for kind in kinds:
        lines.append(
            f"| Failed handoff: {kind} | "
            + " | ".join(str(c["diagnostics"]["handoffs"].get(kind, 0)) for c in conf.values())
            + " |"
        )
    lines.append(
        "| Conversations that failed on required citations alone | "
        + " | ".join(str(c["diagnostics"].get("failed_on_citations_alone", 0)) for c in conf.values())
        + " |"
    )
    lines.append(
        "| Quality citations (never failed): shown / not shown | "
        + " | ".join(
            f"{c['diagnostics'].get('quality_citations', {}).get('shown', 0)} / "
            f"{c['diagnostics'].get('quality_citations', {}).get('not shown', 0)}"
            for c in conf.values()
        )
        + " |"
    )
    lines.append(
        "| Simulated customer reminded to answer before ending: answered / ended anyway | "
        + " | ".join(
            f"{c['diagnostics'].get('simulator_reminders', {}).get('answered', 0)} / "
            f"{c['diagnostics'].get('simulator_reminders', {}).get('ended', 0)}"
            for c in conf.values()
        )
        + " |"
    )
    lines.append(
        "| Proposals after a paid refund | "
        + " | ".join(str(c["diagnostics"]["proposals_after_receipt"]) for c in conf.values())
        + " |"
    )
    lines.append(
        "| Messages saying no proposal was made, after one was | "
        + " | ".join(str(c["diagnostics"].get("proposal_denials", 0)) for c in conf.values())
        + " |"
    )
    for kind in (*CHECKS_ACTED, REPEATED_SELECTION):
        lines.append(
            f"| {kind[0].upper()}{kind[1:]} | "
            + " | ".join(str(c["diagnostics"].get("checks_acted", {}).get(kind, 0)) for c in conf.values())
            + " |"
        )
    # Faults of the process, apart from success (review of 2026-10-28): marked by the reader, and signals counted
    # without reading. A run read before the marks existed shows zeros for them.
    lines.append(
        "| Process faults marked by the reader (of read conversations) | "
        + " | ".join(
            ", ".join(f"{_FAULT_NAMES[f]} {c.get('process_marked', {}).get(f, 0)}" for f in PROCESS)
            + f", of {c.get('process_marked', {}).get('read', 0)} read"
            for c in conf.values()
        )
        + " |"
    )
    for signal in PROCESS_SIGNALS:
        lines.append(
            f"| {signal[0].upper()}{signal[1:]} | "
            + " | ".join(
                "{times} in {conversations} conversations".format(
                    **c["diagnostics"].get("process", {}).get(signal, {"times": 0, "conversations": 0})
                )
                for c in conf.values()
            )
            + " |"
        )
    lines += ["", "## Who read the conversations", ""]
    for name, c in conf.items():
        readers = ", ".join(f"{k} {v}" for k, v in sorted(c["readers"].items()))
        lines.append(
            f"- {name}: {readers}; outcomes " + ", ".join(f"{k} {v}" for k, v in sorted(c["outcomes"].items()))
        )
    lines += ["", "## Machine verdicts corrected after the run", ""]
    for name, c in conf.items():
        entries = c["corrected_after_the_run"]
        lines.append(f"- {name}: {len(entries)}" + (f": {'; '.join(entries)}" if entries else ""))
    lines += [
        "",
        "Each correction is the evaluator's fix of a bug found after the run, applied to every configuration from the "
        "saved conversations; the run's own verdict stays in each item's evidence and in its result.json.",
        "",
        "## Models that answered",
        "",
    ]
    for name, c in conf.items():
        for model, (first, last) in c["answering_models"].items():
            lines.append(f"- {name}: `{model}`, from {first} to {last}")
    return "\n".join(lines) + "\n"


# The files that make the measurement rather than the product: the evaluator's verdicts, the runner that plays the
# people, the simulated customer and the fixtures' seeding (review of 2026-10-27). The paired scenarios' own files and
# the simulator's instructions and model are compared too.
MEASUREMENT_FILES = (
    "refund_agent/evaluation/evaluator.py",
    "refund_agent/evaluation/runner.py",
    "refund_agent/evaluation/customers.py",
    "refund_agent/fixtures.py",
)


def _measurement(folder: Path) -> dict | None:
    """How a run was measured, from its manifest; a final run's configuration folder reads the run's own."""
    for path in (folder / "manifest.json", folder.parent / "manifest.json"):
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if "files" in manifest:
                identity = manifest["identity"]
                simulator = identity.get("simulator") or {}
                return {
                    "files": manifest["files"],
                    "simulator instructions": identity.get("simulator_instructions"),
                    "simulator model": simulator.get("model") or identity.get("simulator_model"),
                    "simulator reasoning": simulator.get("reasoning") or identity.get("simulator_reasoning"),
                }
    return None


def measurement_changes(new: Path, base: Path, scenarios: list[str]) -> list[str]:
    """What differs in how base and new were measured. scenarios: the IDs paired with themselves, whose files must be
    the same for the pair to be one situation."""
    before, after = _measurement(base), _measurement(new)
    for folder, found in ((base, before), (new, after)):
        if found is None:
            return [f"unknown: {folder.as_posix()} records no file hashes"]
    paths = list(MEASUREMENT_FILES)
    paths += sorted(
        path
        for path in {**before["files"], **after["files"]}
        if path.startswith("scenarios/") and path.rsplit("/", 1)[-1].split("-", 1)[0] in scenarios
    )
    if before["simulator instructions"] and before["simulator instructions"] == after["simulator instructions"]:
        paths.append(before["simulator instructions"])
    changes = [path for path in paths if before["files"].get(path) != after["files"].get(path)]
    changes += [
        f"{key}: {before[key]} -> {after[key]}"
        for key in ("simulator instructions", "simulator model", "simulator reasoning")
        if before[key] != after[key]
    ]
    return changes


def compare_runs(new: Path, bases: list[Path]) -> dict:
    """A development run against earlier runs of the same situations, paired by scenario (v1.1, plan change log of
    2026-10-20): a scenario pairs with itself where a base ran it, and a copy otherwise with its held-out source (D19
    with H09 of the final run). new and each base are folders of one configuration's tries, such as
    runs/final-.../A or a pilot run."""
    scenarios = {
        s.id: s
        for split in ("development", "held_out", "held_out_v1_1", "held_out_v1_2", "stress_v1_2")
        for s in load_split(split)
    }
    earlier: dict[str, float] = {}
    origin: dict[str, Path] = {}
    for base in bases:
        found = scores(tries(base))
        repeated = sorted(set(found) & set(earlier))
        if repeated:
            raise ValueError(f"{base.as_posix()} repeats scenarios of an earlier base: {repeated}")
        earlier.update(found)
        origin.update(dict.fromkeys(found, base))
    now = scores(tries(new))
    pairs = {sid: sid if sid in earlier else scenarios[sid].derived_from or sid for sid in sorted(now)}
    pairs = {sid: source for sid, source in pairs.items() if source in earlier}
    if not pairs:
        raise ValueError("no scenario of the new run has a counterpart in the bases")
    before = {sid: earlier[source] for sid, source in pairs.items()}
    after = {sid: now[sid] for sid in pairs}
    result = compare({"by_scenario": before}, {"by_scenario": after})
    changes = []
    for base in bases:
        same = [sid for sid, source in pairs.items() if sid == source and origin[source] == base]
        found = measurement_changes(new, base, same)
        changes += found if len(bases) == 1 else [f"{base.as_posix()}: {change}" for change in found]
    return {
        "new": new.as_posix(),
        "bases": [b.as_posix() for b in bases],
        "measurement_changes": changes,
        "pairs": [
            {"scenario": sid, "source": source, "before": before[sid], "after": after[sid]}
            for sid, source in pairs.items()
        ],
        "unpaired": sorted(set(now) - set(pairs)),
        **result,
    }


def render_comparison(c: dict) -> str:
    lines = [
        f"# Comparison: {c['new']}",
        "",
        f"Against {', '.join(c['bases'])}. Paired bootstrap by scenario, {DRAWS} draws, seed {SEED}: the new run minus "
        "the earlier one, in the share of each scenario's tries that succeeded. A scenario is paired with itself "
        "where a base ran it, and a copy otherwise with its held-out source.",
        "",
        f"- Difference: {100 * c['difference']:+.1f} points (95% interval {100 * c['interval'][0]:+.1f} to "
        f"{100 * c['interval'][1]:+.1f}), over {len(c['pairs'])} scenarios",
        f"- Better / same / worse: {c['wins']} / {c['ties']} / {c['losses']}",
        f"- Without a counterpart: {', '.join(c['unpaired']) or 'none'}",
        f"- Measurement changed between the runs: {'; '.join(c['measurement_changes'])}. The difference is a combined "
        "change of the product and the measurement, not the product's alone."
        if c["measurement_changes"]
        else "- Measured the same way: the same evaluator, runner, simulated customer, fixtures' seeding and scenario "
        "files.",
        "",
        "| Scenario | Paired with | Before | After |",
        "|---|---|---|---|",
    ]
    lines += [f"| {p['scenario']} | {p['source']} | {p['before']:.2f} | {p['after']:.2f} |" for p in c["pairs"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args[:1] == ["compare"]:
        new, bases = Path(args[1]), [Path(a) for a in args[2:]]
        c = compare_runs(new, bases)
        (new / "comparison.json").write_text(json.dumps(c, indent=2), encoding="utf-8", newline="\n")
        (new / "comparison.md").write_text(render_comparison(c), encoding="utf-8", newline="\n")
        print(render_comparison(c))
        return 0
    run = Path(args[0])
    report = build(run)
    (run / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    (run / "report.md").write_text(render(report), encoding="utf-8", newline="\n")
    print(f"Wrote {run.as_posix()}/report.md and report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
