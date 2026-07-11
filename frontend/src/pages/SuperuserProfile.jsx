import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import EmailAccountCard from "../components/EmailAccountCard";

export default function SuperuserProfile() {
  const { logout } = useAuth();
  const [me, setMe] = useState(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState(null);
  const [passwordError, setPasswordError] = useState(null);
  const [changingPassword, setChangingPassword] = useState(false);

  useEffect(() => {
    api
      .getSuperuserMe()
      .then((data) => {
        setMe(data);
        setFullName(data.full_name || "");
        setEmail(data.email || "");
      })
      .catch((e) => setError(e.detail || "Failed to load profile"));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updateSuperuserProfile({ full_name: fullName || null, email: email || null });
      setMe(updated);
      setSaved(true);
    } catch (e) {
      setError(e.detail || "Failed to update profile");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setChangingPassword(true);
    setPasswordError(null);
    setPasswordMessage(null);
    try {
      await api.changeSuperuserPassword({ current_password: currentPassword, new_password: newPassword });
      setPasswordMessage("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
    } catch (e) {
      setPasswordError(e.detail || "Failed to change password");
    } finally {
      setChangingPassword(false);
    }
  }

  if (!me) return <div className="max-w-2xl mx-auto p-6 text-sm text-ink/50">Loading…</div>;

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8 pb-20 space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Your profile</h1>
          <p className="text-sm text-ink/60 mt-0.5">Changes here apply immediately.</p>
        </div>
        <button onClick={logout} className="text-xs font-medium text-ink/50 shrink-0">
          Log out
        </button>
      </div>

      <Link to="/superuser/dashboard" className="text-xs font-medium underline text-ink/50">
        ← Back to dashboard
      </Link>

      <EmailAccountCard />

      <form onSubmit={handleSubmit} className="rounded-xl border border-ink/10 p-4 space-y-3">
        <h2 className="text-sm font-semibold">Identity</h2>
        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">Username</label>
          <input
            type="text"
            value={me.username}
            disabled
            className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm bg-ink/5 text-ink/50"
          />
          <p className="text-xs text-ink/40 mt-1">Your account identifier — cannot be changed.</p>
        </div>
        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">Full name</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
          />
          <p className="text-xs text-ink/40 mt-1">Used for password-reset codes and account notifications.</p>
        </div>

        {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}
        {saved && <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">Saved.</div>}

        <button type="submit" disabled={submitting} className="w-full btn btn-primary disabled:opacity-50">
          {submitting ? "Saving…" : "Save changes"}
        </button>
      </form>

      <form onSubmit={handleChangePassword} className="rounded-xl border border-ink/10 p-4 space-y-3">
        <h2 className="text-sm font-semibold">Change password</h2>
        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">Current password</label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">New password</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={10}
            className="w-full rounded-lg border border-ink/15 px-3 py-2.5 text-sm"
          />
        </div>

        <p className="rounded-lg bg-accentSoft text-accent text-xs px-3 py-2 font-medium">
          🔒 Your password is one-way encrypted — no one, including RolePace staff, can ever view or
          retrieve it, only verify it when you sign in.
        </p>

        {passwordError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{passwordError}</div>}
        {passwordMessage && <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{passwordMessage}</div>}

        <button type="submit" disabled={changingPassword} className="w-full btn btn-primary disabled:opacity-50">
          {changingPassword ? "Updating…" : "Update password"}
        </button>
      </form>
    </div>
  );
}
