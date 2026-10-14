import { type FormEvent, useState } from "react";

import { ApiError, api } from "./api";
import type { Session } from "./types";

export function SignIn({ onSignedIn }: { onSignedIn: (session: Session) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem("");
    try {
      onSignedIn(await api.signIn(email, password));
    } catch (error) {
      // The backend gives the same answer for an unknown email and a wrong password, and so does this screen.
      const signedOut = error instanceof ApiError && error.failure.kind === "signed_out";
      setProblem(signedOut ? "Wrong email or password." : String(error instanceof Error ? error.message : error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page narrow">
      <h1>Sign in</h1>
      <form onSubmit={submit} className="stack">
        <label>
          Email
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {problem && (
          <p role="alert" className="notice error">
            {problem}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
