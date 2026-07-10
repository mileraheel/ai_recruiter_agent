import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, decodeJwtRole } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ROLE_LANDING, LOGIN_PATH } from "../config/roleRouting";
import EmailAccountCard from "../components/EmailAccountCard";

// Staff don't send outreach emails, so there's no reason to interrupt
// their onboarding with a "connect email" step -- admin and candidate
// only, matching who EmailAccountCard's backend actually supports.
const CONNECT_EMAIL_ROLES = new Set(["admin", "candidate"]);

export default function AcceptInvite() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [step, setStep] = useState("credentials"); // "credentials" | "connect-email"
  const [landingPath, setLandingPath] = useState(LOGIN_PATH);
  const { loginWithToken } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.redeemInvite({
        email,
        otp,
        password,
        username: username || undefined,
        full_name: fullName || undefined,
      });
      const role = decodeJwtRole(res.access_token);
      loginWithToken(res.access_token, role);
      const landing = ROLE_LANDING[role] || LOGIN_PATH;
      if (CONNECT_EMAIL_ROLES.has(role)) {
        setLandingPath(landing);
        setStep("connect-email");
      } else {
        navigate(landing);
      }
    } catch (err) {
      setError(err.detail || "Couldn't redeem this invite");
    } finally {
      setSubmitting(false);
    }
  }

  if (step === "connect-email") {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-5">
          <div className="space-y-1 text-center">
            <h1 className="text-xl font-semibold tracking-tight">Almost done</h1>
            <p className="text-sm text-ink/60">
              Connect the email account RolePace will send applications and outreach from — or
              skip for now and do this anytime from your profile.
            </p>
          </div>
          <EmailAccountCard />
          <button onClick={() => navigate(landingPath)} className="w-full btn btn-primary">
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">I have an invite</h1>
          <p className="text-sm text-ink/60">
            Enter the email address your invite was sent to, along with the code from that email,
            to set your password and get started.
          </p>
        </div>

        {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

        <div className="space-y-3">
          <div>
            <label htmlFor="invite-email" className="block text-xs font-medium text-ink/60 mb-1">
              Email
            </label>
            <input
              id="invite-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              required
            />
          </div>
          <div>
            <label htmlFor="invite-otp" className="block text-xs font-medium text-ink/60 mb-1">
              Invite code
            </label>
            <input
              id="invite-otp"
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              inputMode="numeric"
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              required
            />
          </div>
          <div>
            <label htmlFor="invite-password" className="block text-xs font-medium text-ink/60 mb-1">
              Choose a password (min 10 characters)
            </label>
            <input
              id="invite-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={10}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              required
            />
          </div>

          <div className="pt-2 border-t border-ink/10 space-y-3">
            <p className="text-xs text-ink/50">
              Fill in whichever applies to your invite — your invite email will say which kind of
              account this is.
            </p>
            <div>
              <label htmlFor="invite-username" className="block text-xs font-medium text-ink/60 mb-1">
                Username <span className="text-ink/40">(staff or organization admin invites)</span>
              </label>
              <input
                id="invite-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              />
            </div>
            <div>
              <label htmlFor="invite-fullname" className="block text-xs font-medium text-ink/60 mb-1">
                Full name <span className="text-ink/40">(candidate invites, or admin invites for an individual account)</span>
              </label>
              <input
                id="invite-fullname"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full btn btn-primary disabled:opacity-50"
        >
          {submitting ? "Verifying…" : "Set password & continue"}
        </button>

        <p className="text-center text-xs text-ink/40">
          <Link to="/login" className="underline">
            Back to sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
