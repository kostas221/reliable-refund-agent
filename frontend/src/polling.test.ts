import { describe, expect, test } from "vitest";

import { newestAnswers } from "./polling";

/** A read whose answer the test releases when it wants. */
function held<T>() {
  let release!: (value: T) => void;
  let refuse!: (error: unknown) => void;
  const promise = new Promise<T>((resolve, reject) => {
    release = resolve;
    refuse = reject;
  });
  return { load: () => promise, release, refuse };
}

describe("reads that overlap (review of 2026-10-19, R8)", () => {
  test("an older answer arriving last does not replace a newer one", async () => {
    const shown: string[] = [];
    const reads = newestAnswers<string>((value) => shown.push(value), () => shown.push("problem"));
    const timer = held<string>(); // the timer's read, started first
    const afterApproval = held<string>(); // the read after the button, started second
    const first = reads.read(timer.load);
    const second = reads.read(afterApproval.load);
    expect(reads.reading).toBe(true);
    afterApproval.release("refunded");
    await second;
    expect(reads.reading).toBe(true); // the older read is still under way
    timer.release("awaiting_staff_approval");
    await first;
    expect(shown).toEqual(["refunded"]);
    expect(reads.reading).toBe(false);
  });

  test("an older read's failure does not report a problem over a newer answer", async () => {
    const shown: string[] = [];
    const reads = newestAnswers<string>((value) => shown.push(value), () => shown.push("problem"));
    const old = held<string>();
    const fresh = held<string>();
    const first = reads.read(old.load);
    const second = reads.read(fresh.load);
    fresh.release("approved");
    old.refuse(new Error("network"));
    await Promise.all([first, second]);
    expect(shown).toEqual(["approved"]);
  });

  test("answers in order are all shown, and an answer no longer wanted is dropped", async () => {
    const shown: string[] = [];
    const reads = newestAnswers<string>((value) => shown.push(value), () => shown.push("problem"));
    await reads.read(async () => "one");
    await reads.read(async () => "two");
    await reads.read(async () => "three", () => false); // the screen moved to another key meanwhile
    expect(shown).toEqual(["one", "two"]);
  });
});
