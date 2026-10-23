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
date. All the kinds of a group are picked out when the customer names each of them, or says "both", "each", "every",
a number, or "all" followed by "of", "the" or "my". Words are read, not meant: "not the rust one" names the rust
scarf, and "the second one" names nothing; the agent asks, and the customer's answer settles it.
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
_ALL_OF_THEM = re.compile(r"\b(both|each|every|two|three|four|five|all (?:of|the|my))\b")
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


def _names_date(text: str, day: date) -> bool:
    month = _MONTHS[day.month - 1]
    months = f"(?:{month}|{month[:3]})"
    nth = f"{day.day}(?:st|nd|rd|th)?"
    return bool(
        re.search(rf"\b{nth}(?: of)? {months}\b", text)
        or re.search(rf"\b{months}\.? {nth}\b", text)
        or re.search(rf"\b{day.isoformat()}\b", text)
    )


def _tells_apart(kind: Kind, others: Sequence[Kind], text: str) -> bool:
    """Whether these words pick out this kind among the others of its group."""
    said = plain(text)
    if kind.variant - set().union(*(other.variant for other in others)) & _words(text):
        return True
    if all(other.order_id != kind.order_id for other in others) and re.search(
        rf"\b{re.escape(plain(kind.order_id))}\b", said
    ):
        return True
    taken = {d for other in others for d in (other.placed, other.delivered)}
    return any(day is not None and day not in taken and _names_date(said, day) for day in (kind.placed, kind.delivered))


def _picked(chosen: Sequence[Kind], group: Sequence[Kind], text: str, *, all_words: bool) -> bool:
    """Whether these words pick out exactly the chosen kinds of the group."""
    if len(chosen) == len(group):
        if all_words and _ALL_OF_THEM.search(plain(text)):
            return True
        return all(_tells_apart(kind, [k for k in group if k != kind], text) for kind in chosen)
    others = [kind for kind in group if kind not in chosen]
    return all(_tells_apart(kind, others, text) for kind in chosen)


def look_alikes_unnamed(
    kinds: Sequence[Kind], unit_ids: Sequence[str], messages: Sequence[tuple[str, str]]
) -> tuple[Kind, ...]:
    """The group of look-alikes that the customer's words do not yet tell apart for this selection, or () when the
    selection may be proposed.

    kinds: the customer's products, each in one order, with the units not yet refunded. messages: the conversation's
    (author, text), customer and agent only, in order. The selection is picked out when the customer's words, in any
    of their messages, tell the chosen kinds apart; or when the customer's latest message comes right after an agent
    message that asks a question and names the chosen kinds in a way that tells them apart ("Do you mean the olive
    one?" and "Yes"). An answer the agent reads stays the agent's reading; a notice from the backend is not the
    customer's answer."""
    kind_of = {unit: kind for kind in kinds for unit in kind.unit_ids}
    chosen = list(dict.fromkeys(kind_of[unit] for unit in unit_ids if unit in kind_of))
    customer = " \n ".join(text for author, text in messages if author == "customer")
    latest = max((i for i, (author, _) in enumerate(messages) if author == "customer"), default=None)
    question = messages[latest - 1] if latest else None
    asked = question[1] if question and question[0] == "agent" and asks_customer(question[1]) else ""
    for family in dict.fromkeys(kind.family for kind in chosen):
        group = tuple(kind for kind in kinds if kind.family == family)
        if len(group) < 2:
            continue
        mine = [kind for kind in chosen if kind.family == family]
        if _picked(mine, group, customer, all_words=True):
            continue
        if asked and _picked(mine, group, asked, all_words=False):
            continue
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
