"""The refund policy has one controlled source, and a broken source fails on load."""

import tomllib

import pytest
from pydantic import ValidationError

from refund_agent.policy import POLICY_PATH, RENDERED_PATH, Policy, load_policy, render_markdown


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
    assert f"within {policy.rules.refund_window_days} days" in policy.rendered_text("window")
    assert f"valid for {policy.rules.proposal_ttl_hours} hours" in policy.rendered_text("validity")
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
    raw = raw_with_text("validity", "for {proposal_ttl_hours} hours", "for a limited time")
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
