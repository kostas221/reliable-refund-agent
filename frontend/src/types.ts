// The shapes the backend sends (refund_agent/reads.py and refund_agent/api/app.py). Times arrive as ISO 8601 text,
// amounts as integer centavos. Keys ending in "_untrusted", and everything under "untrusted", are text nobody
// verified: the screens show them as plain text only.

export type Role = "customer" | "staff";

export interface Session {
  user_id: string;
  role: Role;
  display_name: string;
  csrf_token: string;
}

export type ProposalStatus =
  | "awaiting_customer_confirmation"
  | "awaiting_staff_approval"
  | "approved"
  | "refunded"
  | "ineligible"
  | "rejected"
  | "cancelled"
  | "expired"
  | "invalidated";

export interface Unit {
  unit_id: string;
  product: string;
  paid_minor: number;
  received_back: boolean;
  refunded: boolean;
}

/** A request already made for an order, as the customer and the agent both see it. */
export interface RequestSummary {
  proposal_id: string;
  status: ProposalStatus; // as displayed: an open request past its validity reads "expired"
  amount_minor: number | null; // none for a request the policy refused
  unit_ids: string[];
  created_at: string;
  receipt_number: string | null;
}

export interface Order {
  order_id: string;
  status: string;
  purchased_at: string;
  delivered_at: string | null;
  currency: string;
  units: Unit[];
  requests: RequestSummary[];
}

export interface Citation {
  citation: string; // the policy's own ID, such as refund-policy/v1/return
  title: string | null;
}

export interface Receipt {
  receipt_number: string;
  operation_id: string;
  proposal_id: string;
  amount_minor: number;
  currency: string;
  payment_id: string;
  units: { unit_id: string; amount_minor: number }[];
  committed_at: string;
}

export interface ProposalCard {
  proposal_id: string;
  conversation_id: string;
  order_id: string;
  status: ProposalStatus; // what the database holds
  display_status: ProposalStatus; // what to show
  status_reason: string | null;
  policy_reasons: string[];
  policy_citations: Citation[];
  policy_version: string;
  amount_minor: number;
  currency: string;
  units: { unit_id: string; product: string; amount_minor: number }[];
  created_at: string;
  expires_at: string;
  receipt: Receipt | null; // only once a refund is committed
}

export interface Message {
  author: "customer" | "agent" | "staff";
  content_untrusted: string;
  at: string;
}

export interface Conversation {
  conversation_id: string;
  customer_id: string;
  control: "agent" | "human_controlled";
  proposals: ProposalCard[];
  handoffs: { id: string; origin: string; status: "open" | "taken"; created_at: string }[];
  messages: Message[];
}

export interface ConversationListItem {
  conversation_id: string;
  control: "agent" | "human_controlled";
  created_at: string;
  last_message_at: string | null;
}

// The staff console: the backend's fields under "trusted", text nobody verified under "untrusted" (plan section 7).

export interface StaffProposal {
  trusted: ProposalCard & {
    customer: { id: string; display_name: string; email: string };
    customer_confirmed_at: string | null;
  };
  untrusted: {
    agent_summary: string; // written by the model
    seller_message: string | null; // written by the seller
  };
}

export interface QueuedHandoff {
  trusted: {
    handoff_id: string;
    conversation_id: string;
    customer_id: string;
    origin: "customer" | "agent" | "staff"; // as recorded; "customer" through the agent's tool is the agent's claim
    created_at: string;
    pending_proposal_id: string | null;
    prior_actions: { at: string; event: string; proposal_id: string | null; operation_id: string | null }[];
  };
  untrusted: {
    reason: string;
    customer_goal: string;
    confirmed_facts: string;
    decision_needed: string;
  };
}

export interface StaffQueue {
  awaiting_approval: StaffProposal[];
  open_handoffs: QueuedHandoff[];
}

export interface HistoryEvent {
  at: string;
  actor_type: string;
  actor_id: string | null;
  event: string;
  outcome: "committed" | "rejected";
  reason: string | null;
  proposal_id: string | null;
  operation_id: string | null;
  details: Record<string, unknown>; // only values the backend set
}

export interface StaffConversation extends Conversation {
  history: HistoryEvent[];
}
