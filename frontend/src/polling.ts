// The screens read the backend again every few seconds (plan section 8: polling is enough for v1). The backend is
// the only source: a failed read keeps the last answer on screen and says so, and never invents a newer state.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, describe } from "./api";

export interface Polled<T> {
  data: T | undefined;
  problem: string; // why the last read failed; empty when it worked
  refresh: () => Promise<void>;
}

/**
 * Reads that may overlap (the timer's and one after a button), of which only the newest started may set the screen:
 * an older answer that arrives last is dropped, so the screen never steps back to a state already replaced (review
 * of 2026-10-19, R8). `reading` holds while any read is under way.
 */
export function newestAnswers<T>(apply: (value: T) => void, fail: (error: unknown) => void) {
  let latest = 0;
  let underWay = 0;
  return {
    get reading(): boolean {
      return underWay > 0;
    },
    async read(load: () => Promise<T>, stillWanted: () => boolean = () => true): Promise<void> {
      const mine = ++latest;
      underWay += 1;
      try {
        const value = await load();
        if (mine === latest && stillWanted()) apply(value);
      } catch (error) {
        if (mine === latest && stillWanted()) fail(error);
      } finally {
        underWay -= 1;
      }
    },
  };
}

/** Reads `load` at once and every `everyMs`. A new `key` starts over; a null `load` reads nothing. */
export function usePolling<T>(load: (() => Promise<T>) | null, everyMs: number, key: string): Polled<T> {
  const [data, setData] = useState<T>();
  const [problem, setProblem] = useState("");
  const current = useRef(load);
  current.current = load;
  const round = useRef(0); // answers of an earlier key are dropped
  const reads = useRef(
    newestAnswers<T>(
      (value) => {
        setData(value);
        setProblem("");
      },
      (error) => setProblem(error instanceof ApiError ? describe(error.failure) : String(error)),
    ),
  );

  const refresh = useCallback(async () => {
    const read = current.current;
    if (!read) return;
    const mine = round.current;
    await reads.current.read(read, () => mine === round.current);
  }, []);

  useEffect(() => {
    round.current += 1;
    setData(undefined);
    setProblem("");
    if (!current.current) return;
    void refresh();
    const timer = setInterval(() => {
      if (!reads.current.reading && document.visibilityState === "visible") void refresh();
    }, everyMs);
    return () => {
      clearInterval(timer);
      round.current += 1;
    };
  }, [key, everyMs, refresh]);

  return { data, problem, refresh };
}
