"""Policy retrieval for the agent's lookup_refund_policy tool (plan section 8).

Every hit carries the real citation ID of its section ("refund-policy/v1/window"), so a citation can only name a
section that exists in the policy version in force. PolicySearch is the slot a better retriever can fill later, for
example the one of the earlier RAG project if it passes a check; WordSearch is a plain word match over the twelve
sections, which is enough to start with and makes no claim that retrieval improves the agent.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from refund_agent.policy import Policy

_STOP = set(
    "a an and are as at be been but by can could do does for from had has have how i if in is it its me my no not "
    "of on or our so that the their them then there these this to was we were what when where which who will with "
    "would you your".split()
)


@dataclass(frozen=True)
class Hit:
    citation: str
    title: str
    text: str


class PolicySearch(Protocol):
    def search(self, query: str, limit: int = 3) -> list[Hit]: ...


def _words(text: str) -> list[str]:
    words = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in _STOP:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        words.append(word)
    return words


class WordSearch:
    """Ranks sections by the query words they contain, weighted by rarity; a word in the title counts twice."""

    def __init__(self, policy: Policy) -> None:
        self.hits = [Hit(policy.citation(s.id), s.title, policy.rendered_text(s.id)) for s in policy.sections]
        self.counts = [Counter(_words(hit.text) + _words(hit.title) * 2) for hit in self.hits]
        # A word found in every section ("refund") tells nothing apart, so rarer words weigh more (TF-IDF).
        found_in = Counter(word for counts in self.counts for word in counts)
        self.weight = {word: math.log(len(self.hits) / n) for word, n in found_in.items()}

    def search(self, query: str, limit: int = 3) -> list[Hit]:
        wanted = set(_words(query))
        scores = [sum(counts[w] * self.weight.get(w, 0.0) for w in wanted) for counts in self.counts]
        # Highest score first; on a tie, the section that comes first in the policy.
        ranked = sorted((index for index, score in enumerate(scores) if score > 0), key=lambda i: (-scores[i], i))
        return [self.hits[index] for index in ranked[:limit]]
