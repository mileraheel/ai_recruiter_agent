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

  // One username/password authenticates both directions for every
  // mainstream provider (Gmail app passwords, Zoho, Outlook, ...) --
  // only host/port genuinely differ between sending (SMTP) and reading
  // (IMAP), so those are the only fields duplicated per direction.
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState("");
  const [username, setUsername] = useState("");
  const [accountEmail, setAccountEmail] = useState("");
  const [password, setPassword] = useState(""); // never pre-filled -- write-only
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
        smtp_host: smtpHost,
        smtp_port: Number(smtpPort),
        imap_host: imapHost,
        imap_port: Number(imapPort),
        username,
        account_email: accountEmail,
        password,
      });
      setPassword(""); // never keep it in memory longer than the request
      setShowSmtpForm(false);
      const status = await api.getEmailAccountStatus();
      setEmailAccount(status);
    } catch (e) {
      setError(e.detail || "Failed to save email account details");
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
        Connect the account RolePace will send applications/outreach from — and read replies to
        them from, once that part of the app is live. Gmail (recommended) or any provider's
        connection details. You can disconnect anytime; a Gmail connection also revokes access on
        Google's side.
      </p>

      {emailAccount?.connected ? (
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs rounded-full px-2.5 py-1 font-medium bg-accentSoft text-accent">
            Connected via {emailAccount.provider === "smtp" ? "SMTP/IMAP" : "Gmail"}: {emailAccount.account_email}
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
              {showSmtpForm ? "Cancel" : "Or enter connection details manually"}
            </button>
          </div>

          {showSmtpForm && (
            <form onSubmit={handleSmtpSubmit} className="space-y-3 pt-2 border-t border-ink/10">
              <div>
                <p className="text-xs font-semibold text-ink/70 mb-2">Outgoing (SMTP) — sending</p>
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-xs font-medium text-ink/60 mb-1">Host</label>
                    <input
                      type="text"
                      value={smtpHost}
                      onChange={(e) => setSmtpHost(e.target.value)}
                      placeholder="smtppro.example.com"
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
                      placeholder="465"
                      required
                      className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-ink/70 mb-2">Incoming (IMAP) — reading replies</p>
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-xs font-medium text-ink/60 mb-1">Host</label>
                    <input
                      type="text"
                      value={imapHost}
                      onChange={(e) => setImapHost(e.target.value)}
                      placeholder="imappro.example.com"
                      required
                      className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink/60 mb-1">Port</label>
                    <input
                      type="number"
                      value={imapPort}
                      onChange={(e) => setImapPort(e.target.value)}
                      placeholder="993"
                      required
                      className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-ink/70 mb-2">Account (used for both)</p>
                <div className="space-y-2.5">
                  <div>
                    <label className="block text-xs font-medium text-ink/60 mb-1">Sending/receiving email address</label>
                    <input
                      type="email"
                      value={accountEmail}
                      onChange={(e) => setAccountEmail(e.target.value)}
                      required
                      className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink/60 mb-1">Username</label>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink/60 mb-1">Password</label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
                      required
                      className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              </div>

              <p className="rounded-lg bg-accentSoft text-accent text-xs px-3 py-2 font-medium">
                🔒 This password is encrypted before it's stored. No one — including RolePace staff —
                can ever view or retrieve it again; it's used only to send and read on your behalf.
              </p>
              <p className="rounded-lg bg-ink/5 text-ink/60 text-xs px-3 py-2">
                Before saving, RolePace will send itself a test email using these details and confirm
                it arrives — this catches a wrong host/port/password immediately instead of only
                surfacing as a failure later. This can take up to about 30 seconds.
              </p>
              <button
                type="submit"
                disabled={savingSmtp}
                className="w-full btn btn-primary btn-small disabled:opacity-50"
              >
                {savingSmtp ? "Testing connection…" : "Test & save connection details"}
              </button>
            </form>
          )}
        </>
      )}
      {error && <div className="rounded-lg bg-dangerSoft text-danger text-xs px-3 py-2">{error}</div>}
    </div>
  );
}
