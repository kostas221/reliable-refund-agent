import { describe, expect, test } from "vitest";

import { type Part, messageParts } from "./messageText";

const TITLES = new Map([
  ["refund-policy/v2/return", "Items must be returned first"],
  ["refund-policy/v2/amount", "Refund amount"],
  ["refund-policy/v2/approval", "Confirmation and approval"],
]);

const text = (value: string, strong = false): Part => ({ kind: "text", text: value, strong });
const cited = (citation: string, strong = false): Part => ({
  kind: "citation",
  citation,
  title: TITLES.get(citation)!,
  strong,
});

/** What the model wrote, rebuilt from the parts: the bold marks are the only characters a screen may leave out. */
function written(parts: Part[]): string {
  return parts.map((part) => (part.kind === "text" ? part.text : part.citation)).join("");
}

describe("bold text, as the model marks it", () => {
  test("plain text is one part", () => {
    expect(messageParts("Your refund is on its way.", TITLES)).toEqual([text("Your refund is on its way.")]);
  });

  test("text between pairs of asterisks is bold, and the marks are not shown", () => {
    expect(messageParts("Your **BRL 99.90** refund", TITLES)).toEqual([
      text("Your "),
      text("BRL 99.90", true),
      text(" refund"),
    ]);
    expect(messageParts("**a** and **b**", TITLES)).toEqual([text("a", true), text(" and "), text("b", true)]);
  });

  test("an unpaired mark, or a pair across a line break, stays as written", () => {
    expect(messageParts("2 ** 3 is eight, **really", TITLES)).toEqual([text("2 ** 3 is eight, **really")]);
    expect(messageParts("**one\ntwo**", TITLES)).toEqual([text("**one\ntwo**")]);
  });
});

describe("policy citations, shown by their titles", () => {
  test("a known citation becomes a part of its own, with the title the backend gave", () => {
    expect(messageParts("They must reach us first (refund-policy/v2/return).", TITLES)).toEqual([
      text("They must reach us first ("),
      cited("refund-policy/v2/return"),
      text(")."),
    ]);
  });

  test("several citations in one bracket are each shown", () => {
    expect(messageParts("(refund-policy/v2/amount, refund-policy/v2/approval)", TITLES)).toEqual([
      text("("),
      cited("refund-policy/v2/amount"),
      text(", "),
      cited("refund-policy/v2/approval"),
      text(")"),
    ]);
  });

  test("an ID the policy does not hold stays as written, so nothing the model wrote is hidden", () => {
    expect(messageParts("See refund-policy/v9/other.", TITLES)).toEqual([text("See refund-policy/v9/other.")]);
    expect(messageParts("See refund-policy/v2/return.", new Map())).toEqual([text("See refund-policy/v2/return.")]);
  });

  test("a citation inside bold text keeps the bold", () => {
    expect(messageParts("**Rule refund-policy/v2/return**", TITLES)).toEqual([
      text("Rule ", true),
      cited("refund-policy/v2/return", true),
    ]);
  });
});

describe("the model's text stays text", () => {
  test("markup is never read as markup", () => {
    const attack = '<img src=x onerror="alert(1)"> **<b>bold</b>**';
    const parts = messageParts(attack, TITLES);
    expect(parts).toEqual([text('<img src=x onerror="alert(1)"> '), text("<b>bold</b>", true)]);
  });

  test.each([
    "",
    "Plain.",
    "Your **BRL 99.90** refund (refund-policy/v2/amount) is **done**.",
    "** (refund-policy/v2/return) **unpaired",
    "(refund-policy/v9/other) and refund-policy/v2/approval",
  ])("nothing but the bold marks is left out of %j", (message) => {
    expect(written(messageParts(message, TITLES)).replaceAll("**", "")).toBe(message.replaceAll("**", ""));
  });
});
