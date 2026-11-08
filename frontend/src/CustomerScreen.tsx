// The customer's screen (plan section 8, product contract section 2): the orders with their earlier requests, the
// chat with the agent, and the proposal cards with the confirm button. Everything shown is read from the backend
// and read again every few seconds, so a refresh, a server restart or a lost answer shows what is stored. The open
// conversation is kept in the page address, so a refresh reopens it.

import { type FormEvent, type RefObject, useEffect, useRef, useState } from "react";

import { ApiError, api, describe } from "./api";
import { ChatText, usePolicyTitles } from "./ChatText";
import { usePolling } from "./polling";
import { ProposalCardView } from "./ProposalCard";
import { canCancel, canConfirm, formatDay, formatMoney, formatTime, handoffNotice, requestLabel } from "./status";
import { timeline } from "./timeline";
import type { Conversation, Order, Unit } from "./types";

const ORDERS_EVERY_MS = 4000;
const CONVERSATION_EVERY_MS = 2500;

function sentence(error: unknown): string {
  return error instanceof ApiError ? describe(error.failure) : String(error);
}

function conversationInAddress(): string | null {
  const found = /conversation=([^&]+)/.exec(window.location.hash);
  return found ? decodeURIComponent(found[1]!) : null;
}

/** The chat's first message for the chosen items; the customer can change it before sending. */
export function refundRequestText(order: Order, units: Unit[]): string {
  const items = units.map((unit) => `${unit.product} (item ${unit.unit_id})`).join(", ");
  return `I would like a refund for ${items} from order ${order.order_id}.`;
}

export function CustomerScreen() {
  const orders = usePolling(api.orders, ORDERS_EVERY_MS, "orders");
  const [conversationId, setConversationId] = useState<string | null>(conversationInAddress);
  const [draft, setDraft] = useState("");
  const draftBox = useRef<HTMLTextAreaElement>(null);

  // When the page loads without a conversation in the address, the latest one the backend knows of is opened. Only
  // then: "New conversation" afterwards means an empty chat, opened in the backend with the first message.
  useEffect(() => {
    if (conversationInAddress()) return;
    api
      .conversations()
      .then((list) => list[0] && setConversationId((open) => open ?? list[0]!.conversation_id))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const address = conversationId ? `#conversation=${encodeURIComponent(conversationId)}` : window.location.pathname;
    window.history.replaceState(null, "", address);
  }, [conversationId]);

  function ask(text: string) {
    setDraft(text);
    draftBox.current?.focus();
  }

  return (
    <div className="columns">
      <section className="panel" aria-labelledby="orders-title">
        <h2 id="orders-title">Your orders</h2>
        <Orders orders={orders.data} problem={orders.problem} onAsk={ask} />
      </section>
      <section className="panel" aria-labelledby="chat-title">
        <Chat
          conversationId={conversationId}
          onOpened={setConversationId}
          onStartOver={() => setConversationId(null)}
          draft={draft}
          setDraft={setDraft}
          draftBox={draftBox}
          onChange={orders.refresh}
        />
      </section>
    </div>
  );
}

function Orders({ orders, problem, onAsk }: { orders?: Order[]; problem: string; onAsk: (text: string) => void }) {
  const [picked, setPicked] = useState<Set<string>>(new Set());

  if (!orders) {
    return problem ? <p role="alert" className="notice error">{problem}</p> : <p role="status">Loading your orders…</p>;
  }
  if (orders.length === 0) return <p>You have no orders.</p>;

  function toggle(unitId: string) {
    setPicked((before) => {
      const after = new Set(before);
      if (!after.delete(unitId)) after.add(unitId);
      return after;
    });
  }

  return (
    <div className="stack">
      {problem && <p className="notice warn">{problem} Showing the last answer.</p>}
      {orders.map((order) => {
        const chosen = order.units.filter((unit) => picked.has(unit.unit_id));
        return (
          <article key={order.order_id} className="order">
            <h3>Order {order.order_id}</h3>
            <p className="muted">
              Bought {formatDay(order.purchased_at)} ·{" "}
              {order.delivered_at ? `delivered ${formatDay(order.delivered_at)}` : "not delivered yet"}
            </p>
            <fieldset className="units">
              <legend>Items: choose the ones to refund</legend>
              {order.units.map((unit) => (
                <label key={unit.unit_id} className="unit">
                  <input
                    type="checkbox"
                    checked={picked.has(unit.unit_id)}
                    disabled={unit.refunded}
                    onChange={() => toggle(unit.unit_id)}
                  />
                  <span className="grow">
                    {unit.product} <span className="muted">({unit.unit_id})</span>
                  </span>
                  <span>{formatMoney(unit.paid_minor, order.currency)}</span>
                  <span className="tag">{unit.refunded ? "Refunded" : unit.received_back ? "Returned" : "Not returned"}</span>
                </label>
              ))}
            </fieldset>
            <button
              type="button"
              disabled={chosen.length === 0}
              onClick={() => {
                onAsk(refundRequestText(order, chosen));
                setPicked(new Set());
              }}
            >
              Ask for a refund{chosen.length > 0 && ` of ${chosen.length} item${chosen.length > 1 ? "s" : ""}`}
            </button>
            {order.requests.length > 0 && (
              <div>
                <h4>Requests for this order</h4>
                <ul className="requests">
                  {order.requests.map((request) => (
                    <li key={request.proposal_id}>
                      <span className="muted">{formatTime(request.created_at)}</span> {requestLabel(request)}
                      {request.amount_minor !== null && ` · ${formatMoney(request.amount_minor, order.currency)}`}
                      <span className="muted"> · {request.unit_ids.join(", ")}</span>
                      {request.rejection_reason && <span> · Reason: {request.rejection_reason}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

interface ChatProps {
  conversationId: string | null;
  onOpened: (id: string) => void;
  onStartOver: () => void;
  draft: string;
  setDraft: (text: string) => void;
  draftBox: RefObject<HTMLTextAreaElement | null>;
  onChange: () => Promise<void>;
}

function Chat({ conversationId, onOpened, onStartOver, draft, setDraft, draftBox, onChange }: ChatProps) {
  const load = conversationId ? () => api.conversation(conversationId) : null;
  const conversation = usePolling<Conversation>(load, CONVERSATION_EVERY_MS, conversationId ?? "none");
  const [sending, setSending] = useState<string | null>(null); // the customer's own text, until the backend has it
  const [notice, setNotice] = useState("");
  const [acting, setActing] = useState(false);
  const [askingForPerson, setAskingForPerson] = useState(false);
  const data = conversation.data;

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending !== null) return;
    setNotice("");
    setSending(text);
    setDraft("");
    let id = conversationId;
    try {
      if (!id) {
        id = (await api.openConversation()).conversation_id;
        onOpened(id);
      }
      await api.say(id, text);
    } catch (error) {
      setNotice(sentence(error));
      // A lost answer proves nothing either way: the text goes back into the box only if the backend did not keep it.
      const stored = id ? await api.conversation(id).catch(() => null) : null;
      const last = stored?.messages.filter((m) => m.author === "customer").at(-1);
      if (last?.content_untrusted !== text) setDraft(text);
    } finally {
      setSending(null);
      await conversation.refresh();
      await onChange();
    }
  }

  async function act(action: () => Promise<unknown>) {
    setActing(true);
    setNotice("");
    try {
      await action();
    } catch (error) {
      setNotice(sentence(error)); // e.g. it changed in the meantime: the card below shows the stored state
    } finally {
      setActing(false);
      await conversation.refresh();
      await onChange();
    }
  }

  const human = data?.control === "human_controlled";
  const titles = usePolicyTitles();
  const withPerson = data ? handoffNotice(data.control, data.handoffs) : null;
  return (
    <div className="stack">
      <div className="chat-head">
        <h2 id="chat-title">Conversation</h2>
        {conversationId && (
          <button type="button" className="quiet" onClick={onStartOver}>
            New conversation
          </button>
        )}
      </div>
      {!conversationId && <p className="muted">Choose items on the left, or write to the assistant below.</p>}
      {conversation.problem && <p className="notice warn">{conversation.problem}</p>}
      {withPerson && (
        <p className="notice info" role="status">
          <strong>{withPerson.label}.</strong> {withPerson.detail}
        </p>
      )}
      {data && (
        <ol className="log" role="log" aria-label="Conversation" aria-live="polite">
          {timeline(data.messages, data.proposals).map((entry) =>
            entry.kind === "message" ? (
              <li key={entry.key} className={`message ${entry.message.author}`}>
                <span className="author">{entry.message.author === "customer" ? "You" : "Assistant"}</span>
                <p className="text">
                  {entry.message.author === "customer" ? (
                    entry.message.content_untrusted
                  ) : (
                    <ChatText text={entry.message.content_untrusted} titles={titles} viewer="customer" />
                  )}
                </p>
              </li>
            ) : (
              <li key={entry.key}>
                <ProposalCardView card={entry.card}>
                  {canConfirm(entry.card) && (
                    <div className="actions">
                      <button
                        type="button"
                        disabled={acting}
                        onClick={() => act(() => api.confirm(entry.card.proposal_id, "confirmed"))}
                      >
                        Confirm refund of {formatMoney(entry.card.amount_minor, entry.card.currency)}
                      </button>
                      <button
                        type="button"
                        className="quiet"
                        disabled={acting}
                        onClick={() => act(() => api.confirm(entry.card.proposal_id, "declined"))}
                      >
                        Decline
                      </button>
                    </div>
                  )}
                  {canCancel(entry.card) && (
                    <div className="actions">
                      <button
                        type="button"
                        className="quiet"
                        disabled={acting}
                        onClick={() => act(() => api.cancel(entry.card.proposal_id))}
                      >
                        Cancel this request
                      </button>
                    </div>
                  )}
                </ProposalCardView>
              </li>
            ),
          )}
          {sending !== null && (
            <li className="message customer sending">
              <span className="author">You · sending…</span>
              <p className="text">{sending}</p>
            </li>
          )}
        </ol>
      )}
      {sending !== null && !human && (
        <p role="status" className="muted">
          The assistant is answering…
        </p>
      )}
      {notice && (
        <p role="alert" className="notice error">
          {notice}
        </p>
      )}
      <form onSubmit={send} className="stack">
        <label>
          Message
          <textarea
            ref={draftBox}
            rows={3}
            maxLength={2000}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
        </label>
        <div className="actions">
          <button type="submit" disabled={sending !== null || draft.trim() === ""}>
            Send
          </button>
          {conversationId && !human && !askingForPerson && (
            <button type="button" className="quiet" onClick={() => setAskingForPerson(true)}>
              Talk to a person
            </button>
          )}
        </div>
      </form>
      {askingForPerson && conversationId && !human && (
        <div className="notice info stack" role="group" aria-label="Talk to a person">
          <p>
            A staff member takes over this conversation and writes to you by email, at the address of your account. Any
            request still open here is closed, and nothing is paid for it; the staff member decides what happens next.
          </p>
          <div className="actions">
            <button
              type="button"
              disabled={acting}
              onClick={() => act(() => api.askForPerson(conversationId)).then(() => setAskingForPerson(false))}
            >
              Yes, talk to a person
            </button>
            <button type="button" className="quiet" onClick={() => setAskingForPerson(false)}>
              Keep chatting
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
