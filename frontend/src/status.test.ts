import { describe, expect, test } from "vitest";

import { canCancel, canConfirm, cardStatus, formatMoney, handoffNotice, requestLabel } from "./status";
import { RECEIPT, card } from "./testCards";
import type { Conversation, ProposalStatus, RequestSummary } from "./types";

const ALL: ProposalStatus[] = [
  "awaiting_customer_confirmation",
  "awaiting_staff_approval",
  "approved",
  "refunded",
  "ineligible",
  "rejected",
  "cancelled",
  "expired",
  "invalidated",
];

describe("nothing reads as refunded without a receipt", () => {
  test("only a receipt makes a card Refunded, and it names the receipt", () => {
    const paid = cardStatus(card("refunded", { receipt: RECEIPT }));
    expect(paid.label).toBe("Refunded");
    expect(paid.detail).toContain("R-00000001");
    expect(paid.detail).toContain("R$ 49,90");
  });

  test.each(ALL.flatMap((status) => [[status, "customer"] as const, [status, "staff"] as const]))(
    "a card in %s without a receipt never says refunded or paid to the %s",
    (status, viewer) => {
      const shown = cardStatus(card(status), viewer);
      expect(shown.label).not.toMatch(/refunded/i);
      expect(`${shown.label} ${shown.detail}`).not.toMatch(/\bwas paid\b|\bhas been paid\b|money (was|has been) sent/i);
      expect(shown.label.length).toBeGreaterThan(0);
      expect(shown.detail.length).toBeGreaterThan(0);
    },
  );

  test("the staff member reads about the customer, not about themselves", () => {
    expect(cardStatus(card("awaiting_customer_confirmation"), "staff").label).toBe("Waiting for the customer");
    expect(cardStatus(card("refunded", { receipt: RECEIPT }), "staff").detail).toContain(
      "the customer's original payment",
    );
  });

  test("an approved request says it is not paid yet", () => {
    expect(cardStatus(card("approved")).label).toBe("Approved, not paid yet");
  });

  test("a request in the list is Refunded only with a receipt number", () => {
    const request: RequestSummary = {
      proposal_id: "prop-1",
      status: "refunded",
      amount_minor: 4990,
      unit_ids: ["d01-o1-u1"],
      created_at: "2026-09-12T10:00:00Z",
      receipt_number: null,
      rejection_reason: null,
    };
    expect(requestLabel(request)).toBe("Being finalised");
    expect(requestLabel({ ...request, receipt_number: "R-00000001" })).toBe("Refunded, receipt R-00000001");
  });
});

describe("the buttons follow what the backend waits for", () => {
  test("confirm only while the customer's confirmation is awaited and still valid", () => {
    expect(canConfirm(card("awaiting_customer_confirmation"))).toBe(true);
    const lapsed = card("awaiting_customer_confirmation", { display_status: "expired" });
    expect(canConfirm(lapsed)).toBe(false);
    expect(cardStatus(lapsed).label).toBe("Expired");
    for (const status of ALL.filter((s) => s !== "awaiting_customer_confirmation")) {
      expect(canConfirm(card(status))).toBe(false);
    }
  });

  test("cancel once confirmed and until paid", () => {
    expect(ALL.filter((status) => canCancel(card(status)))).toEqual(["awaiting_staff_approval", "approved"]);
    expect(canCancel(card("approved", { receipt: RECEIPT }))).toBe(false);
  });
});

describe("words for the reasons a request stopped", () => {
  test("a refusal and a case for a person read differently", () => {
    expect(cardStatus(card("ineligible", { status_reason: "refused" })).label).toBe(
      "Not possible under the refund policy",
    );
    expect(cardStatus(card("ineligible", { status_reason: "needs_person" })).label).toBe("A person has to decide");
  });

  test("an invalidated request says why, in the backend's terms", () => {
    expect(cardStatus(card("invalidated", { status_reason: "superseded" })).label).toBe("Replaced by a newer request");
    expect(cardStatus(card("invalidated", { status_reason: "handed_off" })).label).toBe("Handed to a person");
    expect(cardStatus(card("invalidated", { status_reason: "something new" })).label).toBe("No longer valid");
  });
});

describe("money is written as the backend writes it", () => {
  test.each([
    [4990, "R$ 49,90"],
    [5, "R$ 0,05"],
    [123456, "R$ 1.234,56"],
    [100000000, "R$ 1.000.000,00"],
  ])("%i centavos is %s", (minor, written) => {
    expect(formatMoney(minor, "BRL")).toBe(written);
  });
});

describe("what a customer reads while a person has the conversation (release brief, section 4)", () => {
  const handoff = (status: "open" | "taken", created_at = "2026-09-12T10:10:00Z") => ({
    id: `h-${created_at}`,
    origin: "customer",
    status,
    created_at,
  });
  const human = (...handoffs: Conversation["handoffs"]) => handoffNotice("human_controlled", handoffs);

  test("no notice while the assistant has the conversation", () => {
    expect(handoffNotice("agent", [])).toBeNull();
  });

  test("an open case says it waits for a staff member, not that one is handling it", () => {
    const shown = human(handoff("open"));
    expect(shown?.label).toBe("Waiting for a staff member");
    expect(shown?.detail).not.toMatch(/handling|has taken/i);
  });

  test("a taken case says a staff member has it", () => {
    expect(human(handoff("taken"))?.label).toBe("A staff member has taken your case");
  });

  test("the latest handoff decides, and none at all is not read as taken", () => {
    expect(human(handoff("taken", "2026-09-12T10:10:00Z"), handoff("open", "2026-09-12T11:00:00Z"))?.label).toBe(
      "Waiting for a staff member",
    );
    expect(human()?.label).toBe("Waiting for a staff member");
  });

  test.each(["open", "taken"] as const)("a %s case says how the reply comes and what the chat still does", (status) => {
    const detail = human(handoff(status))?.detail ?? "";
    expect(detail).toContain("by email, at the address of your account");
    expect(detail).toContain("their replies do not come through this chat");
    expect(detail).toContain("The assistant makes no more changes here");
    expect(detail).toContain("your messages are kept for the staff member");
  });

  test.each(["open", "taken"] as const)("a %s case is never presented as resolved or paid", (status) => {
    const shown = human(handoff(status));
    expect(`${shown?.label} ${shown?.detail}`).not.toMatch(/resolved|refunded|will be paid|sorted|done/i);
  });
});
