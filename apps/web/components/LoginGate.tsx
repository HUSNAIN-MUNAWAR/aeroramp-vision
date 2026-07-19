"use client";

import { PropsWithChildren, useEffect, useState } from "react";
import { getToken, login } from "@/lib/api";

export function LoginGate({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("admin@aeroramp.local");
  const [password, setPassword] = useState("AeroRamp-Dev-2026!");
  const [error, setError] = useState("");
  useEffect(() => setReady(Boolean(getToken())), []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try { await login(email, password); setReady(true); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "Login failed"); }
  }
  if (ready) return children;
  return <div className="login-page"><div className="login-card"><div className="brand large"><span className="brand-mark">AR</span><div><strong>AeroRamp Vision</strong><small>Airport turnaround and ramp-safety intelligence</small></div></div><p className="muted">Operational decision support. Not an aviation-certified safety system.</p><form onSubmit={submit}><label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <div className="error-banner">{error}</div>}<button className="primary-button">Sign in</button></form><small className="muted">Development credentials are seeded locally. Change them before any shared deployment.</small></div></div>;
}
