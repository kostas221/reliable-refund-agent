"""The refund policy has one controlled source, and a broken source fails on load."""

import tomllib

import pytest
from pydantic import ValidationError

from refund_agent import policy as policy_module
from refund_agent.fixtures import seed
from refund_agent.policy import POLICY_PATH, RENDERED_PATH, Policy, load_policy, load_policy_version, render_markdown
from refund_agent.scenarios import load_split


def raw_policy() -> dict:
    return tomllib.loads(POLICY_PATH.read_text(encoding="utf-8"))


def raw_with_text(section_id: str, old: str, new: str) -> dict:
    raw = raw_policy()
    (section,) = [s for s in raw["sections"] if s["id"] == section_id]
    assert old in section["text"]
    section["text"] = section["text"].replace(old, new)
    return raw


def test_policy_loads():
    policy = load_policy()
    assert policy.currency == "BRL"
    assert policy.citation("window") == "refund-policy/v1/window"


def test_texts_take_numbers_from_rules():
    policy = load_policy()
    assert f"no later than {policy.rules.refund_window_days} days" in policy.rendered_text("window")
    assert f"expires, {policy.rules.proposal_ttl_hours} hours after" in policy.rendered_text("validity")
    assert 'status "delivered"' in policy.rendered_text("eligible-orders")


def test_rendered_document_is_in_sync():
    expected = render_markdown(load_policy())
    actual = RENDERED_PATH.read_text(encoding="utf-8")
    assert actual == expected, "docs/refund-policy.md is stale: run `uv run python -m refund_agent.policy`"


def test_unknown_section_has_no_citation():
    with pytest.raises(KeyError):
        load_policy().citation("free-shipping")


def test_number_written_into_text_is_rejected():
    raw = raw_with_text("window", "{refund_window_days}", "30")
    with pytest.raises(ValidationError, match="contains a digit"):
        Policy.model_validate(raw)


def test_unknown_placeholder_is_rejected():
    raw = raw_with_text("window", "{refund_window_days}", "{refund_window_weeks}")
    with pytest.raises(ValidationError, match="unknown placeholders"):
        Policy.model_validate(raw)


def test_rule_missing_from_every_text_is_rejected():
    raw = raw_with_text("validity", "{proposal_ttl_hours} hours", "some time")
    with pytest.raises(ValidationError, match="not stated in any section text"):
        Policy.model_validate(raw)


def test_undeclared_rule_is_rejected():
    raw = raw_policy()
    raw["rules"]["refund_shipping"] = True
    with pytest.raises(ValidationError, match="refund_shipping"):
        Policy.model_validate(raw)


def test_misspelled_order_status_is_rejected():
    raw = raw_policy()
    raw["rules"]["eligible_order_statuses"] = ["deliverd"]
    with pytest.raises(ValidationError):
        Policy.model_validate(raw)


def test_duplicate_section_id_is_rejected():
    raw = raw_policy()
    raw["sections"].append(dict(raw["sections"][0]))
    with pytest.raises(ValidationError, match="duplicate section ids"):
        Policy.model_validate(raw)


@pytest.mark.parametrize("wrong", ["30", 30.0, True])
def test_wrong_type_is_rejected_not_converted(wrong):
    raw = raw_policy()
    raw["rules"]["refund_window_days"] = wrong
    with pytest.raises(ValidationError):
        Policy.model_validate(raw)


def test_frozen_version_with_changed_content_does_not_load(tmp_path):
    text = POLICY_PATH.read_text(encoding="utf-8").replace("is on time.", "is late.")
    path = tmp_path / "policy.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="frozen"):
        load_policy(path)


def test_changed_content_loads_under_a_new_version(tmp_path):
    text = POLICY_PATH.read_text(encoding="utf-8").replace("is on time.", "is late.")
    path = tmp_path / "policy.toml"
    path.write_text(text.replace('version = "v1"', 'version = "v2"'), encoding="utf-8")
    assert load_policy(path).version == "v2"


def test_hash_ignores_comments_wrapping_and_line_endings(tmp_path):
    text = POLICY_PATH.read_text(encoding="utf-8")
    text = "# an extra comment\n" + text.replace("All amounts are in {currency},", "All amounts\n   are in {currency},")
    path = tmp_path / "policy.toml"
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert load_policy(path).content_hash() == load_policy().content_hash()


# Versions (plan change log, 2026-10-20): a run loads the version its scenarios declare.


def test_a_version_is_loaded_by_its_name():
    assert load_policy_version("v1") == load_policy()


def test_a_file_that_declares_another_version_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_module, "POLICY_PATH", tmp_path / "refund-policy-v1.toml")
    (tmp_path / "refund-policy-v7.toml").write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="refund-policy-v7.toml declares version v1, not v7"):
        load_policy_version("v7")


def test_a_scenario_is_never_loaded_with_another_version():
    scenario = next(s for s in load_split("development") if s.id == "D01")
    with pytest.raises(ValueError, match="D01 is written for policy v9, not v1"):
        seed(None, scenario.model_copy(update={"policy_version": "v9"}), load_policy())  # before any database work
