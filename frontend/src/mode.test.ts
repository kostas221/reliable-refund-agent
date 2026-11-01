import { describe, expect, test } from "vitest";

import { describe as describeFailure } from "./api";
import { modeBanner } from "./mode";
import type { Mode } from "./types";

const MOCK: Mode = {
  agent: "scripted",
  model: null,
  payments: "simulated",
  budget: null,
  paused: null,
  decisions_waiting: 0,
};
const LIVE: Mode = {
  agent: "model",
  model: "gpt-6.1-sol/low",
  payments: "simulated",
  budget: { limit_usd: 2, spent_usd: 0.1234, left_usd: 1.8766 },
  paused: null,
  decisions_waiting: 0,
};

describe("every screen says who answers and that no money moves", () => {
  test.each([MOCK, LIVE, { ...MOCK, agent: null }])("the banner names the payments as simulated (%#)", (mode) => {
    expect(modeBanner(mode).lines.join(" ")).toContain("no money moves");
  });

  test("demo mode says a script answers, not a language model", () => {
    expect(modeBanner(MOCK).lines[0]).toMatch(/fixed script, not a language model/);
  });

  test("live mode names the model and what was spent of the budget", () => {
    const banner = modeBanner(LIVE);
    expect(banner.tone).toBe("info");
    expect(banner.lines[0]).toContain("gpt-6.1-sol/low");
    expect(banner.lines[1]).toBe("Model spending: $0.12 of $2.00.");
  });

  test("a paused session warns, and says nothing is lost and how many decisions wait", () => {
    const banner = modeBanner({ ...LIVE, paused: "over the limit", decisions_waiting: 2 });
    expect(banner.tone).toBe("warn");
    expect(banner.lines.at(-1)).toMatch(/paused/);
    expect(banner.lines.at(-1)).toMatch(/kept/);
    expect(banner.lines.at(-1)).toContain("2 staff decisions waiting");
  });
});

test("a message sent while the assistant is paused is said to be kept, not lost", () => {
  const said = describeFailure({ kind: "unavailable", detail: "agent_paused" });
  expect(said).toMatch(/paused/);
  expect(said).toMatch(/kept/);
  expect(said).not.toMatch(/try again/);
});
