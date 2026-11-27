import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Workspace } from "./Workspace";
import { Offline } from "./Offline";
import { LanguageProvider, LanguageSwitch, useErrorText, useLocalize, useTranslate } from "./language";
import "./style.css";
import "./workspace.css";
import "./product.css";

type Session = {
  access_token: string;
  user: { username: string; roles: string[]; is_staff: boolean; must_change_password: boolean };
};

function App() {
  const localize = useLocalize(), translate = useTranslate(), errorText = useErrorText();
  const [session, setSession] = useState<Session | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [passwordOpen, setPasswordOpen] = useState(false);
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
    return localize(
      <main>
        <Offline />
      </main>
    );
  if (!session)
    return localize(
      <main className="login">
        <LanguageSwitch />
        <p className="eyebrow">ORDER-TO-AUDIT</p>
        <h1>Sign in</h1>
        <p>Orders, production and accounts in one place.</p>
        {error && <p role="alert">{errorText(error)}</p>}
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
  if (session.user.must_change_password)
    return localize(<main className="login">
      <LanguageSwitch />
      <p className="eyebrow">ORDER-TO-AUDIT</p>
      <h1>Set your password</h1>
      <p>Replace the temporary password before opening your workspace.</p>
      {error && <p role="alert">{errorText(error)}</p>}
      <form onSubmit={async (event) => {
        event.preventDefault(); setBusy(true); setError("");
        const values = new FormData(event.currentTarget);
        if (values.get("new_password") !== values.get("confirm")) {
          setError("New passwords do not match."); setBusy(false); return;
        }
        try {
          setSession(await request("/change-password", session.access_token, {
            method: "POST", body: JSON.stringify({old_password: values.get("old_password"),
              new_password: values.get("new_password")})}));
        } catch (e) { setError((e as Error).message); }
        finally { setBusy(false); }
      }}>
        <label>Temporary password<input name="old_password" type="password" autoComplete="current-password" required /></label>
        <label>New password (at least 12 characters)<input name="new_password" type="password" minLength={12} autoComplete="new-password" required /></label>
        <label>Confirm new password<input name="confirm" type="password" minLength={12} autoComplete="new-password" required /></label>
        <button disabled={busy}>Set password</button>
      </form>
      <button className="link" onClick={() => setSession(null)}>Sign out</button>
    </main>);
  return localize(
    <div className="workspace">
      <aside className="sidebar">
        <strong>Order-to-Audit</strong>
        <p>Factory operations</p>
        <div id="workspace-navigation" />
        <div className="sidebar-preferences"><LanguageSwitch /></div>
        <section className="profile-menu">
          <div className="profile-identity"><span className="avatar" aria-hidden="true">{session.user.username.slice(0, 2).toUpperCase()}</span><span>{session.user.username}<small>{session.user.roles.map(translate).join(", ")}</small></span></div>
          <button onClick={() => {setPasswordOpen(true); setError("");}}>Change password</button>
          <button onClick={() => setSession(null)}>Sign out</button>
        </section>
      </aside>
      <section className="body">
        <main>
          {passwordOpen && <section className="card">
            <div className="section-heading"><h2>Change password</h2><button className="secondary" onClick={() => setPasswordOpen(false)}>Close</button></div>
            {error && <p role="alert">{errorText(error)}</p>}
            <form onSubmit={async (event) => {
              event.preventDefault(); setBusy(true); setError("");
              const values = new FormData(event.currentTarget);
              if (values.get("new_password") !== values.get("confirm")) {
                setError("New passwords do not match."); setBusy(false); return;
              }
              try {
                setSession(await request("/change-password", session.access_token, {
                  method:"POST",body:JSON.stringify({old_password:values.get("old_password"),
                    new_password:values.get("new_password")})}));
                setPasswordOpen(false);
              } catch (e) { setError((e as Error).message); }
              finally { setBusy(false); }
            }}>
              <label>Current password<input name="old_password" type="password" autoComplete="current-password" required /></label>
              <label>New password (at least 12 characters)<input name="new_password" type="password" minLength={12} autoComplete="new-password" required /></label>
              <label>Confirm new password<input name="confirm" type="password" minLength={12} autoComplete="new-password" required /></label>
              <button disabled={busy}>Save password</button>
            </form>
          </section>}
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

createRoot(document.getElementById("root")!).render(<LanguageProvider><App /></LanguageProvider>);
