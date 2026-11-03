"""The Olist subset behind the held-out scenarios (plan section 6, data).

    uv run python -m refund_agent.olist [v1.1 | v1.2 | stress-v1.2 | v1.3]

Reads the Kaggle files in data/raw/olist/ (never committed), refuses them unless each matches the SHA-256 recorded
below, and draws, for each held-out situation, real orders of the shape it needs. The draw is fixed, not chosen:
the orders that fit are ordered by the SHA-256 of the situation's ID and the order ID, and the first not drawn for
another situation is taken. It writes data/olist/subset.json, which the held-out fixtures copy their numbers from;
data/olist/README.md records the source, the licence and what is real and what is synthetic.

Taken from Olist: an order's items, which of them are the same product, each item's seller and category, prices,
freight, payment records, status, and how long delivery took. Synthetic: product and customer names, return
records, refunds, and the dates, moved to 2026 with their intervals kept. Orders whose payments do not add up to
their items and freight are left out: the refund policy does not say how instalment interest is refunded.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from refund_agent.policy import REPO_ROOT

RAW = REPO_ROOT / "data" / "raw" / "olist"
SUBSET = REPO_ROOT / "data" / "olist" / "subset.json"
SOURCE = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
LICENCE = "CC BY-NC-SA 4.0"
# The files as downloaded on 2026-10-18 (the dataset says it is never updated).
FILES = {
    "olist_customers_dataset.csv": "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2",
    "olist_order_items_dataset.csv": "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279",
    "olist_order_payments_dataset.csv": "4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0",
    "olist_orders_dataset.csv": "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf",
    "olist_products_dataset.csv": "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc",
    "product_category_name_translation.csv": "a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278",
}


@dataclass
class Order:
    id: str
    customer: str  # Olist's customer_unique_id, used only to find two orders of one person
    status: str
    purchased_at: str
    delivered_at: str
    items: list[dict] = field(default_factory=list)
    payments: list[dict] = field(default_factory=list)
    # The delivery date Olist promised at purchase: for v1.1, the one interval an order without a delivery time keeps.
    estimated_at: str = ""

    @property
    def products(self) -> int:
        return len({i["product_id"] for i in self.items})

    @property
    def sellers(self) -> int:
        return len({i["seller_id"] for i in self.items})

    @property
    def payment_types(self) -> list[str]:
        return sorted(p["payment_type"] for p in self.payments)

    def adds_up(self) -> bool:
        """The payments equal the items and their freight, to the centavo."""
        owed = sum(cents(i["price"]) + cents(i["freight_value"]) for i in self.items)
        return owed == sum(cents(p["payment_value"]) for p in self.payments)


def cents(value: str) -> int:
    reais, _, centavos = value.partition(".")
    return int(reais) * 100 + int((centavos + "00")[:2])


def sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(name: str) -> list[dict]:
    with open(RAW / name, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load() -> dict[str, Order]:
    wrong = [name for name, expected in FILES.items() if sha256(RAW / name) != expected]
    if wrong:
        sys.exit(f"These files differ from the recorded download: {wrong}")
    customers = {c["customer_id"]: c["customer_unique_id"] for c in read("olist_customers_dataset.csv")}
    english = {
        r["product_category_name"]: r["product_category_name_english"]
        for r in read("product_category_name_translation.csv")
    }
    category = {
        p["product_id"]: english.get(p["product_category_name"], p["product_category_name"] or "unknown")
        for p in read("olist_products_dataset.csv")
    }
    orders = {
        o["order_id"]: Order(
            o["order_id"],
            customers[o["customer_id"]],
            o["order_status"],
            o["order_purchase_timestamp"],
            o["order_delivered_customer_date"],
            estimated_at=o["order_estimated_delivery_date"],
        )
        for o in read("olist_orders_dataset.csv")
    }
    for item in read("olist_order_items_dataset.csv"):
        orders[item["order_id"]].items.append({**item, "category": category[item["product_id"]]})
    for payment in read("olist_order_payments_dataset.csv"):
        orders[payment["order_id"]].payments.append(payment)
    for order in orders.values():
        order.items.sort(key=lambda i: int(i["order_item_id"]))
        order.payments.sort(key=lambda p: int(p["payment_sequential"]))
    return orders


# What each held-out situation needs (docs/scenarios.md). A second order, when there is one, may be tied to the
# first: the same category with another product (similar items), or the same product for another customer.

Fits = Callable[[Order], bool]


def delivered(items: int = 1, products: int | None = None, sellers: int | None = None, pays=("credit_card",)) -> Fits:
    def fits(o: Order) -> bool:
        return (
            o.status == "delivered"
            and bool(o.delivered_at)
            and len(o.items) == items
            and (products is None or o.products == products)
            and (sellers is None or o.sellers == sellers)
            and o.payment_types == sorted(pays)
            and o.adds_up()
        )

    return fits


def in_transit(o: Order) -> bool:
    return o.status == "shipped" and len(o.items) == 1 and o.payment_types == ["credit_card"] and o.adds_up()


ONE_ITEM = delivered()
SITUATIONS: dict[str, tuple[Fits, ...]] = {
    "H01": (delivered(2, products=2, sellers=2),),
    "H02": (delivered(2, products=2, sellers=1),),
    "H03": (delivered(3, products=3),),
    "H04": (ONE_ITEM,),
    "H05": (ONE_ITEM, in_transit),
    "H06": (delivered(3, products=1, sellers=1),),
    "H07": (ONE_ITEM, ONE_ITEM),  # the second: the same category, another product
    "H08": (delivered(2, products=2),),
    "H09": (in_transit,),
    "H10": (delivered(2, products=2),),
    "H11": (ONE_ITEM,),
    "H12": (ONE_ITEM,),
    "H13": (ONE_ITEM,),
    "H14": (ONE_ITEM,),
    "H15": (delivered(2, products=2),),
    "H16": (ONE_ITEM, ONE_ITEM),  # the second: the same product, bought by another customer
    "H17": (ONE_ITEM,),
    "H18": (ONE_ITEM,),
    "H19": (delivered(1, pays=("credit_card", "voucher")),),
    "H20": (ONE_ITEM,),
}
TIED = {
    "H07": lambda first, o: (
        o.items[0]["category"] == first.items[0]["category"]
        and o.items[0]["product_id"] != first.items[0]["product_id"]
    ),
    "H16": lambda first, o: o.items[0]["product_id"] == first.items[0]["product_id"] and o.customer != first.customer,
}


# The held-out set of v1.1 (docs/held-out-v1.1/protocol.md, section 4.1): the shapes of the 20 candidates kept from
# the author's answers (docs/held-out-v1.1/set-aside.md, section 10), as each candidate states them. Drawn by the
# same lot, never an order of v1's subset.


def card_in_instalments(count: int) -> Fits:
    """One delivered item paid by one card payment in this many instalments (H29: the customer says three)."""
    one = delivered()
    return lambda o: one(o) and int(o.payments[0]["payment_installments"]) == count


def delivered_without_time(o: Order) -> bool:
    """Recorded as delivered with no delivery time (H77), one item, one card payment."""
    return (
        o.status == "delivered"
        and not o.delivered_at
        and len(o.items) == 1
        and o.payment_types == ["credit_card"]
        and o.adds_up()
    )


def in_transit_paid_by(pays: tuple[str, ...]) -> Fits:
    return lambda o: o.status == "shipped" and len(o.items) == 1 and o.payment_types == sorted(pays) and o.adds_up()


DEBIT, BOLETO = delivered(pays=("debit_card",)), delivered(pays=("boleto",))
SITUATIONS_V1_1: dict[str, tuple[Fits, ...]] = {
    "H26": (DEBIT,),
    "H28": (ONE_ITEM,),
    "H29": (card_in_instalments(3),),
    "H30": (delivered(3, products=3, sellers=2, pays=("boleto",)),),
    "H35": (delivered(3, products=1, sellers=1),),
    "H40": (ONE_ITEM,),
    "H41": (BOLETO,),
    "H42": (ONE_ITEM,),
    "H47": (ONE_ITEM,),
    "H50": (DEBIT,),
    "H52": (delivered(2, products=2, sellers=2, pays=("voucher",)),),
    "H55": (DEBIT,),
    "H58": (BOLETO,),
    "H60": (delivered(3, products=3, sellers=2),),
    "H61": (DEBIT,),
    "H63": (ONE_ITEM,),
    "H72": (ONE_ITEM,),
    "H74": (ONE_ITEM,),
    "H77": (delivered_without_time,),
    "H80": (ONE_ITEM, in_transit_paid_by(("boleto",))),  # two orders of the customer, not tied
}
SUBSET_V1_1 = REPO_ROOT / "data" / "olist" / "subset-v1.1.json"


# The held-out set of v1.2 (docs/held-out-v1.2/protocol.md, section 4.1): the shapes of the 19 candidates kept from
# the author's answers (docs/held-out-v1.2/set-aside.md, section 9.2), as each candidate states them. Drawn by the
# same lot, never an order of v1's or v1.1's subset.

CARD_ONE_ITEM = delivered()
SITUATIONS_V1_2: dict[str, tuple[Fits, ...]] = {
    "H102": (delivered(3, products=1, sellers=1),),
    "H108": (delivered(3, products=1, sellers=1),),
    "H113": (CARD_ONE_ITEM,),
    "H116": (delivered(3, products=1, sellers=1),),
    "H233": (CARD_ONE_ITEM, CARD_ONE_ITEM),  # two orders of the customer, not tied
    "H235": (delivered(2, products=2, sellers=1),),
    "H238": (delivered(3, products=1, sellers=1),),
    "H240": (delivered(2, products=2, sellers=1),),
    "H241": (delivered(3, products=3, sellers=1),),
    "H245": (delivered(3, products=3, sellers=1), in_transit),
    "H196": (CARD_ONE_ITEM, CARD_ONE_ITEM),
    "H255": (delivered(2, products=2, sellers=1),),
    "H261": (delivered(2, products=2, sellers=1),),
    "H314": (delivered(3, products=3, sellers=1),),
    "H143": (CARD_ONE_ITEM,),
    "H281": (delivered(3, products=3, sellers=1),),
    "H286": (delivered(2, products=2, sellers=1),),
    "H300": (delivered(3, products=3, sellers=1),),
    "H355": (delivered(2, products=2, sellers=1),),
}
# The stress scenarios of v1.2 (docs/held-out-v1.2/stress-scenarios.md), drawn the same way, never an order of v1's,
# v1.1's or v1.2's held-out subset.
SITUATIONS_STRESS_V1_2: dict[str, tuple[Fits, ...]] = {
    "S01": (CARD_ONE_ITEM,),
    "S02": (CARD_ONE_ITEM,),
    "S03": (CARD_ONE_ITEM,),
    "S04": (delivered(2, products=2, sellers=1),),
    "S05": (CARD_ONE_ITEM, CARD_ONE_ITEM),  # two orders of the customer, not tied
    "S06": (delivered(2, products=2, sellers=1),),
    "S07": (delivered(2, products=2, sellers=1),),
    "S08": (delivered(3, products=3, sellers=1),),
}
SUBSET_STRESS_V1_2 = REPO_ROOT / "data" / "olist" / "subset-stress-v1.2.json"
SUBSET_V1_2 = REPO_ROOT / "data" / "olist" / "subset-v1.2.json"


# The comparison set of v1.3 (docs/held-out-v1.3/protocol.md, section 4): the shapes of the 39 selected candidates
# (docs/held-out-v1.3/selected-39-index.md), in each candidate's order of orders, as the author states them. Up to
# four orders a situation, one of them perhaps another customer's; an order may be tied to an earlier order of its
# situation, as the author wrote. H421's order is paid by card and boleto, a pair no Olist order has: it is drawn as a
# card order, and its conversion splits the payment (docs/held-out-v1.3/conversion-log.md).


@dataclass(frozen=True)
class Tie:
    """An order drawn to match the order at index `to` of its situation."""

    to: int
    key: Callable[[Order], str]  # an order can match only orders with the same key
    matches: Callable[[Order, Order], bool]  # (the earlier order, a candidate)
    new_product: bool  # the candidate's product is none of the situation's orders drawn before it


def same_product_other_customer(to: int) -> Tie:
    """The author's "same product as oN, other customer"."""
    return Tie(
        to,
        lambda o: o.items[0]["product_id"],
        lambda first, o: o.items[0]["product_id"] == first.items[0]["product_id"] and o.customer != first.customer,
        new_product=False,
    )


def same_category_other_product(to: int) -> Tie:
    """The author's "same category as oN, another product"."""
    return Tie(
        to,
        lambda o: o.items[0]["category"],
        lambda first, o: o.items[0]["category"] == first.items[0]["category"],
        new_product=True,
    )


CARD = delivered()
SITUATIONS_V1_3: dict[str, tuple[Fits, ...]] = {
    # eligible
    "H401": (CARD, delivered(2, products=2, sellers=1), CARD),
    "H402": (DEBIT,),
    "H403": (CARD, BOLETO, in_transit),
    "H404": (delivered(2, products=2, sellers=1),),
    "H405": (delivered(3, products=3, sellers=2),),
    "H406": (delivered(3, products=1, sellers=1),),
    "H407": (CARD, CARD, in_transit, CARD),  # o4: another customer's
    "H409": (delivered(pays=("voucher",)), CARD),
    "H410": (delivered(2, products=2, sellers=1),),
    "H411": (CARD, CARD, in_transit),
    "H412": (delivered(2, products=2, sellers=1),),
    "H414": (delivered(2, products=2, sellers=2),),
    "H415": (delivered(3, products=3, sellers=1),),
    "H416": (delivered(3, products=1, sellers=1),),
    # ineligible
    "H420": (delivered(pays=("credit_card", "voucher")),),
    "H421": (CARD,),  # its payment is split into card and boleto by the conversion
    "H422": (CARD, CARD, CARD),
    "H424": (CARD, in_transit),
    "H425": (CARD,),
    "H426": (delivered(2, products=2, sellers=1),),
    "H427": (CARD,),
    "H428": (CARD, CARD),
    # attack
    "H432": (CARD, CARD, in_transit, CARD),  # o4: another customer's
    "H433": (CARD,),
    "H435": (CARD,),
    "H436": (delivered(2, products=2, sellers=1),),
    "H438": (CARD, CARD),  # o2: another customer's
    "H440": (CARD,),
    "H441": (CARD,),
    "H442": (CARD,),
    # clarification_handoff: six required handoffs, then three clarifications without one
    "H461": (delivered(2, products=2, sellers=1),),
    "H462": (CARD, delivered(pays=("credit_card", "voucher"))),
    "H464": (CARD, CARD, CARD),
    "H465": (delivered(2, products=2, sellers=1),),
    "H466": (delivered(2, products=2, sellers=1),),
    "H468": (CARD, in_transit),
    "H469": (CARD, delivered(pays=("voucher",)), CARD),
    "H471": (delivered(3, products=3, sellers=1),),
    "H472": (delivered(3, products=3, sellers=1),),
}
# Each tie as the author wrote it, by the index of the tied order in its situation.
TIES_V1_3: dict[str, dict[int, Tie]] = {
    "H407": {3: same_product_other_customer(0)},
    "H432": {3: same_product_other_customer(1)},
    "H438": {1: same_product_other_customer(0)},
    "H469": {1: same_category_other_product(0), 2: same_category_other_product(0)},
}
SUBSET_V1_3 = REPO_ROOT / "data" / "olist" / "subset-v1.3.json"


def lot(situation: str, found: list[Order]) -> list[Order]:
    return sorted(found, key=lambda o: hashlib.sha256(f"{situation}:{o.id}".encode()).hexdigest())


def _attempt(
    pools: list[list[Order]],
    tied: dict[int, Tie],
    keyed: dict[int, dict[str, list[Order]]],
    fixed: dict[int, Order],
) -> list[Order] | None:
    """One situation's orders in index order, with the `fixed` ones given; None when an order cannot be found."""
    picked: list[Order] = []
    for index, pool in enumerate(pools):
        taken = {o.id for o in picked}
        if index in fixed:
            choice = fixed[index] if fixed[index].id not in taken else None
        elif index in tied:
            tie = tied[index]
            first = picked[tie.to]
            products = {o.items[0]["product_id"] for o in picked}
            choice = next(
                (
                    o
                    for o in keyed.get(index, {}).get(tie.key(first), [])
                    if o.id not in taken
                    and tie.matches(first, o)
                    and not (tie.new_product and o.items[0]["product_id"] in products)
                ),
                None,
            )
        else:
            choice = next((o for o in pool if o.id not in taken), None)
        if choice is None:
            return None
        picked.append(choice)
    return picked


def draw_tied(
    orders: dict[str, Order],
    situations: dict[str, tuple[Fits, ...]],
    ties: dict[str, dict[int, Tie]],
    used: set[str] | None = None,
) -> dict[str, list[Order]]:
    """For each situation in turn, its orders by the lot, never one in `used` or drawn before.

    An untied order is the first fitting one by the lot. A tied order is the first by the lot that fits and matches
    the earlier order it is tied to. The order the ties point to is the first by the lot for which every tied order
    can then be found, so a tie never leaves a situation without its orders while another choice would serve.
    """
    used = set(used or ())
    drawn: dict[str, list[Order]] = {}
    for situation, wants in situations.items():
        tied = ties.get(situation, {})
        if any(not 0 <= tie.to < index < len(wants) for index, tie in tied.items()):
            raise ValueError(f"{situation}: a tie must point to an earlier order of its situation")
        references = {tie.to for tie in tied.values()}
        if len(references) > 1:
            raise ValueError(f"{situation}: ties to more than one order are not supported")
        pools = [lot(situation, [o for o in orders.values() if o.id not in used and fits(o)]) for fits in wants]
        keyed: dict[int, dict[str, list[Order]]] = {}
        for index, tie in tied.items():
            for o in pools[index]:
                keyed.setdefault(index, {}).setdefault(tie.key(o), []).append(o)
        picked = None
        if references:
            (reference,) = references
            keys = [(tie, set(keyed.get(index, {}))) for index, tie in tied.items()]
            for candidate in pools[reference]:
                if all(tie.key(candidate) in found for tie, found in keys):
                    picked = _attempt(pools, tied, keyed, {reference: candidate})
                    if picked:
                        break
        else:
            picked = _attempt(pools, tied, keyed, {})
        if not picked:
            sys.exit(f"{situation}: no set of orders fits its shapes and ties")
        used.update(o.id for o in picked)
        print(f"{situation}: {len(pools[0]):6d} fit the first, drawn {', '.join(o.id for o in picked)}")
        drawn[situation] = picked
    return drawn


def draw(
    orders: dict[str, Order],
    situations: dict[str, tuple[Fits, ...]] = SITUATIONS,
    tied: dict[str, Callable[[Order, Order], bool]] = TIED,
    used: set[str] | None = None,
) -> dict[str, list[Order]]:
    """For each situation in turn, the first fitting order by the lot, never one in `used` or drawn before."""
    used = set(used or ())
    drawn: dict[str, list[Order]] = {}

    def by_lot(situation: str, found: list[Order]) -> list[Order]:
        return sorted(found, key=lambda o: hashlib.sha256(f"{situation}:{o.id}".encode()).hexdigest())

    for situation, wants in situations.items():
        tie = tied.get(situation)
        firsts = by_lot(situation, [o for o in orders.values() if o.id not in used and wants[0](o)])
        seconds = [o for o in orders.values() if o.id not in used and len(wants) > 1 and wants[1](o)]
        picked: list[Order] = []
        for first in firsts:
            if len(wants) == 1:
                picked = [first]
                break
            partners = by_lot(situation, [o for o in seconds if o.id != first.id and (tie is None or tie(first, o))])
            if partners:
                picked = [first, partners[0]]
                break
        if not picked:
            sys.exit(f"{situation}: no order, or no pair of orders, fits its shape")
        used.update(o.id for o in picked)
        print(f"{situation}: {len(firsts):6d} fit, drawn {', '.join(o.id for o in picked)}")
        drawn[situation] = picked
    return drawn


def as_record(order: Order) -> dict:
    return {
        "order_id": order.id,
        "status": order.status,
        "purchased_at": order.purchased_at,
        "delivered_at": order.delivered_at or None,
        "items": [
            {
                "order_item_id": int(i["order_item_id"]),
                "product_id": i["product_id"],
                "seller_id": i["seller_id"],
                "category": i["category"],
                "price_minor": cents(i["price"]),
                "freight_minor": cents(i["freight_value"]),
            }
            for i in order.items
        ],
        "payments": [
            {
                "sequential": int(p["payment_sequential"]),
                "method": p["payment_type"],
                "installments": int(p["payment_installments"]),
                "amount_minor": cents(p["payment_value"]),
            }
            for p in order.payments
        ],
    }


def main() -> None:
    drawn = draw(load())
    subset = {
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": "Brazilian E-Commerce Public Dataset by Olist, https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "files_sha256": FILES,
        "drawn_by": "refund_agent/olist.py",
        "situations": {situation: [as_record(o) for o in picked] for situation, picked in drawn.items()},
    }
    SUBSET.parent.mkdir(parents=True, exist_ok=True)
    SUBSET.write_text(json.dumps(subset, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {SUBSET.relative_to(REPO_ROOT)}: {sum(len(p) for p in drawn.values())} orders")


def main_v1_1() -> None:
    """The draw for the held-out set of v1.1, written to its own file: v1's subset is read, never rewritten."""
    v1 = json.loads(SUBSET.read_text(encoding="utf-8"))
    excluded = {o["order_id"] for picked in v1["situations"].values() for o in picked}
    drawn = draw(load(), SITUATIONS_V1_1, {}, used=excluded)
    subset = {
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": "Brazilian E-Commerce Public Dataset by Olist, https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "files_sha256": FILES,
        "drawn_by": "refund_agent/olist.py (main_v1_1)",
        "excluded": f"the {len(excluded)} orders of data/olist/subset.json, the held-out set of v1",
        "situations": {
            situation: [{**as_record(o), "estimated_delivery_at": o.estimated_at} for o in picked]
            for situation, picked in drawn.items()
        },
    }
    SUBSET_V1_1.write_text(json.dumps(subset, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {SUBSET_V1_1.relative_to(REPO_ROOT)}: {sum(len(p) for p in drawn.values())} orders")


def draw_apart(
    situations: dict[str, tuple[Fits, ...]],
    target,
    earlier: tuple,
    name: str,
    excluded_note: str,
    ties: dict[str, dict[int, Tie]] | None = None,
) -> None:
    """A draw written to its own file, never an order of an earlier subset; with `ties`, drawn by draw_tied."""
    excluded = {
        o["order_id"]
        for path in earlier
        for picked in json.loads(path.read_text(encoding="utf-8"))["situations"].values()
        for o in picked
    }
    if ties is None:
        drawn = draw(load(), situations, {}, used=excluded)
    else:
        drawn = draw_tied(load(), situations, ties, used=excluded)
    subset = {
        "source": SOURCE,
        "licence": LICENCE,
        "attribution": "Brazilian E-Commerce Public Dataset by Olist, https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "files_sha256": FILES,
        "drawn_by": f"refund_agent/olist.py ({name})",
        "excluded": f"the {len(excluded)} orders of {excluded_note}",
        "situations": {
            situation: [{**as_record(o), "estimated_delivery_at": o.estimated_at} for o in picked]
            for situation, picked in drawn.items()
        },
    }
    target.write_text(json.dumps(subset, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {target.relative_to(REPO_ROOT)}: {sum(len(p) for p in drawn.values())} orders")


def main_v1_2() -> None:
    """The draw for the held-out set of v1.2; the orders of v1's and v1.1's sets are left out."""
    note = "data/olist/subset.json and subset-v1.1.json, the held-out sets of v1 and v1.1"
    draw_apart(SITUATIONS_V1_2, SUBSET_V1_2, (SUBSET, SUBSET_V1_1), "main_v1_2", note)


def main_stress_v1_2() -> None:
    """The draw for the stress scenarios of v1.2; the orders of every held-out set are left out."""
    note = "data/olist/subset.json, subset-v1.1.json and subset-v1.2.json, the held-out sets of v1, v1.1 and v1.2"
    earlier = (SUBSET, SUBSET_V1_1, SUBSET_V1_2)
    draw_apart(SITUATIONS_STRESS_V1_2, SUBSET_STRESS_V1_2, earlier, "main_stress_v1_2", note)


def main_v1_3() -> None:
    """The draw for the comparison set of v1.3; the orders of every earlier subset are left out."""
    note = (
        "data/olist/subset.json, subset-v1.1.json, subset-v1.2.json and subset-stress-v1.2.json, the held-out sets of "
        "v1, v1.1 and v1.2 and v1.2's stress set"
    )
    earlier = (SUBSET, SUBSET_V1_1, SUBSET_V1_2, SUBSET_STRESS_V1_2)
    draw_apart(SITUATIONS_V1_3, SUBSET_V1_3, earlier, "main_v1_3", note, ties=TIES_V1_3)


if __name__ == "__main__":
    mains = {"v1.1": main_v1_1, "v1.2": main_v1_2, "stress-v1.2": main_stress_v1_2, "v1.3": main_v1_3}
    mains.get(" ".join(sys.argv[1:]), main)()
