import { useEffect, useState } from "react";
import { api } from "../api/client";

// Self-contained: loads its own status and works identically for whoever's
// logged in (admin or candidate) -- the backend resolves the right owner
// from the bearer token, so this component never needs to know or care
// which role is using it. Shared by CandidateProfile.jsx, AdminProfile.jsx,
// and the post-registration "connect your email" step.
export default function EmailAccountCard() {
  const [emailAccount, setEmailAccount] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getEmailAccountStatus().then(setEmailAccount).catch(() => {});
  }, []);

  async function handleConnect() {
    setConnecting(true);
    setError(null);
    try {
      const { consent_url } = await api.getEmailConnectUrl();
      window.location.href = consent_url;
    } catch (e) {
      setError(e.detail || "Failed to start email connection");
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    try {
      await api.disconnectEmailAccount();
      setEmailAccount({ connected: false });
    } catch (e) {
      setError(e.detail || "Failed to disconnect");
    }
  }

  return (
    <div className="rounded-xl border border-ink/10 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Email account</h2>
        {!emailAccount?.connected && (
          <span className="text-xs rounded-full px-2.5 py-1 font-medium bg-warnSoft text-warn">Needed</span>
        )}
      </div>
      <p className="text-xs text-ink/50">
        Connecting Gmail lets the app send applications/outreach from your own inbox, read
        recruiter replies about them, and manage interview calendar events — always with your
        review before anything goes out, once that part of the app is live. You can disconnect
        anytime, which also revokes access on Google's side.
      </p>
      {emailAccount?.connected ? (
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs rounded-full px-2.5 py-1 font-medium bg-accentSoft text-accent">
            Connected: {emailAccount.account_email}
          </span>
          <button onClick={handleDisconnect} className="text-xs font-medium text-danger underline">
            Disconnect
          </button>
        </div>
      ) : (
        <button
          onClick={handleConnect}
          disabled={connecting}
          className="btn btn-primary btn-small disabled:opacity-50"
        >
          {connecting ? "Redirecting…" : "Connect Gmail"}
        </button>
      )}
      {error && <div className="rounded-lg bg-dangerSoft text-danger text-xs px-3 py-2">{error}</div>}
    </div>
  );
}
