"""Which items the customer's words pick out, and whether a message asks the customer something (plan change log,
2026-10-23). Pure functions on words: refunds.propose() reads the data and the conversation and calls them in its
transaction, and the conversation graph uses asks_customer() to end the agent's turn at a question.

Why: in D09, D17 and D31 the agent proposed one or both of two look-alike items without asking which the customer
meant, and a successful assessment of the units it picked was taken as reason enough (32 of 602 recorded proposals,
each the first proposal of a failed try; none in the other 36 scenarios). The backend now refuses a proposal among
look-alikes until the customer's own words, or their answer to a question that named the item, tell it apart.

Look-alikes are units of one product family, the product name before its first comma ("Linen scarf, olive" and
"Linen scarf, rust"), in two or more kinds, where a kind is one product in one order. Identical units of one order
are one kind: which of them is refunded changes nothing for the customer. The family rests on the shop's naming of
its products; a catalog with product and variant codes would group by those instead.

What tells a kind apart from the others of its group: a word of its variant that the others do not have ("olive",
the "l" of "size L"), its order's ID, or the date its order was placed or delivered when no other kind shares that
date. The customer's messages are read in order, clause by clause, and each kind keeps what the customer said of it
last (review after the selection check, 2026-10-23):

- A kind is selected where words tell it apart, and unselected where a word such as "not", "keep", "except" or
  "instead of" comes before them in the clause: "Not the olive one. Please refund the rust one." selects the rust
  scarf only.
- A message that says "only" or "just" unselects the kinds of the group it does not select: "Actually, keep the
  olive one. Refund only the rust scarf." leaves the olive scarf out, whatever was said of it before.
- All the kinds at once: "both", or "each", "every", "all" or a number followed within three words by "of them" or a
  word of the family's name ("the two scarves"); "two weeks ago" selects nothing.
- An answer to the agent's question selects only when it is a yes, with no negation, to a question that named some
  kinds of the group and not all of them ("Do you mean the olive one?" and "Yes, that one"); a "no" unselects the kinds
  the question named; "Thanks" changes nothing.

Words are read, not meant: "the second one" and "the large one" select nothing, so the agent asks again. A notice
from the backend is not the customer's answer.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

# Curly quotation marks as their plain forms, written as escapes so the source stays ASCII.
_PLAIN_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")  # "i'm" is one word, so its "m" is not a size M
_QUOTED = re.compile(r"\"[^\"]*\"|(?<![a-z0-9])'[^']*'(?![a-z0-9])")
_CLAUSE = re.compile(r"[.,;:!?—–]|\s-\s|\bbut\b|\band\b")  # a hyphen inside "t-shirt" ends nothing
_EXCLUDED = re.compile(
    r"\b(no|not|never|nobody|without|except|keep|instead of|rather than|other than|apart from|cannot)\b|n't\b"
)
_ONLY = re.compile(r"\b(only|just)\b")
_COUNT = re.compile(r"\b(?:each|every|all|two|three|four|five|[2-5])\b((?:\s+\S+){1,3})")
_YES = re.compile(r"(yes|yeah|yep|yup|sure|correct|right|exactly|that one|that's (?:the one|it|right))\b")
_NO = re.compile(r"(no|nope)\b")
_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)


def plain(text: str) -> str:
    """Lower case, plain quotation marks, single spaces: the form in which words are compared."""
    return " ".join(text.translate(_PLAIN_QUOTES).casefold().split())


def _words(text: str) -> set[str]:
    return set(_WORD.findall(plain(text)))


def asks_customer(text: str) -> bool:
    """The message asks the customer something: it has a question mark outside quotation marks. A heuristic: an
    instruction such as "Please choose one" asks without a question mark, and the selection check, not this, keeps a
    proposal from being made before the answer."""
    return "?" in _QUOTED.sub("", plain(text))


@dataclass(frozen=True)
class Kind:
    """One product in one order, with its units not yet refunded."""

    order_id: str
    product: str
    placed: date
    delivered: date | None
    unit_ids: tuple[str, ...]

    @property
    def family(self) -> str:
        return plain(self.product).split(",")[0].strip()

    @property
    def variant(self) -> set[str]:
        return _words(",".join(self.product.split(",")[1:]))


def _date_at(text: str, day: date) -> int | None:
    month = _MONTHS[day.month - 1]
    months = f"(?:{month}|{month[:3]})"
    nth = f"{day.day}(?:st|nd|rd|th)?"
    for pattern in (rf"\b{nth}(?: of)? {months}\b", rf"\b{months}\.? {nth}\b", rf"\b{day.isoformat()}\b"):
        found = re.search(pattern, text)
        if found:
            return found.start()
    return None


def _named_at(kind: Kind, others: Sequence[Kind], clause: str) -> int | None:
    """Where in the clause words tell this kind apart from the others of its group, or None."""
    own = kind.variant - set().union(*(other.variant for other in others))
    for word in _WORD.finditer(clause):  # whole words: the "m" of "i'm" is not a size M
        if word.group() in own:
            return word.start()
    if all(other.order_id != kind.order_id for other in others):
        found = re.search(rf"\b{re.escape(plain(kind.order_id))}\b", clause)
        if found:
            return found.start()
    taken = {day for other in others for day in (other.placed, other.delivered)}
    for day in (kind.placed, kind.delivered):
        at = _date_at(clause, day) if day is not None and day not in taken else None
        if at is not None:
            return at
    return None


def _all_of_them_at(clause: str, family: str) -> int | None:
    """Where the clause names every kind of the family at once, or None."""
    found = re.search(r"\bboth\b", clause)
    if found:
        return found.start()
    stems = [word[:-1] for word in _WORD.findall(family) if len(word) > 3]  # "scar" for scarf and scarves
    for found in _COUNT.finditer(clause):
        if re.search(r"\bof them\b", found.group(1)) or any(stem in found.group(1) for stem in stems):
            return found.start()
    return None


def _selected(group: Sequence[Kind], messages: Sequence[tuple[str, str]]) -> dict[Kind, bool]:
    """Which kinds of the group the customer selects now: their messages read in order, clause by clause."""
    state = dict.fromkeys(group, False)
    for index, (author, text) in enumerate(messages):
        if author != "customer":
            continue
        selected_here: set[Kind] = set()
        for clause in (part for part in _CLAUSE.split(plain(text)) if part.strip()):
            whole = _all_of_them_at(clause, group[0].family)
            if whole is not None and not _EXCLUDED.search(clause[:whole]):  # "not both" alone selects nothing
                state.update(dict.fromkeys(group, True))
                selected_here.update(group)
            for kind in group:
                at = _named_at(kind, [other for other in group if other != kind], clause)
                if at is not None:
                    state[kind] = not _EXCLUDED.search(clause[:at])
                    if state[kind]:
                        selected_here.add(kind)
        if selected_here and _ONLY.search(plain(text)):
            state.update({kind: False for kind in group if kind not in selected_here})
        before = messages[index - 1] if index else None
        if before and before[0] == "agent" and asks_customer(before[1]):
            question = plain(before[1])
            asked = [kind for kind in group if _named_at(kind, [o for o in group if o != kind], question) is not None]
            reply = re.split(r"[.!?]", plain(text))[0].strip()
            if asked and len(asked) < len(group):
                if _YES.match(reply) and not _EXCLUDED.search(reply):
                    state.update(dict.fromkeys(asked, True))
                elif _NO.match(reply):
                    state.update({kind: False for kind in asked if kind not in selected_here})
    return state


def look_alikes_unnamed(
    kinds: Sequence[Kind], unit_ids: Sequence[str], messages: Sequence[tuple[str, str]]
) -> tuple[Kind, ...]:
    """The group of look-alikes whose chosen kinds the customer does not select now, or () when the selection may be
    proposed.

    kinds: the customer's products, each in one order, with the units not yet refunded. messages: the conversation's
    (author, text), customer and agent only, in order. What selects a kind is in the module's docstring; an answer
    the agent reads stays the agent's reading, and a notice from the backend is not the customer's answer."""
    kind_of = {unit: kind for kind in kinds for unit in kind.unit_ids}
    chosen = list(dict.fromkeys(kind_of[unit] for unit in unit_ids if unit in kind_of))
    for family in dict.fromkeys(kind.family for kind in chosen):
        group = tuple(kind for kind in kinds if kind.family == family)
        if len(group) < 2:
            continue
        state = _selected(group, messages)
        if not all(state[kind] for kind in chosen if kind.family == family):
            return group
    return ()


def refusal(group: Sequence[Kind]) -> str:
    """What the agent is told when the customer's words do not yet say which look-alikes they mean."""
    items = "; ".join(
        f"{kind.product} (order {kind.order_id}, placed {kind.placed.day} {kind.placed:%B}, "
        f"unit{'s' if len(kind.unit_ids) > 1 else ''} {', '.join(kind.unit_ids)})"
        for kind in group
    )
    return (
        f"The customer's words do not yet say which of these they mean: {items}. Ask which, naming each by what tells "
        "it apart (such as its colour, size or order date), and wait for the answer. Propose all of them only if the "
        "customer says so."
    )
