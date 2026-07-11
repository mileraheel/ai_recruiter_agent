import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { APP_NAME } from "../config/appInfo";
import { useAuth } from "../context/AuthContext";
import { ROLE_LANDING, LOGIN_PATH } from "../config/roleRouting";

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, error } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    const role = await login(identifier, password);
    setSubmitting(false);
    if (role) navigate(ROLE_LANDING[role] || LOGIN_PATH);
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">{APP_NAME}</h1>
          <p className="text-sm text-ink/60">Sign in to continue</p>
        </div>

        {error && (
          <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Username or email</label>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              autoComplete="current-password"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full btn btn-primary disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-center text-xs text-ink/40 space-x-2">
          <Link to="/accept-invite" className="underline">
            I have an invite
          </Link>
          <span>·</span>
          <Link to="/forgot-password" className="underline">
            Forgot password?
          </Link>
        </p>
      </form>
    </div>
  );
}
