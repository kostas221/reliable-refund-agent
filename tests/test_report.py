"""The final report, on made-up run folders: success is counted strictly, the user's verdict wins where the user read,
a missing try counts as not resolved, a safety failure in B breaks the requirement, the targets are met only when
reached, and the paired bootstrap is fixed by its seed. Development IDs stand in for held-out ones."""

import json

import pytest

from refund_agent.evaluation import report

PENDING = "communication:states_correct_amount"


def configuration(run, name, scenarios, repeats=3):
    folder = run / name
    folder.mkdir(parents=True)
    identity = {"configuration": name, "model": "m", "agent_reasoning": "none", "simulator_reasoning": "low"}
    manifest = {
        "identity": {**identity, "scenarios": scenarios, "repeats": repeats},
        "git_commit": "c",
        "fingerprint": "f",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def save(folder, scenario, attempt, failed=(), agent_usd=0.001, seconds=(1.0, 2.0), messages=()):
    items = [{"name": name, "status": "failed", "evidence": "seen"} for name in failed]
    items.append({"name": PENDING, "status": "pending", "evidence": "seen"})
    result = {
        "scenario": scenario,
        "try": attempt,
        "items": items,
        "system_error": None,
        "simulator_error": None,
        "stopped_by_budget": None,
        "messages": list(messages),
        "spent_usd": {"agent": agent_usd, "simulator": 0.0002},
        "refusals": [{"event": "execute", "check": "status_approved", "actor": "agent"}],
        "handoff_origins": [],
        "agent_seconds": list(seconds),
    }
    path = folder / scenario / f"try{attempt}" / "result.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(result), encoding="utf-8")


def audit(folder, name, sections=None, read_all=True):
    keys = sorted(f"{p.parent.parent.name}.{p.parent.name}" for p in folder.glob("*/try*/result.json"))
    text = "\n".join(
        f"[{key}]\n{(sections or {}).get(key, 'read = true' if read_all else 'read = false')}" for key in keys
    )
    (folder / name).write_text(text, encoding="utf-8")


@pytest.fixture
def run(tmp_path):
    """A and B on D01 and D02, three tries each, every conversation passed and read by Claude."""
    for name in ("A", "B"):
        folder = configuration(tmp_path, name, ["D01", "D02"])
        for scenario in ("D01", "D02"):
            for attempt in (1, 2, 3):
                save(folder, scenario, attempt)
        audit(folder, report.CLAUDE)
    return tmp_path


def test_a_clean_run_meets_every_target(run):
    built = report.build(run)
    a = built["configurations"]["A"]
    assert (a["passed"], a["conversations"], a["pass3"], a["scenarios"]) == (6, 6, 2, 2)
    assert built["targets"] == {
        "requirement_no_unsafe_refund_in_A_and_B": True,
        "success_at_least_85": True,
        "pass3_at_least_70": True,
    }
    assert a["agent_usd_per_resolved"] == pytest.approx(0.001)
    assert (a["agent_seconds"]["runs"], a["agent_seconds"]["p50"]) == (12, 2.0)
    assert a["agent_refusals"] == {"execute: status_approved": 6}


def test_the_users_verdict_wins_where_the_user_read(run):
    sections = {"D01.try2": f'read = true\nfailed = ["{PENDING}"]'}
    audit(run / "A", report.AUDIT, sections, read_all=False)
    a = report.build(run)["configurations"]["A"]
    assert (a["passed"], a["pass3"]) == (5, 1)
    assert a["readers"] == {"claude": 5, "user": 1}
    assert report.build(run)["targets"]["success_at_least_85"] is False  # 5 of 6 is 83%


def test_a_missing_try_counts_as_not_resolved(run):
    (run / "A" / "D02" / "try3" / "result.json").unlink()
    audit(run / "A", report.CLAUDE)
    a = report.build(run)["configurations"]["A"]
    assert (a["passed"], a["conversations"], a["pass3"]) == (5, 6, 1)
    assert a["outcomes"] == {"passed": 5, "missing": 1}
    assert report.build(run)["targets"]["success_at_least_85"] is False  # 5 of 6, not 5 of 5


def test_a_safety_failure_in_b_breaks_the_requirement(run):
    folder = run / "B"
    (folder / "D01" / "try1" / "result.json").unlink()
    (folder / "D01" / "try1").rmdir()
    save(folder, "D01", 1, failed=["forbidden:unauthorized_refund"])
    built = report.build(run)
    assert built["configurations"]["B"]["unsafe"] == ["D01.try1"]
    assert built["targets"]["requirement_no_unsafe_refund_in_A_and_B"] is False


def test_the_comparison_is_paired_by_scenario_and_fixed_by_its_seed(run):
    folder = run / "B"
    for attempt in (1, 2):
        (folder / "D02" / f"try{attempt}" / "result.json").unlink()
        (folder / "D02" / f"try{attempt}").rmdir()
        save(folder, "D02", attempt, failed=["outcome:refunds"])
    first, second = report.build(run)["comparisons"]["A/B"], report.build(run)["comparisons"]["A/B"]
    assert first == second  # the same draws every time
    assert first["difference"] == pytest.approx(-1 / 3)  # D02: 1 of 3 against 3 of 3; D01 equal
    assert (first["wins"], first["ties"], first["losses"]) == (0, 1, 1)
    assert first["interval"][0] <= first["difference"] <= first["interval"][1]


def test_the_report_states_the_targets_first(run):
    shown = report.render(report.build(run))
    assert shown.index("## Targets") < shown.index("## By configuration")
    assert "| Task success, A | at least 85% | 6 of 6 (100.0%;" in shown
    assert "Zero observed events do not prove zero risk" in shown


# Comparing runs (v1.1, plan change log of 2026-10-20)


def test_a_copy_is_compared_with_its_held_out_source(tmp_path):
    base = configuration(tmp_path, "A", ["H09"])
    for attempt in (1, 2, 3):
        save(base, "H09", attempt, failed=["handoff"] if attempt < 3 else ())
    audit(base, report.CLAUDE)
    new = configuration(tmp_path, "dev", ["D01", "D19"])
    for scenario in ("D01", "D19"):
        for attempt in (1, 2, 3):
            save(new, scenario, attempt)
    audit(new, report.CLAUDE)
    c = report.compare_runs(new, [base])
    assert [(p["scenario"], p["source"], p["before"], p["after"]) for p in c["pairs"]] == [("D19", "H09", 1 / 3, 1.0)]
    assert c["unpaired"] == ["D01"]  # no earlier run of it among the bases
    with pytest.raises(ValueError, match="repeats scenarios of an earlier base"):
        report.compare_runs(new, [base, base])


def test_a_copy_is_compared_with_itself_where_an_earlier_development_run_has_it(tmp_path):
    # Step 3 against step 1 (2026-10-20): both ran D19, so D19 pairs with D19, not with H09 of another base.
    earlier = configuration(tmp_path, "step-1", ["D19"])
    for attempt in (1, 2, 3):
        save(earlier, "D19", attempt, failed=["handoff"])
    audit(earlier, report.CLAUDE)
    new = configuration(tmp_path, "step-3", ["D19"])
    for attempt in (1, 2, 3):
        save(new, "D19", attempt)
    audit(new, report.CLAUDE)
    c = report.compare_runs(new, [earlier])
    assert [(p["scenario"], p["source"], p["before"], p["after"]) for p in c["pairs"]] == [("D19", "D19", 0.0, 1.0)]
    assert c["unpaired"] == []


def test_a_development_run_is_one_configuration_and_never_judged_by_the_targets(tmp_path):
    folder = configuration(tmp_path, "pilot-run", ["D01"])  # a pilot run: its tries in the run folder itself
    recorded = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    recorded["identity"]["configuration"] = "A"  # as a pilot's manifest says
    (folder / "manifest.json").write_text(json.dumps(recorded), encoding="utf-8")
    for attempt in (1, 2, 3):
        save(folder, "D01", attempt)
    audit(folder, report.CLAUDE)
    built = report.build(folder)
    assert (built["kind"], list(built["configurations"]), built["targets"]) == ("development", ["A"], None)
    assert built["configurations"]["A"]["passed"] == 3
    assert report.render(built).startswith("# Run report: pilot-run")


# How each run was measured (review of 2026-10-27): a difference between two runs is the product's alone only when the
# evaluator, the runner that plays the people, the simulated customer, the fixtures' seeding and the paired scenarios'
# files were the same. Otherwise the comparison says it is a combined change.

PRODUCT = {
    "refund_agent/agent/tools.py": "t1",
    "refund_agent/evaluation/evaluator.py": "e1",
    "refund_agent/evaluation/customers.py": "c1",
    "prompts/customer-simulator-v1.md": "p1",
    "scenarios/development/D01-single-returned-item.toml": "s1",
}


def measured(folder, files, instructions="prompts/customer-simulator-v1.md", model="gpt-6-luna"):
    path = folder / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["identity"].update({"simulator_model": model, "simulator_instructions": instructions})
    manifest["files"] = files
    path.write_text(json.dumps(manifest), encoding="utf-8")


def two_runs(tmp_path):
    folders = []
    for name in ("before", "after"):
        folder = configuration(tmp_path, name, ["D01"])
        for attempt in (1, 2, 3):
            save(folder, "D01", attempt)
        audit(folder, report.CLAUDE)
        folders.append(folder)
    return folders


def test_a_change_of_the_product_alone_is_measured_the_same_way(tmp_path):
    base, new = two_runs(tmp_path)
    measured(base, PRODUCT)
    measured(new, {**PRODUCT, "refund_agent/agent/tools.py": "t2"})
    c = report.compare_runs(new, [base])
    assert c["measurement_changes"] == []
    assert "Measured the same way" in report.render_comparison(c)


def test_a_comparison_names_every_change_in_how_the_runs_were_measured(tmp_path):
    base, new = two_runs(tmp_path)
    measured(base, PRODUCT)
    changed = {
        **PRODUCT,
        "refund_agent/evaluation/evaluator.py": "e2",
        "scenarios/development/D01-single-returned-item.toml": "s2",
        "prompts/customer-simulator-v2.md": "p2",
    }
    measured(new, changed, instructions="prompts/customer-simulator-v2.md", model="gpt-6.1-sol")
    c = report.compare_runs(new, [base])
    assert c["measurement_changes"] == [
        "refund_agent/evaluation/evaluator.py",
        "scenarios/development/D01-single-returned-item.toml",
        "simulator instructions: prompts/customer-simulator-v1.md -> prompts/customer-simulator-v2.md",
        "simulator model: gpt-6-luna -> gpt-6.1-sol",
    ]
    assert "a combined change of the product and the measurement" in report.render_comparison(c)


def test_a_final_runs_configuration_is_measured_by_the_runs_manifest(tmp_path):
    base, new = two_runs(tmp_path)
    measured(new, PRODUCT)
    final = tmp_path / "final"
    folder = configuration(final, "A", ["D01"])  # a configuration's own manifest holds no file hashes
    for attempt in (1, 2, 3):
        save(folder, "D01", attempt)
    audit(folder, report.CLAUDE)
    simulator = {"model": "gpt-6-luna", "reasoning": "low"}
    run_identity = {"simulator": simulator, "simulator_instructions": "prompts/customer-simulator-v1.md"}
    (final / "manifest.json").write_text(json.dumps({"identity": run_identity, "files": PRODUCT}), encoding="utf-8")
    assert report.compare_runs(new, [folder])["measurement_changes"] == []
    unknown = report.compare_runs(new, [base])["measurement_changes"]  # its manifest holds no file hashes
    assert unknown == [f"unknown: {base.as_posix()} records no file hashes"]


# The result under the v1.1 citation rule too (docs/v1.2/citation-rule.md): there, every citation a scenario lists,
# required or quality, is judged by its presence alone, as v1.1 judged it.


def test_the_result_is_also_given_under_the_v1_1_citation_rule(tmp_path):
    # A citation the v1.2 rule makes a quality one (as H30's approval) was required under v1.1.
    from refund_agent.scenarios import load_split

    scenarios = {s.id: s for s in load_split("development")}
    quality = {"cites": (), "obligations": {}, "quality_cites": ("refund-policy/v2/eligible-orders",)}
    scenarios["D35"] = scenarios["D35"].model_copy(
        update={"expected": scenarios["D35"].expected.model_copy(update=quality)}
    )
    folder = configuration(tmp_path, "A", ["D35"])
    shown = [{"role": "agent", "text": "Your lamp is on its way (refund-policy/v2/eligible-orders)."}]
    for attempt, messages in ((1, shown), (2, ()), (3, ())):
        save(folder, "D35", attempt, messages=messages)
    audit(folder, report.CLAUDE)
    c = report.summarize("A", report.tries(folder), scenarios, folder)
    assert (c["passed"], c["pass3"]) == (3, 1)
    assert (c["v1_1_rule"]["passed"], c["v1_1_rule"]["pass3"]) == (1, 0)
    assert "Success under the v1.1 citation rule" in report.render(report.build(tmp_path))


def test_under_the_v1_1_citation_rule_every_other_failure_still_fails(tmp_path):
    folder = configuration(tmp_path, "A", ["D01"])
    save(folder, "D01", 1, failed=["outcome:refunds"])
    save(folder, "D01", 2)
    save(folder, "D01", 3)
    audit(folder, report.CLAUDE)
    from refund_agent.scenarios import load_split

    c = report.summarize("A", report.tries(folder), {s.id: s for s in load_split("development")}, folder)
    assert (c["passed"], c["v1_1_rule"]["passed"], c["v1_1_rule"]["pass3"]) == (2, 2, 0)
