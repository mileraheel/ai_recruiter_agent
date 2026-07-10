import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.requestPasswordReset(email);
      // Same non-committal message regardless of whether the email
      // matched an account -- the backend already doesn't confirm/deny
      // that, so the UI shouldn't either.
      setMessage(res.message);
    } catch (err) {
      setError(err.detail || "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">Forgot password</h1>
          <p className="text-sm text-ink/60">
            Enter your account email and we'll send a link to reset your password.
          </p>
        </div>

        {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}
        {message && <div className="rounded-lg bg-accent/10 text-ink text-sm px-3 py-2">{message}</div>}

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

        <button
          type="submit"
          disabled={submitting}
          className="w-full btn btn-primary disabled:opacity-50"
        >
          {submitting ? "Sending…" : "Send reset link"}
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
