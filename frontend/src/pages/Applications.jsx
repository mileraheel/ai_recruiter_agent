import { useEffect, useState } from "react";
import { api } from "../api/client";
import DataTable from "../components/DataTable";

const STAGE_META = {
  contacted: { label: "Contacted", cls: "bg-black/5 text-ink/60" },
  client_submitted: { label: "Submitted to client", cls: "bg-warnSoft text-warn" },
  interviewing: { label: "Interviewing", cls: "bg-accentSoft text-accent" },
  offer: { label: "Offer", cls: "bg-accentSoft text-accent" },
  rejected: { label: "Rejected", cls: "bg-dangerSoft text-danger" },
  withdrawn: { label: "Withdrawn", cls: "bg-black/5 text-ink/40" },
};
const STAGE_OPTIONS = ["contacted", "client_submitted", "interviewing", "offer", "rejected", "withdrawn"];

function StageBadge({ stage }) {
  if (!stage) return <span className="text-xs text-ink/40">No stage set</span>;
  const meta = STAGE_META[stage] || { label: stage, cls: "bg-black/5" };
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${meta.cls}`}>{meta.label}</span>;
}

function ApplicationDetail({ emailId }) {
  const [detail, setDetail] = useState(null);
  const [stage, setStage] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [roundName, setRoundName] = useState("");
  const [addingInterview, setAddingInterview] = useState(false);

  async function load() {
    const data = await api.getApplication(emailId);
    setDetail(data);
    setStage(data.pipeline_stage || "");
    setNotes(data.pipeline_notes || "");
  }

  useEffect(() => {
    load();
  }, [emailId]);

  async function handleSaveStage() {
    setSaving(true);
    try {
      await api.updatePipeline(emailId, { pipeline_stage: stage || null, pipeline_notes: notes || null });
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function handleAddInterview() {
    if (!roundName.trim()) return;
    setAddingInterview(true);
    try {
      await api.addInterview(emailId, { round_name: roundName });
      setRoundName("");
      await load();
    } finally {
      setAddingInterview(false);
    }
  }

  if (!detail) return <p className="text-xs text-ink/40">Loading…</p>;

  return (
    <div className="space-y-4" onClick={(e) => e.stopPropagation()}>
      <div className="text-xs text-ink/50 space-y-0.5">
        <p>To: {detail.to_email || "—"}</p>
        <p>Subject: {detail.subject}</p>
        <p>Resume: {detail.resume_file_name || "—"}</p>
        <p>Send status: {detail.send_status}</p>
      </div>

      <details>
        <summary className="cursor-pointer text-xs text-ink/50">View email body</summary>
        <pre className="whitespace-pre-wrap bg-black/5 rounded-lg p-3 mt-1 max-h-56 overflow-y-auto text-xs">
          {detail.body}
        </pre>
      </details>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-ink/60">Pipeline stage</label>
        <select
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          className="rounded-lg border border-black/15 px-3 py-2 text-sm"
        >
          <option value="">— not set —</option>
          {STAGE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {STAGE_META[s].label}
            </option>
          ))}
        </select>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes (e.g. recruiter feedback, submission details)"
          rows={2}
          className="w-full rounded-lg border border-black/15 px-3 py-2 text-sm"
        />
        <button
          onClick={handleSaveStage}
          disabled={saving}
          className="rounded-lg bg-ink text-paper px-4 py-2 text-xs font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-ink/60">Interviews</label>
        {detail.interviews.length === 0 && <p className="text-xs text-ink/40">None logged yet.</p>}
        <div className="space-y-1.5">
          {detail.interviews.map((iv) => (
            <div key={iv.id} className="flex items-center justify-between text-xs bg-black/5 rounded-lg px-3 py-2">
              <span>{iv.round_name || "Interview"}</span>
              <span className="text-ink/50">{iv.status}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={roundName}
            onChange={(e) => setRoundName(e.target.value)}
            placeholder="e.g. Phone Screen, Technical, Final"
            className="flex-1 rounded-lg border border-black/15 px-3 py-2 text-xs"
          />
          <button
            onClick={handleAddInterview}
            disabled={addingInterview || !roundName.trim()}
            className="rounded-lg border border-black/15 px-3 py-2 text-xs font-medium disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

const APPLICATION_COLUMNS = [
  {
    key: "candidate_full_name",
    label: "Candidate",
    sortValue: (r) => r.candidate_full_name?.toLowerCase() || "",
    filterValue: (r) => r.candidate_full_name,
    render: (r) => <span className="font-medium">{r.candidate_full_name}</span>,
  },
  {
    key: "job_title",
    label: "Role",
    sortValue: (r) => r.job_title?.toLowerCase() || "",
    filterValue: (r) => `${r.job_title || ""} ${r.company_name || ""}`,
    render: (r) => (
      <div>
        <p>{r.job_title || "(untitled)"}</p>
        {r.company_name && <p className="text-xs text-ink/50">{r.company_name}</p>}
      </div>
    ),
  },
  {
    key: "pipeline_stage",
    label: "Stage",
    sortValue: (r) => r.pipeline_stage || "",
    filterValue: (r) => (r.pipeline_stage ? STAGE_META[r.pipeline_stage]?.label || r.pipeline_stage : "not set"),
    render: (r) => <StageBadge stage={r.pipeline_stage} />,
  },
  {
    key: "interview_count",
    label: "Interviews",
    sortValue: (r) => r.interview_count,
    filterValue: (r) => r.interview_count,
    render: (r) => (r.interview_count > 0 ? `${r.interview_count}` : "—"),
  },
  {
    key: "sent_at",
    label: "Sent",
    sortValue: (r) => r.sent_at || "",
    filterValue: (r) => r.sent_at,
    render: (r) => (r.sent_at ? new Date(r.sent_at).toLocaleDateString() : "—"),
  },
];

export default function Applications() {
  const [applications, setApplications] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listApplications().then(setApplications).catch((e) => setError(e.detail || "Failed to load"));
    api.getReportsSummary().then(setSummary).catch(() => {});
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Applications</h1>
        <p className="text-sm text-ink/60 mt-0.5">
          Every application prepared/sent for your candidates — persists across refreshes. Click a row
          to view details and update its pipeline stage.
        </p>
      </div>

      {summary && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {[
            ["Prepared", summary.total_prepared],
            ["Sent", summary.total_sent],
            ["Submitted", summary.total_client_submitted],
            ["Interviewing", summary.total_interviewing],
            ["Offers", summary.total_offers],
            ["Rejected", summary.total_rejected],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-black/10 p-2 text-center">
              <p className="text-lg font-semibold">{value}</p>
              <p className="text-[10px] text-ink/50">{label}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      <DataTable
        columns={APPLICATION_COLUMNS}
        rows={applications || []}
        rowKey={(r) => r.email_id}
        emptyMessage="No applications yet — post a job to get started."
        expandedContent={(r) => <ApplicationDetail emailId={r.email_id} />}
      />
    </div>
  );
}
