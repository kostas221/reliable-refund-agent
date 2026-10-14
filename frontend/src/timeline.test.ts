import { expect, test } from "vitest";

import { card } from "./testCards";
import { timeline } from "./timeline";
import type { Message } from "./types";

const said = (author: Message["author"], text: string, at: string): Message => ({ author, content_untrusted: text, at });

test("a card follows the agent's message of the turn that made it, not the customer's request", () => {
  // One turn: the proposal is made at 10:00:05, both messages are written when the turn ends at 10:00:09.
  const messages = [
    said("customer", "Refund my mug, please.", "2026-09-12T10:00:09Z"),
    said("agent", "I can refund R$ 49,90.", "2026-09-12T10:00:09Z"),
    said("customer", "Thanks!", "2026-09-12T10:01:00Z"),
  ];
  const proposal = card("awaiting_customer_confirmation", { created_at: "2026-09-12T10:00:05Z" });
  expect(timeline(messages, [proposal]).map((e) => e.key)).toEqual(["m0", "m1", "prop-1", "m2"]);
});

test("a card whose turn has not ended yet goes last", () => {
  const messages = [said("customer", "Refund my mug, please.", "2026-09-12T10:00:00Z")];
  const proposal = card("awaiting_customer_confirmation", { created_at: "2026-09-12T10:00:05Z" });
  expect(timeline(messages, [proposal]).map((e) => e.key)).toEqual(["m0", "prop-1"]);
});

test("two cards of two turns each follow their own turn", () => {
  const messages = [
    said("customer", "Refund the plate.", "2026-09-12T10:00:09Z"),
    said("agent", "Here is a request for the plate.", "2026-09-12T10:00:09Z"),
    said("customer", "And the bowl too.", "2026-09-12T10:02:09Z"),
    said("agent", "Here is a request for both.", "2026-09-12T10:02:09Z"),
  ];
  const first = card("invalidated", { proposal_id: "prop-1", created_at: "2026-09-12T10:00:05Z" });
  const second = card("awaiting_customer_confirmation", { proposal_id: "prop-2", created_at: "2026-09-12T10:02:05Z" });
  expect(timeline(messages, [second, first]).map((e) => e.key)).toEqual(["m0", "m1", "prop-1", "m2", "m3", "prop-2"]);
});
