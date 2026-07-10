import { useEffect, useState } from "react";
import { api } from "../api/client";

function DiffField({ label, value }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div className="text-xs">
      <span className="text-ink/40">{label}: </span>
      <span className="text-ink/80">{typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</span>
    </div>
  );
}

function SubmissionCard({ submission, onDecide }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const p = submission.submitted_profile_json;

  async function decide(decision) {
    setBusy(true);
    try {
      await onDecide(submission.id, { decision, review_notes: notes || null });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-ink/10 p-4 space-y-3">
      <div>
        <p className="font-medium">{p.full_name}</p>
        <p className="text-xs text-ink/50">{p.email} · {p.location}</p>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <DiffField label="Phone" value={p.phone} />
        <DiffField label="Work auth" value={p.work_authorization} />
        <DiffField label="Requires sponsorship" value={p.requires_sponsorship_or_transfer} />
        <DiffField label="C2C rate" value={p.c2c_rate} />
        <DiffField label="Open to relocation" value={p.open_to_relocation} />
        <DiffField label="Career start" value={p.career_start_date} />
      </div>

      {p.tech_stack_summary && (
        <p className="text-xs text-ink/70 border-l-2 border-ink/10 pl-3 italic">{p.tech_stack_summary}</p>
      )}

      <input
        type="text"
        placeholder="Review notes (optional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="w-full rounded-md border border-ink/15 px-2.5 py-1.5 text-xs"
      />

      <div className="flex gap-2">
        <button
          disabled={busy}
          onClick={() => decide("approve")}
          className="flex-1 btn btn-primary btn-small disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => decide("reject")}
          className="flex-1 btn btn-small bg-dangerSoft text-danger disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function CandidateSubmissions() {
  const [submissions, setSubmissions] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const data = await api.listCandidateSubmissions();
      setSubmissions(data);
    } catch (e) {
      setError(e.detail || "Failed to load submissions");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleDecide(id, decision) {
    await api.decideCandidateSubmission(id, decision);
    setSubmissions((prev) => prev.filter((s) => s.id !== id));
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Candidate profile submissions</h1>
        <p className="text-sm text-ink/60 mt-0.5">
          Self-reported profile edits, held here until approved. Skill claims from resume uploads are
          reviewed separately in the Approval Queue.
        </p>
      </div>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {submissions === null && !error && <p className="text-sm text-ink/50">Loading…</p>}

      {submissions !== null && submissions.length === 0 && (
        <div className="rounded-xl border border-dashed border-ink/15 p-8 text-center">
          <p className="text-sm text-ink/50">No pending submissions.</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {submissions?.map((s) => (
          <SubmissionCard key={s.id} submission={s} onDecide={handleDecide} />
        ))}
      </div>
    </div>
  );
}
