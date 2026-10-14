// What the screens say about a request, in words (plan section 8): a state never rests on colour alone, and nothing
// says money was refunded before a committed receipt exists (INV-10). Pure functions, tested in status.test.ts.

import type { ProposalCard, ProposalStatus, RequestSummary } from "./types";

export type Tone = "waiting" | "done" | "stopped";

export interface StatusText {
  label: string;
  detail: string;
  tone: Tone;
}

const OPEN: ProposalStatus[] = ["awaiting_customer_confirmation", "awaiting_staff_approval", "approved"];

// Why a request stopped being valid, from the backend's own words for it (refund_agent/refunds.py).
const INVALIDATED: Record<string, string> = {
  superseded: "Replaced by a newer request",
  handed_off: "Handed to a person",
  order_or_policy_changed: "No longer valid: the order or the policy changed",
};

/** BRL as the backend writes it (refund_agent/scenarios.py format_brl): R$ 1.234,56. */
export function formatMoney(minor: number, currency: string): string {
  const units = Math.floor(Math.abs(minor) / 100);
  const cents = String(Math.abs(minor) % 100).padStart(2, "0");
  const sign = minor < 0 ? "-" : "";
  if (currency !== "BRL") return `${sign}${currency} ${units}.${cents}`;
  return `${sign}R$ ${units.toLocaleString("en-US").replaceAll(",", ".")},${cents}`;
}

/** Times in UTC, the backend's clock. */
export function formatTime(iso: string): string {
  const time = new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
  return `${time} UTC`;
}

export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export type Viewer = "customer" | "staff";

/** The card's state, worded for the customer or for a staff member. Only a receipt makes it "Refunded". */
export function cardStatus(card: ProposalCard, viewer: Viewer = "customer"): StatusText {
  const staff = viewer === "staff";
  if (card.receipt) {
    const money = formatMoney(card.receipt.amount_minor, card.receipt.currency);
    const to = staff ? "the customer's original payment" : "your original payment";
    return {
      label: "Refunded",
      detail: `Receipt ${card.receipt.receipt_number}: ${money} sent back to ${to} on ${formatTime(card.receipt.committed_at)}.`,
      tone: "done",
    };
  }
  switch (card.display_status) {
    case "awaiting_customer_confirmation":
      return staff
        ? { label: "Waiting for the customer", detail: "The customer has not confirmed it yet.", tone: "waiting" }
        : {
            label: "Waiting for your confirmation",
            detail: "Nothing happens until you press Confirm. Typing yes in the chat does not confirm.",
            tone: "waiting",
          };
    case "awaiting_staff_approval":
      return {
        label: "Waiting for staff approval",
        detail: staff
          ? "The customer confirmed it. Approve or reject it below."
          : "You confirmed this request. A staff member reviews it next.",
        tone: "waiting",
      };
    case "approved":
      return {
        label: "Approved, not paid yet",
        detail: "A staff member approved it. A receipt appears here once the money is sent.",
        tone: "waiting",
      };
    case "refunded":
      // Cannot happen without a receipt, which commits with the refund; if it ever did, it is not shown as paid.
      return { label: "Being finalised", detail: "No receipt yet, so nothing is shown as paid.", tone: "waiting" };
    case "ineligible":
      return card.status_reason === "needs_person"
        ? { label: "A person has to decide", detail: "The policy does not let the assistant decide this one.", tone: "stopped" }
        : { label: "Not possible under the refund policy", detail: "Nothing will be paid for this request.", tone: "stopped" };
    case "rejected":
      return { label: "Rejected", detail: "A staff member rejected this request. Nothing will be paid.", tone: "stopped" };
    case "cancelled":
      return { label: "Cancelled", detail: "This request was cancelled. Nothing will be paid.", tone: "stopped" };
    case "expired":
      return {
        label: "Expired",
        detail: staff
          ? "It was not completed in time. Nothing will be paid for it."
          : "It was not completed in time. Nothing will be paid for it; you can ask again.",
        tone: "stopped",
      };
    case "invalidated":
      return {
        label: INVALIDATED[card.status_reason ?? ""] ?? "No longer valid",
        detail: "Nothing will be paid for this request.",
        tone: "stopped",
      };
  }
}

/** A short label for a request in the list of an order's requests. */
export function requestLabel(request: RequestSummary): string {
  if (request.receipt_number) return `Refunded, receipt ${request.receipt_number}`;
  const labels: Record<ProposalStatus, string> = {
    awaiting_customer_confirmation: "Waiting for your confirmation",
    awaiting_staff_approval: "Waiting for staff approval",
    approved: "Approved, not paid yet",
    refunded: "Being finalised",
    ineligible: "Not possible under the policy",
    rejected: "Rejected",
    cancelled: "Cancelled",
    expired: "Expired",
    invalidated: "No longer valid",
  };
  return labels[request.status];
}

/** The confirm button shows only while the backend waits for it, and not once the validity has passed. */
export function canConfirm(card: ProposalCard): boolean {
  return card.display_status === "awaiting_customer_confirmation" && card.receipt === null;
}

/** A confirmed request can still be cancelled until it is paid. */
export function canCancel(card: ProposalCard): boolean {
  return (card.display_status === "awaiting_staff_approval" || card.display_status === "approved") && !card.receipt;
}

export function isOpen(card: ProposalCard): boolean {
  return OPEN.includes(card.display_status) && card.receipt === null;
}
