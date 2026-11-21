import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Workspace } from "./Workspace";
import { Offline } from "./Offline";
import "./style.css";
import "./workspace.css";

type Session = {
  access_token: string;
  user: { username: string; roles: string[]; is_staff: boolean };
};

function App() {
  const [session, setSession] = useState<Session | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if ("serviceWorker" in navigator)
      navigator.serviceWorker
        .register("/service-worker.js")
        .then(() => navigator.serviceWorker.ready)
        .then((registration) =>
          registration.active?.postMessage({
            assets: [
              ...document.querySelectorAll(
                'script[src],link[rel="stylesheet"]',
              ),
            ].map(
              (el) =>
                new URL(
                  el.getAttribute("src") || el.getAttribute("href")!,
                  location.origin,
                ).pathname,
            ),
          }),
        )
        .catch(() => {});
  }, []);
  async function request(
    path: string,
    token: string,
    options: RequestInit = {},
  ) {
    const response = await fetch("/api" + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!response.ok) {
      if (response.status === 401 && token) setSession(null);
      const data = await response.json();
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Check the supplied values.",
      );
    }
    return response.json();
  }
  if (location.pathname === "/offline")
    return (
      <main>
        <Offline />
      </main>
    );
  if (!session)
    return (
      <main className="login">
        <p className="eyebrow">ORDER-TO-AUDIT</p>
        <h1>Sign in</h1>
        <p>Your factory workspace</p>
        {error && <p role="alert">{error}</p>}
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy) return;
            setBusy(true);
            setError("");
            const data = new FormData(event.currentTarget);
            try {
              setSession(
                await request("/login", "", {
                  method: "POST",
                  body: JSON.stringify({
                    username: data.get("username"),
                    password: data.get("password"),
                  }),
                }),
              );
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Username
            <input name="username" autoComplete="username" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </main>
    );
  return (
    <div className="workspace">
      <aside>
        <strong>Order-to-Audit</strong>
        <p>Factory workspace</p>
        <small>
          React · FastAPI
          <br />
          PostgreSQL ledger
        </small>
      </aside>
      <section className="body">
        <header>
          <span>
            {session.user.username} · {session.user.roles.join(", ")}
          </span>
          <button onClick={() => setSession(null)}>Sign out</button>
        </header>
        <main>
          <Workspace
            token={session.access_token}
            user={session.user}
            request={request}
          />
        </main>
      </section>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
