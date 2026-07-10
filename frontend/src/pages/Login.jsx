import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { APP_NAME } from "../config/appInfo";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { loginAdmin, error } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    const ok = await loginAdmin(username, password);
    setSubmitting(false);
    if (ok) navigate("/post-job");
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">{APP_NAME}</h1>
          <p className="text-sm text-ink/60">Sign in to manage your bench</p>
        </div>

        {error && (
          <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
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

        <p className="text-center text-xs text-ink/40">
          Candidate?{" "}
          <Link to="/candidate/login" className="underline">
            Go to the candidate portal
          </Link>
          {" · "}
          <Link to="/signup" className="underline">
            Register your corporate
          </Link>
          {" · "}
          <Link to="/accept-invite" className="underline">
            I have an invite
          </Link>
        </p>
        <p className="text-center text-xs text-ink/30">
          <Link to="/superuser/login" className="underline">
            Platform admin sign in
          </Link>
          {" · "}
          <Link to="/staff/login" className="underline">
            Staff sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
