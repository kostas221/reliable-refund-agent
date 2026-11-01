// The banner on every screen: who answers in the chat and what a payment is (closing plan, section 3). A person
// trying the demo must know whether a fixed script or a language model is answering, that no money moves, and,
// when a paid session has stopped, that nothing they did is lost.

import type { Mode } from "./types";

export interface Banner {
  tone: "info" | "warn";
  lines: string[];
}

const PAYMENTS = "Payments are simulated in a test ledger: no money moves.";

function dollars(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

export function modeBanner(mode: Mode): Banner {
  if (mode.agent === "model") {
    const lines = [`Live mode: a language model (${mode.model}) answers in the chat. ${PAYMENTS}`];
    if (mode.budget) {
      lines.push(`Model spending: ${dollars(mode.budget.spent_usd)} of ${dollars(mode.budget.limit_usd)}.`);
    }
    if (mode.paused) {
      const waiting = mode.decisions_waiting;
      lines.push(
        "The assistant is paused: this session's model budget or credit is used up. Messages, confirmations " +
          "and staff decisions are kept and are answered when the session's owner starts it again" +
          (waiting ? ` (${waiting} staff decision${waiting === 1 ? "" : "s"} waiting).` : "."),
      );
      return { tone: "warn", lines };
    }
    return { tone: "info", lines };
  }
  if (mode.agent === "scripted") {
    return { tone: "info", lines: [`Demo mode: the assistant follows a fixed script, not a language model. ${PAYMENTS}`] };
  }
  return { tone: "info", lines: [`The assistant is not running. ${PAYMENTS}`] };
}
