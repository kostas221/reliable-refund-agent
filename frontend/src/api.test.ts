import { describe as group, expect, test } from "vitest";

import { describe, failureFrom } from "./api";

group("what an error answer means", () => {
  test("a refused check keeps its name, and the person reads that the state changed", () => {
    const failure = failureFrom(409, { detail: "invalid_transition", explanation: "the proposal is awaiting_staff_approval" });
    expect(failure).toEqual({
      kind: "conflict",
      check: "invalid_transition",
      explanation: "the proposal is awaiting_staff_approval",
    });
    expect(describe(failure)).toBe("This changed in the meantime. The screen now shows the current state.");
  });

  test("a busy agent's answer is passed on as written", () => {
    const busy = failureFrom(409, { detail: "the agent is still answering the previous message" });
    expect(describe(busy)).toBe("The agent is still answering the previous message.");
  });

  test("someone else's data reads exactly like missing data", () => {
    expect(failureFrom(404, { detail: "not_found" })).toEqual({ kind: "not_found" });
  });

  test("a lost session, a busy agent and a server fault are told apart", () => {
    expect(failureFrom(401, { detail: "sign in first" }).kind).toBe("signed_out");
    expect(failureFrom(503, { detail: "the agent could not answer" }).kind).toBe("unavailable");
    expect(failureFrom(500, null)).toEqual({ kind: "server", status: 500 });
  });

  test("a validation error, whose detail is a list, is still a plain refusal", () => {
    expect(failureFrom(422, { detail: [{ msg: "extra field" }] })).toEqual({
      kind: "refused",
      status: 422,
      check: "",
      explanation: "",
    });
  });

  test("a gateway that could not reach the backend counts as no answer", () => {
    expect(failureFrom(502, null)).toEqual({ kind: "offline" });
    expect(failureFrom(504, null)).toEqual({ kind: "offline" });
  });

  test("no answer at all claims nothing about what happened", () => {
    expect(describe({ kind: "offline" })).toContain("Nothing is assumed");
  });
});
