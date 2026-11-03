"""The draw with ties (refund_agent/olist.py, draw_tied), used for the comparison set of v1.3: an order tied to an
earlier one is found as the author's tie says, the order a tie points to is passed over when nothing matches it,
and no order is drawn twice. Made-up orders: the Kaggle files are not in the repository."""

import pytest

from refund_agent import olist
from refund_agent.olist import (
    Order,
    delivered,
    draw_tied,
    lot,
    same_category_other_product,
    same_product_other_customer,
)


def order(oid: str, customer: str, product: str, category: str = "casa", pay: str = "credit_card") -> Order:
    return Order(
        id=oid,
        customer=customer,
        status="delivered",
        purchased_at="2018-01-01 10:00:00",
        delivered_at="2018-01-05 10:00:00",
        items=[
            {
                "order_item_id": "1",
                "product_id": product,
                "seller_id": "s1",
                "category": category,
                "price": "10.00",
                "freight_value": "2.00",
            }
        ],
        payments=[
            {"payment_sequential": "1", "payment_type": pay, "payment_installments": "1", "payment_value": "12.00"}
        ],
    )


def by_id(*orders: Order) -> dict[str, Order]:
    return {o.id: o for o in orders}


CARD = delivered()


def test_an_untied_situation_takes_the_first_orders_by_the_lot(capsys):
    orders = by_id(*(order(f"o{n}", f"c{n}", f"p{n}") for n in range(6)))
    drawn = draw_tied(orders, {"H900": (CARD, CARD)}, {})
    first, second = lot("H900", list(orders.values()))[:2]
    assert [o.id for o in drawn["H900"]] == [first.id, second.id]


def test_a_tied_order_is_the_same_product_bought_by_another_customer(capsys):
    mine = order("mine", "ana", "mug")
    orders = by_id(mine, order("same-customer", "ana", "mug"), order("other", "bia", "mug"), order("x", "caio", "pan"))
    drawn = draw_tied(orders, {"H900": (CARD, CARD)}, {"H900": {1: same_product_other_customer(0)}}, used={"x"})
    first, second = drawn["H900"]
    assert second.items[0]["product_id"] == first.items[0]["product_id"]
    assert second.customer != first.customer


def test_the_order_a_tie_points_to_is_passed_over_when_nothing_matches_it(capsys):
    orders = by_id(order("lonely", "ana", "kettle"), order("mug-1", "bia", "mug"), order("mug-2", "caio", "mug"))
    assert lot("H903", list(orders.values()))[0].id == "lonely"  # the lot puts the kettle first
    drawn = draw_tied(orders, {"H903": (CARD, CARD)}, {"H903": {1: same_product_other_customer(0)}})
    assert [o.id for o in drawn["H903"]] == ["mug-2", "mug-1"]  # the kettle has no partner: the next by the lot


def test_orders_tied_by_category_are_products_none_of_the_others_has(capsys):
    lamps = [order(f"lamp-{n}", f"c{n}", f"p{n % 2}", category="iluminacao") for n in range(6)]
    voucher = order("v", "cv", "p9", category="iluminacao", pay="voucher")
    orders = by_id(*lamps, voucher, order("pan", "cp", "p5", category="cozinha"))
    tie = same_category_other_product(0)
    situations = {"H900": (CARD, delivered(pays=("voucher",)), CARD)}
    drawn = draw_tied(orders, situations, {"H900": {1: tie, 2: tie}})
    products = [o.items[0]["product_id"] for o in drawn["H900"]]
    assert len(set(products)) == 3, products
    assert {o.items[0]["category"] for o in drawn["H900"]} == {"iluminacao"}
    assert drawn["H900"][1].id == "v"


def test_no_order_is_drawn_twice_or_taken_from_an_earlier_set(capsys):
    orders = by_id(*(order(f"o{n}", f"c{n}", f"p{n}") for n in range(5)))
    drawn = draw_tied(orders, {"H900": (CARD, CARD), "H901": (CARD, CARD)}, {}, used={"o0"})
    ids = [o.id for picked in drawn.values() for o in picked]
    assert len(ids) == len(set(ids)) == 4
    assert "o0" not in ids


def test_a_situation_that_cannot_be_drawn_stops_the_draw(capsys):
    orders = by_id(order("a", "ana", "kettle"), order("b", "bia", "mug"))
    with pytest.raises(SystemExit, match="no set of orders fits"):
        draw_tied(orders, {"H900": (CARD, CARD)}, {"H900": {1: same_product_other_customer(0)}})


def test_a_tie_must_point_to_an_earlier_order():
    with pytest.raises(ValueError, match="earlier order"):
        draw_tied({}, {"H900": (CARD, CARD)}, {"H900": {0: same_product_other_customer(1)}})


def test_the_comparison_sets_ties_are_the_authors():
    """Each tie names the order the author's `tie` names (docs/held-out-v1.3/selected-39-author-specifications.md)."""
    ties = {sid: {index: (tie.to, tie.new_product) for index, tie in t.items()} for sid, t in olist.TIES_V1_3.items()}
    assert ties == {
        "H407": {3: (0, False)},  # "same product as o1, other customer"
        "H432": {3: (1, False)},  # "same product as o2, other customer"
        "H438": {1: (0, False)},  # "same product as o1, other customer"
        "H469": {1: (0, True), 2: (0, True)},  # "same category as o1, another product", twice
    }
    assert len(olist.SITUATIONS_V1_3) == 39
