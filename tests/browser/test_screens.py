"""The critical paths of the two screens in a real browser, by keyboard and mouse (plan sections 7, 8 and 13).

Each person has a browser context of their own, so the customer and the staff member hold separate sessions, as on
two computers. The expected values are written here by hand, and what the screens show is checked against the
database itself.
"""

import re

from playwright.sync_api import Browser, Locator, Page, expect
from sqlalchemy import text

from refund_agent import db as database
from tests.browser.conftest import PASSWORD, Server

AGENT_TIME_MS = 30_000  # the scripted agent's turn, a staff decision's notice, and the screens' next read
NO_ANSWER = "No answer from the server. Nothing is assumed"


def two_people(browser: Browser) -> tuple[Page, Page, list[str]]:
    """Ana's page and Rui's, each in a session of its own, and the script errors either page raises."""
    customer, staff = browser.new_context().new_page(), browser.new_context().new_page()
    errors: list[str] = []
    for page in (customer, staff):
        page.on("pageerror", lambda error: errors.append(str(error)))
    return customer, staff, errors


def sign_in(page: Page, url: str, email: str) -> None:
    """Typed as a person would, sent with Enter."""
    page.goto(url)
    page.get_by_label("Email").press_sequentially(email)
    page.get_by_label("Password").press_sequentially(PASSWORD)
    page.get_by_label("Password").press("Enter")


def ana_asks_for_the_mug(customer: Page, server: Server) -> Locator:
    """Ana signs in and asks for her refund; returns the Confirm button of the agent's proposal."""
    sign_in(customer, server.url, "ana.lima@example.test")
    expect(customer.get_by_role("heading", name="Your orders")).to_be_visible()
    message = customer.get_by_label("Message")
    message.press_sequentially("Hi, I sent back the blue mug because it arrived chipped. Can I get a refund?")
    message.press("Enter")
    # The agent proposes; the card shows the amount the backend computed, and only the customer can confirm it.
    confirm = customer.get_by_role("button", name="Confirm refund of R$ 49,90")
    expect(confirm).to_be_visible(timeout=AGENT_TIME_MS)
    return confirm


def ana_confirms_the_mug(customer: Page, server: Server) -> Locator:
    """Ana asks for her refund and confirms the agent's proposal; returns the card in the chat."""
    ana_asks_for_the_mug(customer, server).click()
    # The order's list of requests says it too; the card in the chat is the one checked.
    card = customer.get_by_role("article", name=re.compile(r"^Refund request "))
    expect(card.get_by_text("Waiting for staff approval", exact=True)).to_be_visible()
    return card


def rui_opens_the_request(staff: Page) -> Locator:
    """Rui, signed in, opens Ana's request from the queue; returns its Approve button."""
    staff.get_by_role("button", name=re.compile(r"R\$ 49,90 · Ana Lima")).click()
    expect(staff.get_by_text("Checked by the backend")).to_be_visible()
    approve = staff.get_by_role("button", name="Approve refund of R$ 49,90")
    expect(approve).to_be_visible()
    return approve


def the_receipt(card: Locator) -> str:
    """Waits for the receipt on Ana's card, at the screen's next read; returns its number."""
    receipt = card.get_by_text(re.compile(r"Receipt R-\d{8}: R\$ 49,90 sent back to your original payment"))
    expect(receipt).to_be_visible(timeout=AGENT_TIME_MS)
    return re.search(r"R-\d{8}", receipt.inner_text()).group()


def refunds(server: Server) -> list[tuple]:
    """Every refund in the database, with its units."""
    owner = database.engine("owner", server.name)
    try:
        with owner.connect() as conn:
            found = conn.execute(
                text(
                    "SELECT o.receipt_number, o.amount_minor, array_agg(l.order_unit_id) FROM refund_operations o "
                    "JOIN ledger_lines l ON l.operation_id = o.id GROUP BY o.id"
                )
            ).all()
    finally:
        owner.dispose()
    return [tuple(row) for row in found]


def confirmations(server: Server) -> tuple[list[tuple], int]:
    """The stored customer decisions, and how many confirm attempts the backend refused."""
    owner = database.engine("owner", server.name)
    try:
        with owner.connect() as conn:
            decisions = conn.execute(text("SELECT decision FROM customer_confirmations")).all()
            refused = conn.execute(
                text("SELECT count(*) FROM audit_events WHERE event = 'confirm' AND outcome = 'rejected'")
            ).scalar_one()
    finally:
        owner.dispose()
    return [tuple(row) for row in decisions], refused


def test_a_refund_through_both_screens_by_keyboard_and_mouse(serve, browser):
    server = serve("D01")  # Ana sent back a blue mug that cost R$ 49,90
    customer, staff, errors = two_people(browser)
    card = ana_confirms_the_mug(customer, server)
    sign_in(staff, server.url, "rui.costa@shop.example.test")
    rui_opens_the_request(staff).click()
    # The agent is told of the approval and pays; the customer's screen shows the receipt.
    shown = the_receipt(card)
    assert refunds(server) == [(shown, 4990, ["d01-o1-u1"])]
    assert errors == []


def test_a_restart_with_a_pending_approval_leaves_both_screens_right(serve, browser):
    """Plan section 13, failure case 8."""
    server = serve("D01")
    customer, staff, errors = two_people(browser)
    card = ana_confirms_the_mug(customer, server)
    sign_in(staff, server.url, "rui.costa@shop.example.test")
    approve = rui_opens_the_request(staff)

    server.stop()
    # While it is down, each screen keeps what it last read and says it has no answer; it assumes nothing.
    for page in (customer, staff):
        expect(page.get_by_text(NO_ANSWER).first).to_be_visible(timeout=10_000)
    expect(card.get_by_text("Waiting for staff approval", exact=True)).to_be_visible()

    server.start()
    # Back up: the notice goes, the same state shows, and nobody had to sign in again.
    for page in (customer, staff):
        expect(page.get_by_text(NO_ANSWER)).to_have_count(0, timeout=10_000)
    customer.reload()  # a reload shows what the database holds, not what the page remembered
    expect(customer.get_by_role("heading", name="Your orders")).to_be_visible()
    card = customer.get_by_role("article", name=re.compile(r"^Refund request "))
    expect(card.get_by_text("Waiting for staff approval", exact=True)).to_be_visible()
    assert refunds(server) == []

    approve.click()
    shown = the_receipt(card)
    assert refunds(server) == [(shown, 4990, ["d01-o1-u1"])]
    assert errors == []


def messages(server: Server) -> list[tuple[str, str]]:
    """Every stored message of the conversation, in order: who wrote it and what."""
    owner = database.engine("owner", server.name)
    try:
        with owner.connect() as conn:
            found = conn.execute(text("SELECT author, content_untrusted FROM messages ORDER BY created_at, id")).all()
    finally:
        owner.dispose()
    return [tuple(row) for row in found]


def test_a_case_handed_to_a_person_through_both_screens_and_a_restart(serve, browser):
    """Release brief, section 4: the customer asks for a person; each screen says what waits, also after a restart;
    the staff member identifies the customer and takes the case; the assistant answers and changes nothing after."""
    server = serve("D01")
    customer, staff, errors = two_people(browser)
    ana_asks_for_the_mug(customer, server)
    customer.get_by_role("button", name="Talk to a person").click()
    choice = customer.get_by_role("group", name="Talk to a person")
    expect(choice).to_contain_text("writes to you by email, at the address of your account")
    choice.get_by_role("button", name="Yes, talk to a person").click()

    # The customer reads what waits and how the reply comes; the open request is closed, not confirmable.
    waiting = customer.get_by_role("status").filter(has_text="Waiting for a staff member")
    expect(waiting).to_contain_text("by email, at the address of your account")
    card = customer.get_by_role("article", name=re.compile(r"^Refund request "))
    expect(card.get_by_text("Handed to a person", exact=True)).to_be_visible()
    expect(customer.get_by_role("button", name=re.compile(r"^Confirm refund"))).to_have_count(0)

    # The staff member finds the case in the queue and the customer's contact in the backend's own record.
    sign_in(staff, server.url, "rui.costa@shop.example.test")
    expect(staff.get_by_role("heading", name="Handed to a person (1)")).to_be_visible()
    case = staff.get_by_role("button", name=re.compile(r"^The customer asked for a person · d01-ana"))
    case.click()
    contact = staff.get_by_text("Ana Lima (ana.lima@example.test, d01-ana)")
    expect(contact).to_be_visible()

    server.stop()
    server.start()
    for page in (customer, staff):
        expect(page.get_by_text(NO_ANSWER)).to_have_count(0, timeout=10_000)
    customer.reload()  # what the database holds, not what the page remembered
    expect(waiting).to_be_visible()
    staff.reload()
    case.click()
    expect(contact).to_be_visible()

    staff.get_by_role("button", name="Take this case").click()
    expect(staff.get_by_role("heading", name="Handed to a person (0)")).to_be_visible()
    expect(contact).to_be_visible()  # the case left the queue; its contact stays on the open conversation
    taken = customer.get_by_role("status").filter(has_text="A staff member has taken your case")
    expect(taken).to_be_visible(timeout=AGENT_TIME_MS)

    # A message after the takeover is kept for the staff member, and nothing answers it.
    before = messages(server)
    message = customer.get_by_label("Message")
    message.press_sequentially("Hello, is anyone there?")
    message.press("Enter")
    stored = customer.get_by_role("log", name="Conversation").locator("li.message.customer:not(.sending)")
    expect(stored.filter(has_text="Hello, is anyone there?")).to_be_visible(timeout=AGENT_TIME_MS)  # read back
    assert messages(server) == [*before, ("customer", "Hello, is anyone there?")]
    assert refunds(server) == []
    assert errors == []


def test_a_confirmation_whose_answer_is_lost_counts_once(serve, browser):
    """An uncertain HTTP result (product contract section 5): the confirmation reaches the server and is stored, and
    its answer never reaches the page. A second tab, still showing the old card, presses Confirm again."""
    server = serve("D01")
    customer, staff, errors = two_people(browser)
    confirm = ana_asks_for_the_mug(customer, server)

    # Ana's second tab on the same conversation; its reads fail from now on, so it keeps the card as it was.
    stale = customer.context.new_page()
    stale.on("pageerror", lambda error: errors.append(str(error)))
    stale.goto(customer.url)
    stale_confirm = stale.get_by_role("button", name="Confirm refund of R$ 49,90")
    expect(stale_confirm).to_be_visible()
    reads = "**/api/conversations/*"
    stale.route(reads, lambda route: route.abort() if route.request.method == "GET" else route.fallback())

    def lose_the_answer(route):
        route.fetch()  # the request reaches the server, which stores the confirmation
        route.abort("connectionreset")  # and its answer is lost on the way back

    customer.route("**/api/proposals/*/confirmation", lose_the_answer, times=1)
    confirm.click()
    # The page says it does not know, then shows what the database holds.
    expect(customer.get_by_role("alert").filter(has_text=NO_ANSWER)).to_be_visible()
    card = customer.get_by_role("article", name=re.compile(r"^Refund request "))
    expect(card.get_by_text("Waiting for staff approval", exact=True)).to_be_visible()
    expect(confirm).to_have_count(0)
    assert confirmations(server) == ([("confirmed",)], 0)

    # The old tab's Confirm reaches the backend, which refuses it: still one confirmation.
    stale_confirm.click()
    expect(stale.get_by_role("alert")).to_have_text(
        "This changed in the meantime. The screen now shows the current state."
    )
    assert confirmations(server) == ([("confirmed",)], 1)
    stale.unroute(reads)
    stale_card = stale.get_by_role("article", name=re.compile(r"^Refund request "))
    expect(stale_card.get_by_text("Waiting for staff approval", exact=True)).to_be_visible()
    expect(stale_confirm).to_have_count(0)

    # Nothing is stuck: the approval pays once.
    sign_in(staff, server.url, "rui.costa@shop.example.test")
    rui_opens_the_request(staff).click()
    shown = the_receipt(card)
    assert refunds(server) == [(shown, 4990, ["d01-o1-u1"])]
    assert errors == []


def staff_decisions(server: Server) -> list[tuple]:
    """Every stored staff decision with its reason."""
    owner = database.engine("owner", server.name)
    try:
        with owner.connect() as conn:
            found = conn.execute(text("SELECT decision, reason FROM staff_decisions")).all()
    finally:
        owner.dispose()
    return [tuple(row) for row in found]


def test_a_rejection_needs_a_reason_and_the_customer_is_shown_it(serve, browser):
    server = serve("D04")  # Davi returned earbuds that cost R$ 189,90; the staff member finds another model
    reason = "The returned earbuds are a different model from the one sold."
    customer, staff, errors = two_people(browser)
    sign_in(customer, server.url, "davi.nunes@example.test")
    expect(customer.get_by_role("heading", name="Your orders")).to_be_visible()
    message = customer.get_by_label("Message")
    message.press_sequentially(
        "Hi, I returned the wireless earbuds because they kept disconnecting. I'd like a refund."
    )
    message.press("Enter")
    confirm = customer.get_by_role("button", name="Confirm refund of R$ 189,90")
    expect(confirm).to_be_visible(timeout=AGENT_TIME_MS)
    confirm.click()
    card = customer.get_by_role("article", name=re.compile(r"^Refund request "))
    expect(card.get_by_text("Waiting for staff approval", exact=True)).to_be_visible()

    sign_in(staff, server.url, "rui.costa@shop.example.test")
    staff.get_by_role("button", name=re.compile(r"R\$ 189,90 · Davi Nunes")).click()
    reject = staff.get_by_role("button", name="Reject")
    expect(reject).to_be_disabled()  # no reason, no rejection
    staff.get_by_label("Reason for the customer, needed to reject").press_sequentially(reason)
    expect(reject).to_be_enabled()
    reject.click()

    # The customer's card says it was rejected and why, at the screen's next read; nothing was paid.
    expect(card.get_by_text("Rejected", exact=True)).to_be_visible(timeout=AGENT_TIME_MS)
    expect(card.locator("p.reason")).to_have_text(f"The staff member's reason: {reason}")
    assert staff_decisions(server) == [("rejected", reason)]
    assert refunds(server) == []
    assert errors == []
