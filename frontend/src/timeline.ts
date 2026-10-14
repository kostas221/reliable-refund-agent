// Where a proposal card goes among the messages. A turn of the agent writes its messages when it ends, after the
// proposal it made in the middle, so ordering by time alone would put the card before the customer's own request.
// A card therefore follows the first agent message written at or after it; one whose turn has not ended yet goes last.

import type { Message, ProposalCard } from "./types";

export type Entry = { kind: "message"; message: Message; key: string } | { kind: "card"; card: ProposalCard; key: string };

export function timeline(messages: Message[], cards: ProposalCard[]): Entry[] {
  const waiting = [...cards].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const entries: Entry[] = [];
  messages.forEach((message, index) => {
    entries.push({ kind: "message", message, key: `m${index}` });
    if (message.author !== "agent") return;
    while (waiting.length > 0 && Date.parse(waiting[0]!.created_at) <= Date.parse(message.at)) {
      const card = waiting.shift()!;
      entries.push({ kind: "card", card, key: card.proposal_id });
    }
  });
  for (const card of waiting) entries.push({ kind: "card", card, key: card.proposal_id });
  return entries;
}
