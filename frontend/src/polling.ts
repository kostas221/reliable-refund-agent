// The screens read the backend again every few seconds (plan section 8: polling is enough for v1). The backend is
// the only source: a failed read keeps the last answer on screen and says so, and never invents a newer state.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, describe } from "./api";

export interface Polled<T> {
  data: T | undefined;
  problem: string; // why the last read failed; empty when it worked
  refresh: () => Promise<void>;
}

/** Reads `load` at once and every `everyMs`. A new `key` starts over; a null `load` reads nothing. */
export function usePolling<T>(load: (() => Promise<T>) | null, everyMs: number, key: string): Polled<T> {
  const [data, setData] = useState<T>();
  const [problem, setProblem] = useState("");
  const current = useRef(load);
  current.current = load;
  const round = useRef(0); // answers of an earlier key are dropped
  const reading = useRef(false);

  const refresh = useCallback(async () => {
    const read = current.current;
    if (!read) return;
    const mine = round.current;
    reading.current = true;
    try {
      const value = await read();
      if (mine === round.current) {
        setData(value);
        setProblem("");
      }
    } catch (error) {
      if (mine === round.current) setProblem(error instanceof ApiError ? describe(error.failure) : String(error));
    } finally {
      reading.current = false;
    }
  }, []);

  useEffect(() => {
    round.current += 1;
    setData(undefined);
    setProblem("");
    if (!current.current) return;
    void refresh();
    const timer = setInterval(() => {
      if (!reading.current && document.visibilityState === "visible") void refresh();
    }, everyMs);
    return () => {
      clearInterval(timer);
      round.current += 1;
    };
  }, [key, everyMs, refresh]);

  return { data, problem, refresh };
}
