import { useEffect, useState } from "react";
import { api } from "../api/client";

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

function ApplicationRow({ app, expanded, onToggle }) {
  return (
    <div className="rounded-xl border border-black/10 overflow-hidden">
      <button onClick={onToggle} className="w-full text-left px-4 py-3 flex items-center justify-between gap-3">
        <div>
          <p className="font-medium text-sm">{app.candidate_full_name}</p>
          <p className="text-xs text-ink/50 mt-0.5">
            {app.job_title || "(untitled)"} {app.company_name ? `— ${app.company_name}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <StageBadge stage={app.pipeline_stage} />
          {app.interview_count > 0 && (
            <span className="text-xs text-ink/50">{app.interview_count} interview{app.interview_count === 1 ? "" : "s"}</span>
          )}
        </div>
      </button>
      {expanded && <ApplicationDetail emailId={app.email_id} />}
    </div>
  );
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

  if (!detail) return <div className="px-4 py-3 text-xs text-ink/40 border-t border-black/10">Loading…</div>;

  return (
    <div className="border-t border-black/10 px-4 py-4 space-y-4">
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

export default function Applications() {
  const [applications, setApplications] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    api.listApplications().then(setApplications).catch((e) => setError(e.detail || "Failed to load"));
    api.getReportsSummary().then(setSummary).catch(() => {});
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Applications</h1>
        <p className="text-sm text-ink/60 mt-0.5">Every application prepared/sent for your candidates — persists across refreshes.</p>
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

      {applications !== null && applications.length === 0 && (
        <div className="rounded-xl border border-dashed border-black/15 p-8 text-center">
          <p className="text-sm text-ink/50">No applications yet — post a job to get started.</p>
        </div>
      )}

      <div className="space-y-2">
        {applications?.map((app) => (
          <ApplicationRow
            key={app.email_id}
            app={app}
            expanded={expandedId === app.email_id}
            onToggle={() => setExpandedId(expandedId === app.email_id ? null : app.email_id)}
          />
        ))}
      </div>
    </div>
  );
}
