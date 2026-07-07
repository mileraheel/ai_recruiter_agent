import { useEffect, useState } from "react";
import { api } from "../api/client";
import DataTable from "../components/DataTable";

const STATUS_NOTICES = {
  pending_approval: "Profile submitted, awaiting admin approval.",
  needs_search_config: "Approved — needs a search config block in candidate.yaml.",
  not_found: "No profile on record.",
};

const CANDIDATE_COLUMNS = [
  {
    key: "full_name",
    label: "Candidate",
    sortValue: (r) => r.full_name?.toLowerCase() || "",
    filterValue: (r) => `${r.full_name} ${r.slug}`,
    render: (r) => (
      <div>
        <p className="font-medium">{r.full_name}</p>
        <p className="text-xs text-ink/50 mt-0.5">{r.slug}</p>
      </div>
    ),
  },
  {
    key: "resume_exists",
    label: "Resume",
    sortValue: (r) => (r.resume_exists ? 1 : 0),
    filterValue: (r) => (r.resume_exists ? "found" : "missing"),
    render: (r) => (
      <span
        className={`text-xs rounded-full px-2 py-0.5 font-medium ${
          r.resume_exists ? "bg-accentSoft text-accent" : "bg-dangerSoft text-danger"
        }`}
      >
        {r.resume_exists ? "Resume found" : "Resume missing"}
      </span>
    ),
  },
  {
    key: "pending_skill_count",
    label: "Pending skills",
    sortValue: (r) => r.pending_skill_count,
    filterValue: (r) => r.pending_skill_count,
    render: (r) =>
      r.pending_skill_count > 0 ? (
        <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-warnSoft text-warn">
          {r.pending_skill_count} pending
        </span>
      ) : (
        <span className="text-xs text-ink/30">—</span>
      ),
  },
  {
    key: "strict_skill_match_required",
    label: "Match",
    sortValue: (r) => (r.strict_skill_match_required ? 1 : 0),
    filterValue: (r) => (r.strict_skill_match_required ? "strict" : "broad"),
    render: (r) => (r.status === "ok" ? (r.strict_skill_match_required ? "Strict" : "Broad") : "—"),
  },
  {
    key: "status",
    label: "Status",
    sortValue: (r) => r.status,
    filterValue: (r) => STATUS_NOTICES[r.status] || r.status,
    render: (r) =>
      r.status !== "ok" ? (
        <span className="text-xs rounded-lg bg-warnSoft text-warn px-2 py-1 inline-block">
          {STATUS_NOTICES[r.status] || r.status}
        </span>
      ) : (
        <span className="text-xs text-accent">OK</span>
      ),
  },
];

export default function Candidates() {
  const [candidates, setCandidates] = useState(null);
  const [error, setError] = useState(null);
  const [checking, setChecking] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState(null);
  const [inviteSuccess, setInviteSuccess] = useState(null);

  async function load() {
    try {
      setError(null);
      const data = await api.listCandidates();
      setCandidates(data);
    } catch (e) {
      setError(e.detail || "Failed to load candidates");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCheckNow() {
    setChecking(true);
    try {
      await api.triggerWatchCycle();
      await load();
    } catch (e) {
      setError(e.detail || "Watch cycle failed");
    } finally {
      setChecking(false);
    }
  }

  async function handleInvite(e) {
    e.preventDefault();
    setInviting(true);
    setInviteError(null);
    setInviteSuccess(null);
    try {
      const res = await api.inviteCandidate(inviteEmail);
      setInviteSuccess(`Invite sent to ${res.invited_email}.`);
      setInviteEmail("");
    } catch (err) {
      setInviteError(err.detail || "Failed to send invite");
    } finally {
      setInviting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Candidates</h1>
          <p className="text-sm text-ink/60 mt-0.5">
            Invite a candidate below to add them to your bench. Once they accept and their
            profile/resume is admin-approved, this list picks them up automatically.
          </p>
        </div>
      </div>

      <form onSubmit={handleInvite} className="rounded-xl border border-black/10 p-4 space-y-3">
        <p className="text-sm font-medium">Invite a candidate</p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="candidate@email.com"
            required
            className="flex-1 rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
          />
          <button
            type="submit"
            disabled={inviting}
            className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {inviting ? "Sending…" : "Send invite"}
          </button>
        </div>
        {inviteError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{inviteError}</div>}
        {inviteSuccess && (
          <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{inviteSuccess}</div>
        )}
      </form>

      <button
        onClick={handleCheckNow}
        disabled={checking}
        className="rounded-lg border border-black/15 px-3 py-2 text-sm font-medium disabled:opacity-50"
      >
        {checking ? "Checking…" : "Check for updates"}
      </button>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      <DataTable
        columns={CANDIDATE_COLUMNS}
        rows={candidates || []}
        rowKey={(r) => r.slug}
        emptyMessage="No candidates yet."
      />
    </div>
  );
}
