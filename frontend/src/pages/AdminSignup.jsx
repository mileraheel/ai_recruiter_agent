import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function AdminSignup() {
  const [organizationName, setOrganizationName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.adminSignup({ organization_name: organizationName, username, password });
      loginWithToken(res.access_token, "admin");
      navigate("/post-job");
    } catch (e) {
      setError(e.detail || "Sign up failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">Register your corporate</h1>
          <p className="text-sm text-ink/60">
            This creates a brand new organization — it can't join an existing one. If your company
            is already registered, ask an existing admin there to add you instead.
          </p>
        </div>

        {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Corporate / organization name</label>
            <input
              type="text"
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Password (min 10 characters)</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
              autoComplete="new-password"
              minLength={10}
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-ink text-paper py-2.5 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create organization"}
        </button>

        <p className="text-center text-xs text-ink/40">
          Already registered?{" "}
          <Link to="/login" className="underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
