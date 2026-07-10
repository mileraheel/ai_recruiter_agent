import { useEffect, useState } from "react";
import { api } from "../api/client";

// Self-contained: loads its own status and works identically for whoever's
// logged in (any role) -- the backend resolves the right owner from the
// bearer token, so this component never needs to know or care which role
// is using it. Shared by every profile page and the post-registration
// "connect your email" step.
export default function EmailAccountCard() {
  const [emailAccount, setEmailAccount] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState(null);
  const [showSmtpForm, setShowSmtpForm] = useState(false);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("");
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpEmail, setSmtpEmail] = useState("");
  const [smtpPassword, setSmtpPassword] = useState(""); // never pre-filled -- write-only
  const [savingSmtp, setSavingSmtp] = useState(false);

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

  async function handleSmtpSubmit(e) {
    e.preventDefault();
    setSavingSmtp(true);
    setError(null);
    try {
      await api.connectSmtp({
        host: smtpHost,
        port: Number(smtpPort),
        username: smtpUsername,
        account_email: smtpEmail,
        password: smtpPassword,
      });
      setSmtpPassword(""); // never keep it in memory longer than the request
      setShowSmtpForm(false);
      const status = await api.getEmailAccountStatus();
      setEmailAccount(status);
    } catch (e) {
      setError(e.detail || "Failed to save SMTP details");
    } finally {
      setSavingSmtp(false);
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
        Connect the account RolePace will send applications and outreach from — Gmail (recommended)
        or any provider's SMTP details. You can disconnect anytime; a Gmail connection also revokes
        access on Google's side.
      </p>

      {emailAccount?.connected ? (
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs rounded-full px-2.5 py-1 font-medium bg-accentSoft text-accent">
            Connected via {emailAccount.provider === "smtp" ? "SMTP" : "Gmail"}: {emailAccount.account_email}
          </span>
          <button onClick={handleDisconnect} className="text-xs font-medium text-danger underline">
            Disconnect
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="btn btn-primary btn-small disabled:opacity-50"
            >
              {connecting ? "Redirecting…" : "Connect Gmail"}
            </button>
            <button
              type="button"
              onClick={() => setShowSmtpForm((s) => !s)}
              className="text-xs font-medium text-ink/50 underline"
            >
              {showSmtpForm ? "Cancel" : "Or enter SMTP details manually"}
            </button>
          </div>

          {showSmtpForm && (
            <form onSubmit={handleSmtpSubmit} className="space-y-2.5 pt-2 border-t border-ink/10">
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-xs font-medium text-ink/60 mb-1">SMTP host</label>
                  <input
                    type="text"
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    placeholder="smtp.example.com"
                    required
                    className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink/60 mb-1">Port</label>
                  <input
                    type="number"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(e.target.value)}
                    placeholder="587"
                    required
                    className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-ink/60 mb-1">Sending email address</label>
                <input
                  type="email"
                  value={smtpEmail}
                  onChange={(e) => setSmtpEmail(e.target.value)}
                  required
                  className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink/60 mb-1">SMTP username</label>
                <input
                  type="text"
                  value={smtpUsername}
                  onChange={(e) => setSmtpUsername(e.target.value)}
                  required
                  className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink/60 mb-1">SMTP password</label>
                <input
                  type="password"
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                />
              </div>
              <p className="rounded-lg bg-accentSoft text-accent text-xs px-3 py-2 font-medium">
                🔒 This password is encrypted before it's stored. No one — including RolePace staff —
                can ever view or retrieve it again; it's used only to send on your behalf.
              </p>
              <button
                type="submit"
                disabled={savingSmtp}
                className="w-full btn btn-primary btn-small disabled:opacity-50"
              >
                {savingSmtp ? "Saving…" : "Save SMTP details"}
              </button>
            </form>
          )}
        </>
      )}
      {error && <div className="rounded-lg bg-dangerSoft text-danger text-xs px-3 py-2">{error}</div>}
    </div>
  );
}
