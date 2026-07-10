import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import EmailAccountCard from "../components/EmailAccountCard";

export default function AdminSignup() {
  const [organizationName, setOrganizationName] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [step, setStep] = useState("credentials"); // "credentials" | "connect-email"
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.adminSignup({
        organization_name: organizationName,
        username,
        full_name: fullName || undefined,
        password,
      });
      loginWithToken(res.access_token, "admin");
      setStep("connect-email");
    } catch (e) {
      setError(e.detail || "Sign up failed");
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
          <button onClick={() => navigate("/post-job")} className="w-full btn btn-primary">
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
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              autoComplete="username"
              required
            />
            <p className="text-xs text-ink/40 mt-1">Your account identifier — cannot be changed later.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Full name (optional)</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              autoComplete="name"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Password (min 10 characters)</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
              autoComplete="new-password"
              minLength={10}
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full btn btn-primary disabled:opacity-50"
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
