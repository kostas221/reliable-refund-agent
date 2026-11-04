"""The final evaluation's command without network, key or database: what runs is fixed in the code, the dry run sends
nothing, and a run refuses to start until a set is named and is not spent, the set matches its freeze, the targets and
the predictions are committed, the tree is clean, a key is present, the prices were checked and the budget is within
the plan's limit. The manifest records which set ran."""

import json
from dataclasses import replace
from datetime import date

import anthropic
import openai
import pytest

from refund_agent.evaluation import final, manifest
from refund_agent.policy import REPO_ROOT
from refund_agent.scenarios import SPLIT_DIRS, FrozenError, load_split

V1_3 = final.SETS["held_out_v1_3"]  # as the runner has it, before a test stands in for it


@pytest.fixture(autouse=True)
def no_openai_client(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise AssertionError("a client of a model provider was created")

    monkeypatch.setattr(openai, "OpenAI", refuse)
    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    monkeypatch.setattr(final, "RUNS", tmp_path)
    # A set that may still run, with its targets and predictions written just before the run: no such set exists since
    # v1.3's was spent (2026-11-04), so v1.3's set stands in for one, unspent, and any committed file for its documents.
    protocol = REPO_ROOT / "docs" / "held-out-v1.3" / "protocol.md"
    stand_in = replace(V1_3, targets=protocol, predictions=protocol, spent="")
    monkeypatch.setitem(final.SETS, "held_out_v1_3", stand_in)
    monkeypatch.setattr(final, "paid_run", lambda *args: pytest.fail("a paid run started"))


def repository(monkeypatch, *, changed_file="", dirty_tree=""):
    """git as the guards see it: every file committed at 0123abcd, unless told otherwise."""

    def git(*args, **kwargs):
        if args[0] == "log":
            return "0123abcd"
        return dirty_tree if "--untracked-files=no" in args else changed_file

    monkeypatch.setattr(manifest, "git", git)


READY = ["--set", "held_out_v1_3", "--budget-usd", "5", "--prices-checked", "2026-10-19"]


class On19October(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 19)


@pytest.fixture
def ready(monkeypatch):
    repository(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    monkeypatch.setattr(final, "date", On19October)
    checked = []
    monkeypatch.setattr(final, "check_frozen", checked.append)  # the set is frozen only after the owner approves it
    return checked


def test_what_runs_is_fixed_in_the_code():
    assert {name: vars(setup) for name, setup in final.CONFIGURATIONS.items()} == {
        "A": {"model": "gpt-6-luna", "reasoning": "none", "configuration": "A"},
        "B": {"model": "gpt-6.1-sol", "reasoning": "low", "configuration": "A"},
        "C": {"model": "gpt-6-luna", "reasoning": "none", "configuration": "C"},
    }
    assert vars(final.SIMULATOR) == {"model": "gpt-6-luna", "reasoning": "low", "configuration": "A"}
    assert final.plan(["H02", "H01"])[:4] == [("H01", 1, "A"), ("H01", 1, "B"), ("H01", 1, "C"), ("H01", 2, "A")]
    assert len(final.plan([f"H{n:02d}" for n in range(1, 21)])) == 180


def test_the_comparison_runs_the_products_model_against_sonnet_with_every_check():
    # docs/held-out-v1.3/protocol.md, section 4: A is the product (Sol low), B the Anthropic model at effort low.
    assert {name: vars(setup) for name, setup in final.configurations_of("held_out_v1_3").items()} == {
        "A": {"model": "gpt-6.1-sol", "reasoning": "low", "configuration": "A"},
        "B": {"model": "claude-sonnet-5-5", "reasoning": "low", "configuration": "A"},
    }
    assert final.configurations_of("held_out_v1_2") is final.CONFIGURATIONS
    trials = final.plan(["H402", "H401"], tuple(final.configurations_of("held_out_v1_3")))
    assert trials[:3] == [("H401", 1, "A"), ("H401", 1, "B"), ("H401", 2, "A")]
    assert len(final.plan([f"H{n}" for n in range(401, 440)], ("A", "B"))) == 234


def test_the_dry_run_of_the_comparison_writes_both_first_requests_and_sends_nothing(tmp_path, capsys):
    assert final.main(["--dry-run"]) == 0  # the coming run's set by default
    folder = tmp_path / "final-dry-run"
    sol = json.loads((folder / "first-agent-request-A.json").read_text(encoding="utf-8"))
    sonnet = json.loads((folder / "first-agent-request-B.json").read_text(encoding="utf-8"))
    assert (sol["model"], sol["reasoning"]["effort"]) == ("gpt-6.1-sol", "low")
    assert (sonnet["model"], sonnet["output_config"]["effort"]) == ("claude-sonnet-5-5", "low")
    # One prompt and one set of tools, in each provider's form.
    assert sonnet["system"][0]["text"] == sol["instructions"]
    assert [tool["name"] for tool in sonnet["tools"]] == [tool["name"] for tool in sol["tools"]]
    d01 = next(s for s in load_split("development") if s.id == "D01")
    assert sol["input"][0]["content"] == d01.customer.opening_message  # never a held-out scenario's
    assert d01.customer.opening_message in json.dumps(sonnet["messages"])
    out = capsys.readouterr().out
    assert "nothing sent" in out
    assert "held_out_v1_3, 234 conversations" in out  # 39 scenarios, three tries, two configurations
    assert not (folder / "first-agent-request-C.json").exists()


def test_the_dry_run_writes_each_configurations_first_request_and_sends_nothing(tmp_path, capsys):
    assert final.main(["--dry-run", "--set", "held_out_v1_2"]) == 0  # the final evaluations' three configurations
    requests = {
        name: json.loads((tmp_path / "final-dry-run" / f"first-agent-request-{name}.json").read_text(encoding="utf-8"))
        for name in "ABC"
    }
    assert [(r["model"], r["reasoning"]["effort"]) for r in requests.values()] == [
        ("gpt-6-luna", "none"),
        ("gpt-6.1-sol", "low"),
        ("gpt-6-luna", "none"),
    ]
    same = [{k: v for k, v in r.items() if k not in ("model", "reasoning")} for r in requests.values()]
    assert same[0] == same[1] == same[2]  # one prompt and one set of tools for every configuration
    d01 = next(s for s in load_split("development") if s.id == "D01")
    assert requests["A"]["input"][0]["content"] == d01.customer.opening_message  # never a held-out scenario's
    out = capsys.readouterr().out
    assert "nothing sent" in out
    # The estimate counts the named set: 19 scenarios, three tries, three configurations.
    assert "held_out_v1_2, 171 conversations" in out


def test_one_dry_run_never_mixes_sets_of_different_configurations():
    with pytest.raises(ValueError, match="different configurations"):
        final.dry_run(("held_out_v1_2", "held_out_v1_3"))


def test_a_held_out_set_that_does_not_match_its_freeze_stops_the_run(ready, monkeypatch, capsys):
    def changed(directory):
        raise FrozenError("changed ['H401-three-delivered-orders-customer-keeps-initial-two-unit-card.toml']")

    monkeypatch.setattr(final, "check_frozen", changed)
    assert final.main(READY) == 1
    assert "H401-three-delivered-orders-customer-keeps-initial-two-unit-card.toml" in capsys.readouterr().out


def test_a_run_names_its_set(ready, capsys):
    assert final.main(READY[2:]) == 1
    expected = (
        "give --set with the held-out set to run: held_out, held_out_v1_1, held_out_v1_2, held_out_v1_3, stress_v1_2"
    )
    assert expected in capsys.readouterr().out


def test_v1s_set_is_spent(ready, capsys):
    assert final.main(["--set", "held_out", *READY[2:]]) == 1
    assert "v1's held-out set is spent" in capsys.readouterr().out
    assert ready == []  # refused before anything of that set was read


def test_v1_1s_set_is_spent(ready, capsys):
    assert final.main(["--set", "held_out_v1_1", *READY[2:]]) == 1
    assert "v1.1's held-out set is spent" in capsys.readouterr().out
    assert ready == []


@pytest.mark.parametrize(
    ("name", "said"),
    [
        ("held_out_v1_2", "v1.2's held-out set is spent: its final evaluation ran on 2026-10-30"),
        ("stress_v1_2", "v1.2's stress set is spent: it ran on 2026-10-30"),
    ],
)
def test_v1_2s_sets_are_spent(ready, capsys, name, said):
    assert final.main(["--set", name, *READY[2:]]) == 1
    assert said in capsys.readouterr().out
    assert ready == []


def test_v1_3s_comparison_set_is_spent(ready, monkeypatch, capsys):
    # Its 39 scenarios are development copies now (D90 to D128), run and tuned on: never held out again.
    monkeypatch.setitem(final.SETS, "held_out_v1_3", V1_3)
    assert final.main(READY) == 1
    assert "v1.3's comparison set is spent: it ran on 2026-11-03" in capsys.readouterr().out
    assert ready == []


@pytest.mark.parametrize(
    ("name", "folder", "count", "first"),
    [
        ("held_out_v1_2", "held-out-v1.2", 19, "H102"),
        ("stress_v1_2", "stress-v1.2", 8, "S01"),
        ("held_out_v1_3", "held-out-v1.3", 39, "H401"),
    ],
)
def test_the_manifest_records_the_set_and_its_freeze(monkeypatch, name, folder, count, first):
    monkeypatch.setattr(final, "file_sha256", lambda path: f"sha256 of {path.parent.name}/{path.name}")
    scenarios = {s.id: s for s in load_split(name)}
    record = final.identity(scenarios, {}, date(2026, 10, 19), name)
    assert (record["set"], record["frozen_sha256"]) == (name, f"sha256 of {folder}/FROZEN")
    assert len(record["scenarios"]) == count and first in record["scenarios"]
    names = list(final.configurations_of(name))
    assert list(record["configurations"]) == names
    assert record["order"] == f"for each scenario, for each try: {', '.join(names)}"


def test_the_targets_and_the_predictions_must_be_committed(ready, monkeypatch, capsys):
    repository(monkeypatch, changed_file=" M docs/held-out-v1.3/protocol.md")
    assert final.main(READY) == 1
    assert "commit docs/held-out-v1.3/protocol.md first" in capsys.readouterr().out


def test_the_tree_must_be_clean(ready, monkeypatch, capsys):
    repository(monkeypatch, dirty_tree=" M refund_agent/agent/tools.py")
    assert final.main(READY) == 1
    assert "one identified revision" in capsys.readouterr().out


@pytest.mark.parametrize("key", ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"])
def test_every_key_the_comparison_needs_must_be_present(ready, monkeypatch, capsys, key):
    monkeypatch.delenv(key, raising=False)
    assert final.main(READY) == 1
    assert f"no {key}" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        (["--budget-usd", "5"], "--prices-checked"),
        (["--budget-usd", "5", "--prices-checked", "2026-10-20"], "--prices-checked"),  # tomorrow
        (["--prices-checked", "2026-10-19"], "--budget-usd"),
        (["--prices-checked", "2026-10-19", "--budget-usd", "16"], "at most $15"),
        (["--prices-checked", "2026-10-19", "--budget-usd", "0"], "above 0"),
    ],
)
def test_prices_must_be_checked_and_the_budget_within_the_plans_limit(ready, capsys, options, reason):
    assert final.main(["--set", "held_out_v1_3", *options]) == 1
    assert reason in capsys.readouterr().out


def test_when_everything_is_ready_the_run_starts_with_the_commits_it_rests_on(ready, monkeypatch):
    started = []
    monkeypatch.setattr(
        final, "paid_run", lambda args, scenarios, commits: started.append((len(scenarios), commits)) or 0
    )
    assert final.main(READY) == 0
    assert started == [(39, {"targets_commit": "0123abcd", "predictions_commit": "0123abcd"})]
    assert ready == [SPLIT_DIRS["held_out_v1_3"]]  # the freeze checked is the named set's
    assert final.SETS["held_out_v1_3"].prefix == "comparison-v1.3"
