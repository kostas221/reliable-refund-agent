// The staff console (plan sections 7 and 8): the queue, a proposal to approve or reject, a conversation with its
// history, and the cases handed to a person. What the backend computed is shown apart from text nobody verified (the
// model's summary, the seller's message, the texts of a handoff), which is labelled with who wrote it and shown as
// plain text only. The approve button names the amount the backend computed, never one from that text.

import { type ReactNode, useEffect, useState } from "react";

import { ApiError, api, describe } from "./api";
import { ChatText, usePolicyTitles } from "./ChatText";
import { usePolling } from "./polling";
import { ProposalCardView } from "./ProposalCard";
import { formatMoney, formatTime } from "./status";
import type { HistoryEvent, QueuedHandoff, StaffConversation, StaffProposal } from "./types";

const QUEUE_EVERY_MS = 3000;
const DETAIL_EVERY_MS = 2500;

type Selection =
  | { kind: "proposal"; id: string }
  | { kind: "conversation"; id: string; handoffId?: string }
  | null;

function sentence(error: unknown): string {
  return error instanceof ApiError ? describe(error.failure) : String(error);
}

function selectionInAddress(): Selection {
  const fields = new URLSearchParams(window.location.hash.slice(1));
  const proposal = fields.get("proposal");
  const conversation = fields.get("conversation");
  if (proposal) return { kind: "proposal", id: proposal };
  if (conversation) return { kind: "conversation", id: conversation, handoffId: fields.get("handoff") ?? undefined };
  return null;
}

function addressOf(selection: Selection): string {
  if (!selection) return window.location.pathname;
  if (selection.kind === "proposal") return `#proposal=${encodeURIComponent(selection.id)}`;
  const handoff = selection.handoffId ? `&handoff=${encodeURIComponent(selection.handoffId)}` : "";
  return `#conversation=${encodeURIComponent(selection.id)}${handoff}`;
}

export function StaffScreen() {
  const queue = usePolling(api.staffQueue, QUEUE_EVERY_MS, "queue");
  const [selected, setSelected] = useState<Selection>(selectionInAddress);

  useEffect(() => window.history.replaceState(null, "", addressOf(selected)), [selected]);

  const handoff =
    selected?.kind === "conversation" && selected.handoffId
      ? queue.data?.open_handoffs.find((h) => h.trusted.handoff_id === selected.handoffId)
      : undefined;

  return (
    <div className="columns">
      <section className="panel" aria-labelledby="queue-title">
        <h2 id="queue-title">Queue</h2>
        {queue.problem && <p className="notice warn">{queue.problem}</p>}
        {!queue.data ? (
          !queue.problem && <p role="status">Loading the queue…</p>
        ) : (
          <div className="stack">
            <div>
              <h3>Waiting for approval ({queue.data.awaiting_approval.length})</h3>
              {queue.data.awaiting_approval.length === 0 && <p className="muted">Nothing to approve.</p>}
              <ul className="queue">
                {queue.data.awaiting_approval.map(({ trusted }) => (
                  <li key={trusted.proposal_id}>
                    <button
                      type="button"
                      className="row"
                      aria-current={selected?.kind === "proposal" && selected.id === trusted.proposal_id}
                      onClick={() => setSelected({ kind: "proposal", id: trusted.proposal_id })}
                    >
                      <strong>{formatMoney(trusted.amount_minor, trusted.currency)}</strong> · {trusted.customer.display_name}
                      <span className="muted">
                        {trusted.proposal_id} · expires {formatTime(trusted.expires_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            {queue.data.untold_decisions.length > 0 && (
              <div>
                <h3>Decisions the assistant has not been told of ({queue.data.untold_decisions.length})</h3>
                <p className="muted">Its delivery failed; it is tried again a few times, then stops. Take over if needed.</p>
                <ul className="queue">
                  {queue.data.untold_decisions.map((untold) => (
                    <li key={untold.proposal_id}>
                      <button
                        type="button"
                        className="row"
                        onClick={() => setSelected({ kind: "conversation", id: untold.conversation_id })}
                      >
                        <strong>{untold.decision === "approved" ? "Approved" : "Rejected"}</strong> · {untold.proposal_id}
                        <span className="muted">
                          {untold.attempts} attempt{untold.attempts === 1 ? "" : "s"} · {untold.last_error}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h3>Handed to a person ({queue.data.open_handoffs.length})</h3>
              {queue.data.open_handoffs.length === 0 && <p className="muted">No open cases.</p>}
              <ul className="queue">
                {queue.data.open_handoffs.map(({ trusted }) => (
                  <li key={trusted.handoff_id}>
                    <button
                      type="button"
                      className="row"
                      aria-current={selected?.kind === "conversation" && selected.handoffId === trusted.handoff_id}
                      onClick={() =>
                        setSelected({ kind: "conversation", id: trusted.conversation_id, handoffId: trusted.handoff_id })
                      }
                    >
                      <strong>{ORIGIN[trusted.origin]}</strong> · {trusted.customer_id}
                      <span className="muted">
                        {trusted.handoff_id} · {formatTime(trusted.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </section>
      <section className="panel" aria-label="Details">
        {!selected && <p className="muted">Choose a request or a case from the queue.</p>}
        {selected?.kind === "proposal" && (
          <ProposalDetail
            key={selected.id}
            proposalId={selected.id}
            onOpenConversation={(id) => setSelected({ kind: "conversation", id })}
            onChange={queue.refresh}
          />
        )}
        {selected?.kind === "conversation" && (
          <ConversationDetail
            key={selected.id}
            conversationId={selected.id}
            handoff={handoff}
            onOpenProposal={(id) => setSelected({ kind: "proposal", id })}
            onChange={queue.refresh}
          />
        )}
      </section>
    </div>
  );
}

const ORIGIN: Record<QueuedHandoff["trusted"]["origin"], string> = {
  customer: "The customer asked for a person",
  agent: "The assistant handed it over",
  staff: "A staff member took over",
};

/** Text nobody verified, with who wrote it. Always plain text: never markup, never a button. */
function Unverified({ by, children }: { by: string; children: ReactNode }) {
  return (
    <div className="unverified">
      <p className="unverified-label">Not verified · written by {by}</p>
      {children}
    </div>
  );
}

function ProposalDetail(props: { proposalId: string; onOpenConversation: (id: string) => void; onChange: () => Promise<void> }) {
  const { proposalId, onOpenConversation, onChange } = props;
  const found = usePolling<StaffProposal>(() => api.staffProposal(proposalId), DETAIL_EVERY_MS, proposalId);
  const [acting, setActing] = useState(false);
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState(""); // a rejection's reason, shown to the customer and passed on by the agent

  async function decide(decision: "approved" | "rejected") {
    setActing(true);
    setNotice("");
    try {
      await api.decide(proposalId, decision, decision === "rejected" ? reason.trim() : undefined);
      setReason("");
    } catch (error) {
      setNotice(sentence(error)); // e.g. it expired or the customer cancelled: the card shows the stored state
    } finally {
      setActing(false);
      await found.refresh();
      await onChange();
    }
  }

  if (!found.data) {
    return found.problem ? <p role="alert" className="notice error">{found.problem}</p> : <p role="status">Loading…</p>;
  }
  const { trusted, untrusted } = found.data;
  const waiting = trusted.display_status === "awaiting_staff_approval";
  return (
    <div className="stack">
      <h2>Refund request {trusted.proposal_id}</h2>
      {found.problem && <p className="notice warn">{found.problem}</p>}
      <div className="trusted">
        <p className="trusted-label">Checked by the backend</p>
        <dl className="facts">
          <dt>Customer</dt>
          <dd>
            {trusted.customer.display_name} <span className="muted">({trusted.customer.email}, {trusted.customer.id})</span>
          </dd>
          <dt>Order</dt>
          <dd>{trusted.order_id}</dd>
          <dt>Customer confirmed</dt>
          <dd>{trusted.customer_confirmed_at ? formatTime(trusted.customer_confirmed_at) : "Not yet"}</dd>
          <dt>Policy version</dt>
          <dd>{trusted.policy_version}</dd>
        </dl>
        <ProposalCardView card={trusted} viewer="staff">
          {waiting && (
            <div className="actions">
              <button type="button" disabled={acting} onClick={() => decide("approved")}>
                Approve refund of {formatMoney(trusted.amount_minor, trusted.currency)}
              </button>
              <label htmlFor="rejection-reason">Reason for the customer, needed to reject</label>
              <textarea
                id="rejection-reason"
                rows={2}
                maxLength={500}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <button
                type="button"
                className="danger"
                disabled={acting || reason.trim() === ""}
                onClick={() => decide("rejected")}
              >
                Reject
              </button>
            </div>
          )}
        </ProposalCardView>
      </div>
      {notice && (
        <p role="alert" className="notice error">
          {notice}
        </p>
      )}
      <Unverified by="the AI assistant (its summary changes nothing that is paid)">
        <p className="text">{untrusted.agent_summary || "(no summary)"}</p>
      </Unverified>
      {untrusted.seller_message && (
        <Unverified by="the seller">
          <p className="text">{untrusted.seller_message}</p>
        </Unverified>
      )}
      <p>
        <button type="button" className="quiet" onClick={() => onOpenConversation(trusted.conversation_id)}>
          Read the conversation and its history
        </button>
      </p>
    </div>
  );
}

interface ConversationProps {
  conversationId: string;
  handoff?: QueuedHandoff;
  onOpenProposal: (id: string) => void;
  onChange: () => Promise<void>;
}

function ConversationDetail({ conversationId, handoff, onOpenProposal, onChange }: ConversationProps) {
  const found = usePolling<StaffConversation>(
    () => api.staffConversation(conversationId),
    DETAIL_EVERY_MS,
    conversationId,
  );
  const [acting, setActing] = useState(false);
  const [notice, setNotice] = useState("");
  const [askingTakeover, setAskingTakeover] = useState(false);
  const titles = usePolicyTitles();

  async function act(action: () => Promise<unknown>) {
    setActing(true);
    setNotice("");
    try {
      await action();
    } catch (error) {
      setNotice(sentence(error));
    } finally {
      setActing(false);
      setAskingTakeover(false);
      await found.refresh();
      await onChange();
    }
  }

  if (!found.data) {
    return found.problem ? <p role="alert" className="notice error">{found.problem}</p> : <p role="status">Loading…</p>;
  }
  const data = found.data;
  const human = data.control === "human_controlled";
  return (
    <div className="stack">
      <h2>Conversation {data.conversation_id}</h2>
      {found.problem && <p className="notice warn">{found.problem}</p>}
      <p className="trusted inline">
        <span className="trusted-label">Checked by the backend</span> Customer {data.customer.display_name} (
        {data.customer.email}, {data.customer.id}) ·{" "}
        {human ? "handled by a person: the assistant makes no more changes" : "handled by the assistant"}
      </p>
      {handoff && <HandoffDetail handoff={handoff} history={data.history} acting={acting} onTake={act} />}
      {!human && !askingTakeover && (
        <p>
          <button type="button" className="quiet" onClick={() => setAskingTakeover(true)}>
            Take over this conversation
          </button>
        </p>
      )}
      {!human && askingTakeover && (
        <div className="notice info stack" role="group" aria-label="Take over">
          <p>The assistant stops making changes, and any request still open here is closed without payment.</p>
          <div className="actions">
            <button type="button" disabled={acting} onClick={() => act(() => api.takeOver(conversationId))}>
              Yes, take over
            </button>
            <button type="button" className="quiet" onClick={() => setAskingTakeover(false)}>
              Keep the assistant
            </button>
          </div>
        </div>
      )}
      {notice && (
        <p role="alert" className="notice error">
          {notice}
        </p>
      )}
      <h3>Requests</h3>
      {data.proposals.length === 0 && <p className="muted">No refund request in this conversation.</p>}
      {data.proposals.map((card) => (
        <ProposalCardView key={card.proposal_id} card={card} viewer="staff">
          {card.display_status === "awaiting_staff_approval" && (
            <button type="button" onClick={() => onOpenProposal(card.proposal_id)}>
              Review for approval
            </button>
          )}
        </ProposalCardView>
      ))}
      <h3>Messages</h3>
      <Unverified by="the customer and the AI assistant">
        {data.messages.length === 0 && <p className="muted">No messages.</p>}
        <ol className="transcript">
          {data.messages.map((message, index) => (
            <li key={index}>
              <span className="author">
                {message.author === "customer" ? "Customer" : "Assistant"} · {formatTime(message.at)}
              </span>
              <p className="text">
                {message.author === "customer" ? (
                  message.content_untrusted
                ) : (
                  <ChatText text={message.content_untrusted} titles={titles} viewer="staff" />
                )}
              </p>
            </li>
          ))}
        </ol>
      </Unverified>
      <h3>History</h3>
      <History events={data.history} />
    </div>
  );
}

function HandoffDetail(props: {
  handoff: QueuedHandoff;
  history: HistoryEvent[];
  acting: boolean;
  onTake: (action: () => Promise<unknown>) => Promise<void>;
}) {
  const { trusted, untrusted } = props.handoff;
  // Who recorded it: a "customer" origin written through the assistant's tool is the assistant's claim.
  const recorded = props.history.find((e) => e.event === "hand_off" && e.details.handoff_id === trusted.handoff_id);
  const claimed = trusted.origin === "customer" && recorded?.actor_type === "agent";
  // The customer's button writes a fixed reason in the backend; anything else was written by the model.
  const byButton = recorded?.actor_type === "customer";
  return (
    <div className="stack">
      <div className="trusted">
        <p className="trusted-label">Checked by the backend</p>
        <dl className="facts">
          <dt>Case</dt>
          <dd>
            {trusted.handoff_id} · {formatTime(trusted.created_at)}
          </dd>
          <dt>Origin</dt>
          <dd>
            {ORIGIN[trusted.origin]}
            {claimed && " (according to the assistant)"}
          </dd>
          {byButton && (
            <>
              <dt>Reason</dt>
              <dd>The customer pressed Talk to a person.</dd>
            </>
          )}
          <dt>Request it closed</dt>
          <dd>{trusted.pending_proposal_id ?? "None"}</dd>
          <dt>Earlier actions</dt>
          <dd>
            {trusted.prior_actions.length === 0
              ? "None"
              : trusted.prior_actions.map((a) => `${EVENT[a.event] ?? a.event}${a.proposal_id ? ` (${a.proposal_id})` : ""}`).join(", ")}
          </dd>
        </dl>
        <div className="actions">
          <button
            type="button"
            disabled={props.acting}
            onClick={() => props.onTake(() => api.takeHandoff(trusted.handoff_id))}
          >
            Take this case
          </button>
        </div>
      </div>
      {!byButton && (
        <Unverified by="the AI assistant">
          <dl className="facts">
            <dt>Reason</dt>
            <dd className="text">{untrusted.reason || "(none)"}</dd>
            <dt>What the customer wants</dt>
            <dd className="text">{untrusted.customer_goal || "(none)"}</dd>
            <dt>Facts it says were confirmed</dt>
            <dd className="text">{untrusted.confirmed_facts || "(none)"}</dd>
            <dt>Decision needed</dt>
            <dd className="text">{untrusted.decision_needed || "(none)"}</dd>
          </dl>
        </Unverified>
      )}
    </div>
  );
}

// The audit log's event names (refund_agent/refunds.py), in words.
const EVENT: Record<string, string> = {
  open_conversation: "Conversation opened",
  propose: "Proposal made",
  confirm: "Customer's decision",
  decide: "Staff decision",
  execute: "Refund executed",
  cancel: "Cancelled by the customer",
  expire: "Expired",
  superseded: "Replaced by a newer proposal",
  handed_off: "Closed by a handoff",
  hand_off: "Handed to a person",
  take_handoff: "Case taken",
};

function History({ events }: { events: HistoryEvent[] }) {
  if (events.length === 0) return <p className="muted">No events.</p>;
  return (
    <div className="scroll">
      <table className="history">
        <thead>
          <tr>
            <th scope="col">When</th>
            <th scope="col">Who</th>
            <th scope="col">What</th>
            <th scope="col">Outcome</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, index) => (
            <tr key={index} className={event.outcome}>
              <td>{formatTime(event.at)}</td>
              <td>
                {event.actor_type}
                {event.actor_id && <span className="muted"> {event.actor_id}</span>}
              </td>
              <td>
                {EVENT[event.event] ?? event.event} <code className="muted">{event.event}</code>
              </td>
              <td>{event.outcome === "rejected" ? `Refused: ${event.reason ?? "?"}` : "Done"}</td>
              <td>
                {[
                  event.proposal_id,
                  event.operation_id,
                  ...Object.entries(event.details).map(([key, value]) => `${key}: ${JSON.stringify(value)}`),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
