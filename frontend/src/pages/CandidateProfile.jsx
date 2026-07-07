import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import NotificationPrompt from "../components/NotificationPrompt";
import TrialBanner from "../components/TrialBanner";

const STATUS_STYLES = {
  no_account: "bg-black/5 text-ink/60",
  pending: "bg-warnSoft text-warn",
  approved: "bg-accentSoft text-accent",
  rejected: "bg-dangerSoft text-danger",
};

const STATUS_LABELS = {
  no_account: "No profile submitted yet",
  pending: "Pending admin review",
  approved: "Approved — active",
  rejected: "Rejected — please revise and resubmit",
};

const EMPTY_PROFILE = {
  full_name: "",
  email: "",
  phone: "",
  location: "",
  linkedin_url: "",
  work_authorization: "",
  requires_sponsorship_or_transfer: false,
  career_start_date: "",
  tech_stack_summary: "",
  closing_statement: "",
  experience_highlights: [],
  passport_number: "",
  c2c_rate: "",
  employer: null,
  open_to_relocation: false,
  c2c_allowed: false,
  w2_allowed: false,
  contract_allowed: false,
  contract_to_hire_allowed: false,
  full_time_allowed: false,
  has_security_clearance: false,
  public_trust_available: false,
  willing_to_work_remote: false,
  willing_to_work_hybrid: false,
  willing_to_work_onsite: false,
};

function TextField({ label, value, onChange, type = "text", required = false, placeholder }) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink/60 mb-1">{label}</label>
      <input
        type={type}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
        className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
      />
    </div>
  );
}

function CheckField({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} className="rounded" />
      {label}
    </label>
  );
}

export default function CandidateProfile() {
  const { logout } = useAuth();
  const [me, setMe] = useState(null);
  const [form, setForm] = useState(EMPTY_PROFILE);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeStatus, setResumeStatus] = useState(null);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [emailAccount, setEmailAccount] = useState(null);
  const [connecting, setConnecting] = useState(false);

  async function load() {
    try {
      const data = await api.getMe();
      setMe(data);
      if (data.approved_profile) {
        setForm({ ...EMPTY_PROFILE, ...data.approved_profile });
      } else {
        setForm((f) => ({ ...f, full_name: data.full_name, email: data.login_email || "" }));
      }
    } catch (e) {
      setError(e.detail || "Failed to load profile");
    }
  }

  useEffect(() => {
    load();
    api.getEmailAccountStatus().then(setEmailAccount).catch(() => {});
  }, []);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
    setSaved(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = { ...form };
      if (!payload.career_start_date) payload.career_start_date = null;
      if (!payload.linkedin_url) payload.linkedin_url = null;
      await api.submitMyProfile(payload);
      setSaved(true);
      await load();
    } catch (e) {
      setError(e.detail || "Failed to submit profile");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResumeUpload() {
    if (!resumeFile) return;
    setUploadingResume(true);
    setResumeStatus(null);
    try {
      const res = await api.uploadMyResume(resumeFile);
      setResumeStatus(res.message + (res.new_skills_suggested ? ` (${res.new_skills_suggested} new skills detected)` : ""));
    } catch (e) {
      setResumeStatus(e.detail || "Upload failed");
    } finally {
      setUploadingResume(false);
    }
  }

  async function handleConnectGmail() {
    setConnecting(true);
    try {
      const { consent_url } = await api.getEmailConnectUrl();
      window.location.href = consent_url;
    } catch (e) {
      setError(e.detail || "Failed to start Gmail connection");
      setConnecting(false);
    }
  }

  async function handleDisconnectGmail() {
    try {
      await api.disconnectEmailAccount();
      setEmailAccount({ connected: false });
    } catch (e) {
      setError(e.detail || "Failed to disconnect");
    }
  }

  if (!me) return <div className="max-w-2xl mx-auto p-6 text-sm text-ink/50">Loading…</div>;

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8 pb-20 space-y-6">
      <TrialBanner />
      <NotificationPrompt />
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Your profile</h1>
          <p className="text-sm text-ink/60 mt-0.5">
            Nothing here is used for job matching until an admin reviews and approves it.
          </p>
        </div>
        <button onClick={logout} className="text-xs font-medium text-ink/50 shrink-0">
          Log out
        </button>
      </div>

      <Link to="/candidate/applications" className="text-xs font-medium underline text-ink/60">
        View your applications & interviews →
      </Link>

      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[me.profile_status] || ""}`}>
        {STATUS_LABELS[me.profile_status] || me.profile_status}
      </span>

      {/* Resume upload */}
      <div className="rounded-xl border border-black/10 p-4 space-y-3">
        <h2 className="text-sm font-semibold">Resume</h2>
        <p className="text-xs text-ink/50">
          Upload a .docx resume. Skills detected in it are queued for admin approval before they're
          used for job matching or tailoring — same review process either way.
        </p>
        <input
          type="file"
          accept=".docx"
          onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
          className="text-sm"
        />
        <button
          onClick={handleResumeUpload}
          disabled={!resumeFile || uploadingResume}
          className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {uploadingResume ? "Uploading…" : "Upload resume"}
        </button>
        {resumeStatus && <p className="text-xs text-ink/60">{resumeStatus}</p>}
      </div>

      {/* Gmail connection */}
      <div className="rounded-xl border border-black/10 p-4 space-y-3">
        <h2 className="text-sm font-semibold">Email account</h2>
        <p className="text-xs text-ink/50">
          Connecting Gmail lets the app read recruiter emails about your applications, draft/send
          replies and follow-ups, and manage interview calendar events — always with your review
          before anything goes out, once that part of the app is live. You can disconnect anytime,
          which also revokes access on Google's side.
        </p>
        {emailAccount?.connected ? (
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs rounded-full px-2.5 py-1 font-medium bg-accentSoft text-accent">
              Connected: {emailAccount.account_email}
            </span>
            <button
              onClick={handleDisconnectGmail}
              className="text-xs font-medium text-danger underline"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <button
            onClick={handleConnectGmail}
            disabled={connecting}
            className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {connecting ? "Redirecting…" : "Connect Gmail"}
          </button>
        )}
      </div>

      {/* Profile form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="rounded-xl border border-black/10 p-4 space-y-3">
          <h2 className="text-sm font-semibold">Personal</h2>
          <TextField label="Full legal name" value={form.full_name} onChange={(v) => set("full_name", v)} required />
          <TextField label="Email" type="email" value={form.email} onChange={(v) => set("email", v)} required />
          <TextField label="Phone" value={form.phone} onChange={(v) => set("phone", v)} required />
          <TextField label="Current location" value={form.location} onChange={(v) => set("location", v)} required />
          <TextField label="LinkedIn URL" value={form.linkedin_url} onChange={(v) => set("linkedin_url", v)} />
          <CheckField label="Open to relocation" checked={form.open_to_relocation} onChange={(v) => set("open_to_relocation", v)} />
        </div>

        <div className="rounded-xl border border-black/10 p-4 space-y-3">
          <h2 className="text-sm font-semibold">Work authorization & engagement</h2>
          <TextField label="Work authorization (e.g. H1B, GC, USC)" value={form.work_authorization} onChange={(v) => set("work_authorization", v)} required />
          <CheckField label="Requires sponsorship/transfer" checked={form.requires_sponsorship_or_transfer} onChange={(v) => set("requires_sponsorship_or_transfer", v)} />
          <TextField label="Career start date" type="date" value={form.career_start_date} onChange={(v) => set("career_start_date", v)} />
          <TextField label="C2C rate (e.g. $85/hr)" value={form.c2c_rate} onChange={(v) => set("c2c_rate", v)} />
          <div className="grid grid-cols-2 gap-2 pt-1">
            <CheckField label="C2C" checked={form.c2c_allowed} onChange={(v) => set("c2c_allowed", v)} />
            <CheckField label="W2" checked={form.w2_allowed} onChange={(v) => set("w2_allowed", v)} />
            <CheckField label="Contract" checked={form.contract_allowed} onChange={(v) => set("contract_allowed", v)} />
            <CheckField label="Contract-to-hire" checked={form.contract_to_hire_allowed} onChange={(v) => set("contract_to_hire_allowed", v)} />
            <CheckField label="Full-time" checked={form.full_time_allowed} onChange={(v) => set("full_time_allowed", v)} />
          </div>
        </div>

        <div className="rounded-xl border border-black/10 p-4 space-y-3">
          <h2 className="text-sm font-semibold">Availability & clearance</h2>
          <div className="grid grid-cols-2 gap-2">
            <CheckField label="Remote" checked={form.willing_to_work_remote} onChange={(v) => set("willing_to_work_remote", v)} />
            <CheckField label="Hybrid" checked={form.willing_to_work_hybrid} onChange={(v) => set("willing_to_work_hybrid", v)} />
            <CheckField label="Onsite" checked={form.willing_to_work_onsite} onChange={(v) => set("willing_to_work_onsite", v)} />
          </div>
          <CheckField label="Has active security clearance" checked={form.has_security_clearance} onChange={(v) => set("has_security_clearance", v)} />
          <CheckField label="Public trust available" checked={form.public_trust_available} onChange={(v) => set("public_trust_available", v)} />
        </div>

        <div className="rounded-xl border border-black/10 p-4 space-y-3">
          <h2 className="text-sm font-semibold">Narrative (used in outreach emails & resume summary)</h2>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Tech stack summary</label>
            <textarea
              value={form.tech_stack_summary || ""}
              onChange={(e) => set("tech_stack_summary", e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Closing statement</label>
            <textarea
              value={form.closing_statement || ""}
              onChange={(e) => set("closing_statement", e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
            />
          </div>
        </div>

        {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}
        {saved && <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">Submitted for admin review.</div>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-ink text-paper py-2.5 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Submit for approval"}
        </button>
      </form>
    </div>
  );
}
