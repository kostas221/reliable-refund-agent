// Cards for the screens' tests: Ana's mug (scenario D01), in any state.

import type { ProposalCard, ProposalStatus, Receipt } from "./types";

export const RECEIPT: Receipt = {
  receipt_number: "R-00000001",
  operation_id: "op-1",
  proposal_id: "prop-1",
  amount_minor: 4990,
  currency: "BRL",
  payment_id: "pay-1",
  units: [{ unit_id: "d01-o1-u1", amount_minor: 4990 }],
  committed_at: "2026-09-12T10:05:00Z",
};

export function card(status: ProposalStatus, extra: Partial<ProposalCard> = {}): ProposalCard {
  return {
    proposal_id: "prop-1",
    conversation_id: "conv-1",
    order_id: "d01-o1",
    status,
    display_status: status,
    status_reason: null,
    policy_reasons: [],
    policy_citations: [],
    policy_version: "v1",
    amount_minor: 4990,
    currency: "BRL",
    units: [{ unit_id: "d01-o1-u1", product: "Ceramic mug", amount_minor: 4990 }],
    created_at: "2026-09-12T10:00:00Z",
    expires_at: "2026-09-15T10:00:00Z",
    receipt: null,
    rejection_reason: null,
    ...extra,
  };
}
