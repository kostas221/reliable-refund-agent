// The CSRF token on changes: a page that lost it reads it again from its own session and tries once more; any
// other refusal is final. The network is replaced, so the test sees every request in order.

import { afterEach, expect, test, vi } from "vitest";

import { ApiError, api } from "./api";

type Seen = { method: string; path: string; token: string | null };

function answer(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function network(reply: (method: string, path: string, token: string | null) => Response): Seen[] {
  const seen: Seen[] = [];
  vi.stubGlobal("fetch", async (path: string, init: RequestInit) => {
    const token = (init.headers as Record<string, string>)["X-CSRF-Token"] ?? null;
    const method = init.method ?? "GET";
    seen.push({ method, path, token });
    return reply(method, path, token);
  });
  return seen;
}

const session = (token: string) =>
  answer(200, { user_id: "d01-ana", role: "customer", display_name: "Ana Lima", csrf_token: token });
const WRONG_TOKEN = { detail: "missing or wrong X-CSRF-Token header" };
const CONFIRMATION = "/api/proposals/prop-1/confirmation";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a change without a token reads it from the session first, then is sent once", async () => {
  const seen = network((_method, path) =>
    path === "/api/session" ? session("first") : answer(200, { proposal_id: "prop-1", status: "awaiting_staff_approval" }),
  );
  await api.confirm("prop-1", "confirmed");
  expect(seen).toEqual([
    { method: "GET", path: "/api/session", token: null },
    { method: "POST", path: CONFIRMATION, token: "first" },
  ]);
});

test("a token the backend refuses is read again and the change is tried once more", async () => {
  const seen = network((_method, path, token) => {
    if (path === "/api/session") return session("second");
    return token === "second" ? answer(200, { proposal_id: "prop-1", status: "awaiting_staff_approval" }) : answer(403, WRONG_TOKEN);
  });
  await api.confirm("prop-1", "confirmed");
  expect(seen.map((s) => `${s.method} ${s.path} ${s.token}`)).toEqual([
    `POST ${CONFIRMATION} first`,
    "GET /api/session null",
    `POST ${CONFIRMATION} second`,
  ]);
});

test("a token refused twice is a failure, not a loop", async () => {
  const seen = network((_method, path) => (path === "/api/session" ? session("third") : answer(403, WRONG_TOKEN)));
  await expect(api.confirm("prop-1", "confirmed")).rejects.toBeInstanceOf(ApiError);
  expect(seen.filter((s) => s.method === "POST")).toHaveLength(2);
});

test("any other refusal is final and not tried again", async () => {
  const seen = network(() => answer(403, { detail: "this door is for customers" }));
  await expect(api.decide("prop-1", "approved")).rejects.toMatchObject({ failure: { kind: "refused", status: 403 } });
  expect(seen).toHaveLength(1);
});
