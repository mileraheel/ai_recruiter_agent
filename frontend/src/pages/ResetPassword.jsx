import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, decodeJwtRole } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ROLE_LANDING, LOGIN_PATH } from "../config/roleRouting";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  // Pre-filled from the link in the reset email, but editable in case a
  // param got mis-copied or the user opens this page directly.
  const [email, setEmail] = useState(searchParams.get("email") || "");
  const [otp, setOtp] = useState(searchParams.get("otp") || "");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const { loginWithToken } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.confirmPasswordReset({ email, otp, new_password: newPassword });
      const role = decodeJwtRole(res.access_token);
      loginWithToken(res.access_token, role);
      navigate(ROLE_LANDING[role] || LOGIN_PATH);
    } catch (err) {
      setError(err.detail || "Couldn't reset your password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">Set a new password</h1>
          <p className="text-sm text-ink/60">
            Enter the code from your reset email along with your new password.
          </p>
        </div>

        {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              autoComplete="email"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Reset code</label>
            <input
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              inputMode="numeric"
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">New password (min 10 characters)</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={10}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full btn btn-primary disabled:opacity-50"
        >
          {submitting ? "Resetting…" : "Reset password"}
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
