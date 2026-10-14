"""What a paid run ran with (plan section 11), adapted from the manifest of the Agent Action Guard project.

The identity holds the models, settings, prices, budget and prompt hashes; the fingerprint covers every file that
decides what a run does (the agent, the backend's rules, the evaluator, the prompts, the policy, the scenarios, the
schema and the locked dependencies), with line endings made uniform so a Windows checkout hashes like any other.
The commit is recorded too, with whether the working tree had uncommitted changes. Two runs with different
fingerprints are different experiments and are never pooled.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from refund_agent.policy import REPO_ROOT

RUN_FILES = (
    "refund_agent/agent/*.py",
    "refund_agent/evaluation/*.py",
    "refund_agent/refunds.py",
    "refund_agent/eligibility.py",
    "refund_agent/states.py",
    "refund_agent/reads.py",
    "refund_agent/scenarios.py",
    "refund_agent/policy.py",
    "refund_agent/fixtures.py",
    "prompts/*.md",
    "policies/*.toml",
    "scenarios/development/*.toml",
    "migrations/sql/*.sql",
    "uv.lock",
)


def file_hashes(root: Path = REPO_ROOT) -> dict[str, str]:
    paths = sorted({path for pattern in RUN_FILES for path in root.glob(pattern) if path.is_file()})
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for path in paths
    }


def fingerprint(hashes: dict[str, str]) -> str:
    return hashlib.sha256("\n".join(f"{p}:{h}" for p, h in sorted(hashes.items())).encode()).hexdigest()


def git(*args: str, root: Path = REPO_ROOT) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(identity: dict, root: Path = REPO_ROOT) -> dict:
    hashes = file_hashes(root)
    status = git("status", "--porcelain", root=root)
    return {
        "schema": 1,
        "identity": identity,
        "fingerprint": fingerprint(hashes),
        "files": hashes,
        "git_commit": git("rev-parse", "HEAD", root=root),
        "git_dirty": bool(status),
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
    }
