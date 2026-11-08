// The one way the screens talk to the backend (docs/http-api.md). The session cookie travels by itself: it is
// HttpOnly, so this code cannot even read it. Every change carries the session's CSRF token. Nothing here decides
// anything; it passes on what the backend answered, and a failure says which kind it is, so a screen can say the
// right thing and read the stored state again instead of guessing.

import type {
  Conversation,
  ConversationListItem,
  Mode,
  Order,
  PolicySections,
  ProposalStatus,
  Session,
  StaffConversation,
  StaffProposal,
  StaffQueue,
} from "./types";

export type Failure =
  | { kind: "signed_out" } // 401: the session ended or never began
  | { kind: "not_found" } // 404: missing, or someone else's (the backend does not say which)
  | { kind: "conflict"; check: string; explanation: string } // 409: the state changed; read it again
  | { kind: "refused"; status: number; check: string; explanation: string } // 403 or 422
  | { kind: "unavailable"; detail: string } // 503: the agent could not answer; the message is kept
  | { kind: "server"; status: number } // any other 5xx
  | { kind: "offline" }; // no answer arrived: the request may or may not have been carried out

export class ApiError extends Error {
  constructor(readonly failure: Failure) {
    super(describe(failure));
  }
}

/** What an HTTP error answer means. FastAPI sends {"detail": text}; a refused check also sends "explanation". */
export function failureFrom(status: number, payload: unknown): Failure {
  const body = typeof payload === "object" && payload !== null ? (payload as Record<string, unknown>) : {};
  const detail = typeof body.detail === "string" ? body.detail : "";
  const explanation = typeof body.explanation === "string" ? body.explanation : "";
  if (status === 401) return { kind: "signed_out" };
  if (status === 404) return { kind: "not_found" };
  if (status === 409) return { kind: "conflict", check: detail, explanation };
  // The development proxy (or any gateway) could not reach the backend, or got no answer in time: whether the
  // request was carried out is unknown, exactly as when no answer arrives.
  if (status === 502 || status === 504) return { kind: "offline" };
  if (status === 503) return { kind: "unavailable", detail };
  if (status >= 500) return { kind: "server", status };
  return { kind: "refused", status, check: detail, explanation };
}

/** A sentence for the person at the screen. */
export function describe(failure: Failure): string {
  switch (failure.kind) {
    case "signed_out":
      return "You are signed out. Please sign in again.";
    case "not_found":
      return "Not found.";
    case "conflict":
      // A refused check names the state in the backend's terms, which the card already shows in words; a door's
      // own sentence (the agent is still answering) is written for people and is passed on.
      return failure.check.includes(" ")
        ? `${failure.check[0]!.toUpperCase()}${failure.check.slice(1)}.`
        : "This changed in the meantime. The screen now shows the current state.";
    case "refused":
      return failure.explanation || "This is not allowed.";
    case "unavailable":
      // A paused live session: retrying cannot help until the session's owner starts it again.
      if (failure.detail === "agent_paused") {
        return "The assistant is paused: this session's model budget is used up. Your message is kept and will be answered when the session's owner starts it again.";
      }
      return "The assistant could not answer just now. Your message is kept; please try again.";
    case "server":
      return "Something went wrong on our side. Please try again.";
    case "offline":
      return "No answer from the server. Nothing is assumed: the screen shows what is stored once it answers again.";
  }
}

let csrfToken = "";
let sessionEnded: () => void = () => {};

/** Called once by the app: what to do when any request finds the session gone. */
export function onSessionEnded(handler: () => void): void {
  sessionEnded = handler;
}

const SIGN_IN = (method: string, path: string) => method === "POST" && path === "/api/session";

async function send(method: "GET" | "POST" | "DELETE", path: string, body?: unknown): Promise<[Response, unknown]> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken;
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError({ kind: "offline" });
  }
  return [response, await response.json().catch(() => null)];
}

/** The backend refused a change for its CSRF header, which says nothing about the change itself. */
function csrfRefused(response: Response, payload: unknown): boolean {
  const detail = typeof payload === "object" && payload !== null ? (payload as { detail?: unknown }).detail : null;
  return response.status === 403 && typeof detail === "string" && detail.includes("X-CSRF-Token");
}

async function call<T>(method: "GET" | "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  // A change needs the session's CSRF token. This page may have lost it (a reload of this module in development),
  // so it reads it again from the session, which only a page of this origin can, and tries the change once more.
  const change = method !== "GET" && !SIGN_IN(method, path);
  if (change && !csrfToken) await refreshToken();
  let [response, payload] = await send(method, path, body);
  if (change && csrfRefused(response, payload)) {
    await refreshToken();
    [response, payload] = await send(method, path, body);
  }
  if (!response.ok) {
    const failure = failureFrom(response.status, payload);
    if (failure.kind === "signed_out" && path !== "/api/session") sessionEnded();
    throw new ApiError(failure);
  }
  return payload as T;
}

async function refreshToken(): Promise<void> {
  const [response, payload] = await send("GET", "/api/session");
  if (response.ok) csrfToken = (payload as Session).csrf_token;
}

function remember(session: Session): Session {
  csrfToken = session.csrf_token;
  return session;
}

const at = encodeURIComponent;

type Decided = { proposal_id: string; status: ProposalStatus };

export const api = {
  mode: () => call<Mode>("GET", "/api/mode"),
  policy: () => call<PolicySections>("GET", "/api/policy"),
  session: () => call<Session>("GET", "/api/session").then(remember),
  signIn: (email: string, password: string) =>
    call<Session>("POST", "/api/session", { email, password }).then(remember),
  signOut: () => call<{ signed_out: boolean }>("DELETE", "/api/session"),

  // The customer's doors
  orders: () => call<Order[]>("GET", "/api/orders"),
  conversations: () => call<ConversationListItem[]>("GET", "/api/conversations"),
  openConversation: () => call<{ conversation_id: string }>("POST", "/api/conversations"),
  conversation: (id: string) => call<Conversation>("GET", `/api/conversations/${at(id)}`),
  say: (id: string, text: string) => call<{ answers: string[] }>("POST", `/api/conversations/${at(id)}/messages`, { text }),
  confirm: (proposalId: string, decision: "confirmed" | "declined") =>
    call<Decided>("POST", `/api/proposals/${at(proposalId)}/confirmation`, { decision }),
  cancel: (proposalId: string) => call<Decided>("POST", `/api/proposals/${at(proposalId)}/cancellation`),
  askForPerson: (conversationId: string) =>
    call<{ handoff_id: string }>("POST", `/api/conversations/${at(conversationId)}/handoff`),

  // The staff console's doors
  staffQueue: () => call<StaffQueue>("GET", "/api/staff/queue"),
  staffProposal: (id: string) => call<StaffProposal>("GET", `/api/staff/proposals/${at(id)}`),
  staffConversation: (id: string) => call<StaffConversation>("GET", `/api/staff/conversations/${at(id)}`),
  // A rejection carries the reason the customer is shown; an approval none (the backend refuses one).
  decide: (proposalId: string, decision: "approved" | "rejected", reason?: string) =>
    call<Decided>("POST", `/api/staff/proposals/${at(proposalId)}/decision`, reason ? { decision, reason } : { decision }),
  takeHandoff: (handoffId: string) =>
    call<{ handoff_id: string; status: string }>("POST", `/api/staff/handoffs/${at(handoffId)}/take`),
  takeOver: (conversationId: string) =>
    call<{ handoff_id: string }>("POST", `/api/staff/conversations/${at(conversationId)}/takeover`),
};
