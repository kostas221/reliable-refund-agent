// Who is signed in decides the screen. The backend says so: the page asks for the session when it loads (the cookie
// survives a refresh and a server restart), and goes back to signing in whenever any request finds the session gone.

import { useEffect, useState } from "react";

import { ApiError, api, onSessionEnded } from "./api";
import { CustomerScreen } from "./CustomerScreen";
import { modeBanner } from "./mode";
import { SignIn } from "./SignIn";
import { StaffScreen } from "./StaffScreen";
import type { Mode, Session } from "./types";

const RETRY_MS = 3000;
const MODE_EVERY_MS = 10000; // the spending and a pause change while people use the screens

/** Who answers in the chat and what a payment is, on every screen (backend: GET /api/mode). */
function ModeBanner() {
  const [mode, setMode] = useState<Mode | null>(null);
  useEffect(() => {
    let stopped = false;
    const read = () =>
      api
        .mode()
        .then((found) => !stopped && setMode(found))
        .catch(() => undefined); // the last answer stays shown; the page says when the server is down
    void read();
    const timer = window.setInterval(read, MODE_EVERY_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);
  if (mode === null) return null;
  const banner = modeBanner(mode);
  return (
    <div className={`notice ${banner.tone} mode`} role="status" aria-label="Mode">
      {banner.lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}

export function App() {
  // undefined: still asking the backend; null: nobody is signed in.
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [problem, setProblem] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [signOutProblem, setSignOutProblem] = useState("");

  // Signing out also forgets what the page had open, so the next person starts from their own screen.
  function forget() {
    window.history.replaceState(null, "", window.location.pathname);
    setSession(null);
  }

  useEffect(() => onSessionEnded(forget), []);

  // A server that is down or still starting is a temporary state: the page asks again until it answers.
  useEffect(() => {
    let retry: number | undefined;
    api
      .session()
      .then((found) => {
        setProblem("");
        setSession(found);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.failure.kind === "signed_out") {
          setProblem("");
          setSession(null);
        } else {
          setProblem(`${error instanceof Error ? error.message : String(error)} Trying again…`);
          retry = window.setTimeout(() => setAttempt((n) => n + 1), RETRY_MS);
        }
      });
    return () => window.clearTimeout(retry);
  }, [attempt]);

  // The page says "signed out" only once the backend has ended the session (or it had already ended).
  async function signOut() {
    setSignOutProblem("");
    try {
      await api.signOut();
    } catch (error) {
      if (!(error instanceof ApiError && error.failure.kind === "signed_out")) {
        setSignOutProblem(`Could not sign out: ${error instanceof Error ? error.message : String(error)}`);
        return;
      }
    }
    forget();
  }

  if (problem) return <p role="alert" className="page notice error">{problem}</p>;
  if (session === undefined) return <p role="status" className="page">Loading…</p>;
  if (session === null)
    return (
      <>
        <div className="page narrow">
          <ModeBanner />
        </div>
        <SignIn onSignedIn={setSession} />
      </>
    );
  return (
    <div className="page">
      <ModeBanner />
      <header className="top">
        <strong>{session.role === "staff" ? "Refunds: staff console" : "Refunds"}</strong>
        <span className="who">
          Signed in as {session.display_name}
          <button type="button" className="quiet" onClick={signOut}>
            Sign out
          </button>
        </span>
      </header>
      {signOutProblem && (
        <p role="alert" className="notice error">
          {signOutProblem}
        </p>
      )}
      <main>{session.role === "staff" ? <StaffScreen /> : <CustomerScreen />}</main>
    </div>
  );
}
