// A refund proposal as the backend stored it: the items and amounts it computed, its state in words, the policy
// sections behind a refusal, and the receipt only once the refund is committed. The buttons come from the screen
// that shows the card, since a customer and a staff member may do different things with it.

import type { ReactNode } from "react";

import { type Viewer, cardStatus, formatMoney, formatTime, isOpen } from "./status";
import type { ProposalCard } from "./types";

interface Props {
  card: ProposalCard;
  viewer?: Viewer;
  children?: ReactNode;
}

export function ProposalCardView({ card, viewer = "customer", children }: Props) {
  const status = cardStatus(card, viewer);
  // A request the policy refused promises nothing, so it shows no amounts (as the agent's tool does).
  const promised = card.status !== "ineligible";
  return (
    <article className={`card ${status.tone}`} aria-label={`Refund request ${card.proposal_id}`}>
      <header className="card-head">
        <strong>Refund request</strong>
        <span className="muted">
          {card.proposal_id} · order {card.order_id}
        </span>
      </header>
      <ul className="lines">
        {card.units.map((unit) => (
          <li key={unit.unit_id}>
            <span>
              {unit.product} <span className="muted">({unit.unit_id})</span>
            </span>
            {promised && <span>{formatMoney(unit.amount_minor, card.currency)}</span>}
          </li>
        ))}
      </ul>
      {promised && (
        <p className="total">
          Total <strong>{formatMoney(card.amount_minor, card.currency)}</strong>
        </p>
      )}
      <p className="state">
        <span className="badge">{status.label}</span> {status.detail}
      </p>
      {card.policy_citations.length > 0 && (
        <p className="cite">
          Policy:{" "}
          {card.policy_citations.map((c, i) => (
            <span key={c.citation}>
              {i > 0 && "; "}
              {c.title ?? "Section"} <code>{c.citation}</code>
            </span>
          ))}
        </p>
      )}
      {isOpen(card) && <p className="muted">Valid until {formatTime(card.expires_at)}.</p>}
      {children}
    </article>
  );
}
