"""The demo refund policy, loaded from its single controlled source.

Each version has one file, policies/refund-policy-<version>.toml, with the rules and the section texts. The backend
reads the rules from this module, and docs/refund-policy.md is rendered from the file of the policy in force
(POLICY_PATH), so the two cannot disagree. A scenario names the version it was written for, and a run loads that
version (load_policy_version).

A released version is frozen by its content hash (FROZEN_VERSIONS): a changed rule or text needs a new version.
After a new version, re-render the document with `uv run python -m refund_agent.policy`.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
import textwrap
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REPO_ROOT = Path(__file__).resolve().parent.parent
# The policy in force; scenarios and runs name the version they were written for (load_policy_version).
POLICY_PATH = REPO_ROOT / "policies" / "refund-policy-v2.toml"
RENDERED_PATH = REPO_ROOT / "docs" / "refund-policy.md"

# The order_status values of the Olist dataset.
OrderStatus = Literal[
    "created", "approved", "invoiced", "processing", "shipped", "delivered", "canceled", "unavailable"
]

# strict: a wrong type is an error, never converted (by default "30", 30.0 and true would all load as numbers).
_FROZEN = ConfigDict(frozen=True, extra="forbid", strict=True)
# TOML arrays arrive as lists; these fields accept them as tuples, and their elements stay strict.
_ARRAY = {"strict": False}

# Released versions and the content hash each one is frozen at. load_policy refuses a frozen version whose
# content changed: a changed rule or text needs a new version, so a version always names one policy.
FROZEN_VERSIONS = {
    "v1": "4b13ed244bb199f0538df9aba8ed1af53370dd80c7b15802b4253b01e4ebecde",
    # Approved by the user on 2026-10-20, before its first run.
    "v2": "49c40ec9f72b3b2e22b7b90b3e8755b1ca1bd0a776436435135cc65931de97b0",
}


class Rules(BaseModel):
    """The rules the backend enforces. Section texts refer to them by field name, e.g. {refund_window_days}."""

    model_config = _FROZEN

    eligible_order_statuses: tuple[OrderStatus, ...] = Field(min_length=1, **_ARRAY)
    refund_window_days: int = Field(gt=0, le=365)
    proposal_ttl_hours: int = Field(gt=0, le=720)


class Section(BaseModel):
    model_config = _FROZEN

    id: str = Field(pattern=r"^[a-z]+(-[a-z]+)*$")
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _one_paragraph(cls, text: str) -> str:
        # The TOML texts are wrapped for reading; each section is one paragraph.
        return " ".join(text.split())

    def placeholders(self) -> set[str]:
        return {name for _, name, _, _ in string.Formatter().parse(self.text) if name is not None}


class Policy(BaseModel):
    model_config = _FROZEN

    policy_id: str = Field(pattern=r"^[a-z]+(-[a-z]+)*$")
    version: str = Field(pattern=r"^v[0-9]+$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    rules: Rules
    sections: tuple[Section, ...] = Field(min_length=1, **_ARRAY)

    @model_validator(mode="after")
    def _single_source(self) -> Policy:
        ids = [section.id for section in self.sections]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate section ids: {duplicates}")
        known = self.placeholder_values().keys()
        for section in self.sections:
            if re.search(r"[0-9]", section.title + section.text):
                raise ValueError(f"section {section.id!r} contains a digit; numbers must come from [rules]")
            unknown = section.placeholders() - known
            if unknown:
                raise ValueError(f"section {section.id!r} uses unknown placeholders: {sorted(unknown)}")
        stated = set().union(*(section.placeholders() for section in self.sections))
        hidden = known - stated
        if hidden:
            raise ValueError(f"rules not stated in any section text: {sorted(hidden)}")
        return self

    def placeholder_values(self) -> dict[str, str]:
        """What each {placeholder} in a section text is replaced with."""
        values = {"currency": self.currency}
        for name, value in self.rules.model_dump().items():
            if isinstance(value, tuple | list):
                values[name] = " or ".join(f'"{item}"' for item in value)
            else:
                values[name] = str(value)
        return values

    def content_hash(self) -> str:
        """SHA-256 of the policy's content. Comments, wrapping and line endings of the TOML file do not change it."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def section(self, section_id: str) -> Section:
        for section in self.sections:
            if section.id == section_id:
                return section
        raise KeyError(f"unknown policy section: {section_id!r}")

    def citation(self, section_id: str) -> str:
        """The ID a citation of this section carries, e.g. 'refund-policy/v1/window'."""
        return f"{self.policy_id}/{self.version}/{self.section(section_id).id}"

    def rendered_text(self, section_id: str) -> str:
        """The section text with the rule values filled in."""
        return self.section(section_id).text.format(**self.placeholder_values())


def load_policy(path: Path = POLICY_PATH) -> Policy:
    with path.open("rb") as f:
        policy = Policy.model_validate(tomllib.load(f))
    frozen = FROZEN_VERSIONS.get(policy.version)
    if frozen is not None and frozen != policy.content_hash():
        raise ValueError(
            f"policy {policy.version} is frozen at {frozen} but its content hashes to {policy.content_hash()}; "
            "a changed policy needs a new version"
        )
    return policy


def load_policy_version(version: str) -> Policy:
    """The policy of this version, from policies/refund-policy-<version>.toml. A scenario names the version it was
    written for, and runs load that one, so a newer default never reinterprets an older scenario."""
    path = POLICY_PATH.parent / f"refund-policy-{version}.toml"
    if not path.exists():
        raise ValueError(f"policy {version} does not exist: no {path.relative_to(REPO_ROOT).as_posix()}")
    policy = load_policy(path)
    if policy.version != version:
        raise ValueError(f"{path.name} declares version {policy.version}, not {version}")
    return policy


def render_markdown(policy: Policy) -> str:
    source = POLICY_PATH.relative_to(REPO_ROOT).as_posix()
    lines = [
        f"# Refund policy ({policy.policy_id}/{policy.version})",
        "",
        f"<!-- Generated from {source} by `uv run python -m refund_agent.policy`. Do not edit by hand. -->",
        "",
        "Demo policy of a fictional shop. Under each heading is the ID that a citation of that section carries.",
        "",
    ]
    for section in policy.sections:
        lines += [
            f"## {section.title}",
            "",
            f"`{policy.citation(section.id)}`",
            "",
            textwrap.fill(policy.rendered_text(section.id), width=120),
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    RENDERED_PATH.write_text(render_markdown(load_policy()), encoding="utf-8", newline="\n")
    print(f"wrote {RENDERED_PATH.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
