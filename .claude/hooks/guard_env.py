"""Claude Code hook: Claude never reads .env, where the API keys live (CLAUDE.md).

Runs before Read, Grep and every tool that runs a shell command, and refuses:
- Read or Grep aimed at a secret env file: .env, or .env.<name> other than .env.example, .sample or .template;
- a shell command that names one, unless it only checks that the file exists (test -f .env, [ -f .env ],
  git check-ignore .env, Test-Path .env, ls .env) and has no pipe, substitution or input redirection.

It guards against mistakes, not against a determined attacker: a command that builds the name (cat .e?v) is not
caught. The deny rules in .claude/settings.json keep Read, Grep and Glob away from .env as well. Commands the user
types in a terminal are not affected. An allowed call gets no output, so the normal permission prompts still apply:
this hook never says "allow".
"""

from __future__ import annotations

import json
import re
import sys

SAFE = {"example", "sample", "template"}
SHELL_TOOLS = {"Bash", "PowerShell", "Monitor", "mcp__terminal__run_in_terminal"}

# .env or .env.<name> as a word of a command: after the start, a space, a quote, a slash or a separator.
_EDGE = r"\s\"'`=<>(){}/\\:;|&,"
MENTION = re.compile(rf"(?:^|(?<=[{_EDGE}]))\.env(?:\.([a-z0-9_-]+))?(?=$|[{_EDGE}.*?\[\]])", re.IGNORECASE)

_PATH = r"[^\s;|&<>`$()]+"
PRESENCE_CHECKS = [
    re.compile(rf"(?:test|\[\[?)\s+-[efs]\s+{_PATH}(?:\s+\]\]?)?", re.IGNORECASE),
    re.compile(rf"git\s+check-ignore(?:\s+-[-\w]+)*(?:\s+--)?(?:\s+{_PATH})+", re.IGNORECASE),
    re.compile(rf"test-path(?:\s+-(?:literal)?path)?\s+{_PATH}", re.IGNORECASE),
    re.compile(rf"ls(?:\s+-[a-z]+)*(?:\s+{_PATH})+", re.IGNORECASE),
]
# Ways to pass a file's contents on to another command.
PASSES_ON = re.compile(r"(?<!\|)\|(?!\|)|`|\$\(|<|\bxargs\b|\beval\b")

REASON = (
    "Blocked by the project's .env lock (.claude/hooks/guard_env.py): .env holds the API keys and Claude never "
    "reads it (CLAUDE.md). To check that it exists, use `test -f .env`. To search other files for the text "
    "'.env', use the Grep tool. Anything that needs the key is run by the user in Git Bash."
)


def secret_name(path: str) -> bool:
    """Whether a path names a secret env file. On Windows, .env::$DATA, .env. and C:.env open the same file."""
    name = re.split(r"[/\\]", path.rstrip("/\\"))[-1]
    for part in name.split(":"):
        part = part.rstrip(". ").lower()
        if part == ".env" or (part.startswith(".env.") and part[5:] not in SAFE):
            return True
    return False


def mentions_secret(text: str) -> bool:
    return any(m.group(1) is None or m.group(1).lower() not in SAFE for m in MENTION.finditer(text))


def only_checks_presence(command: str) -> bool:
    if PASSES_ON.search(command):
        return False
    for segment in re.split(r"&&|\|\||;|\n", command):
        segment = re.sub(r"^(?:if|then|else|elif|!)\s+", "", segment.strip())
        if mentions_secret(segment) and not any(check.fullmatch(segment) for check in PRESENCE_CHECKS):
            return False
    return True


def refused(tool: str, given: dict) -> bool:
    if tool == "Read":
        return secret_name(str(given.get("file_path", "")))
    if tool == "Grep":
        return secret_name(str(given.get("path", ""))) or ".env" in str(given.get("glob", "")).lower()
    if tool in SHELL_TOOLS:
        command = str(given.get("command", ""))
        return mentions_secret(command) and not only_checks_presence(command)
    return False


def main() -> None:
    event = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    if refused(event.get("tool_name", ""), event.get("tool_input") or {}):
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": REASON}
        print(json.dumps({"hookSpecificOutput": decision}))


if __name__ == "__main__":
    main()
