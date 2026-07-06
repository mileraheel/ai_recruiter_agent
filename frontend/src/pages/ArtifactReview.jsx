import { useEffect, useState } from "react";
import { api } from "../api/client";
import SelfApprovalDisclaimer from "../components/SelfApprovalDisclaimer";

function ResumeApprovalCard({ item, onDecide }) {
  const [busy, setBusy] = useState(false);

  async function decide(decision) {
    setBusy(true);
    try {
      await onDecide(item.id, decision);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-black/10 p-4 space-y-2">
      <p className="font-medium text-sm">{item.candidate_name}</p>
      <p className="text-xs text-ink/50">
        New resume uploaded — {item.new_skills_suggested} new skill{item.new_skills_suggested === 1 ? "" : "s"} detected
        (reviewed separately in the Approval Queue).
      </p>
      <p className="text-xs text-ink/40">
        This file only becomes the live resume used for tailoring once approved.
      </p>
      <div className="flex gap-2 pt-1">
        <button
          disabled={busy}
          onClick={() => decide("approve")}
          className="flex-1 rounded-lg bg-accent text-white text-sm font-medium py-2 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => decide("reject")}
          className="flex-1 rounded-lg bg-dangerSoft text-danger text-sm font-medium py-2 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

function DocumentCard({ doc, onDecide }) {
  const [busy, setBusy] = useState(false);

  async function decide(decision) {
    setBusy(true);
    try {
      await onDecide(doc.id, decision);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-black/10 p-4 space-y-2">
      <p className="font-medium text-sm">{doc.candidate_name}</p>
      <p className="text-xs text-ink/50">
        {doc.document_type} — {doc.file_name}
      </p>
      <div className="flex gap-2 pt-1">
        <button
          disabled={busy}
          onClick={() => decide("approve")}
          className="flex-1 rounded-lg bg-accent text-white text-sm font-medium py-2 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => decide("reject")}
          className="flex-1 rounded-lg bg-dangerSoft text-danger text-sm font-medium py-2 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function ArtifactReview() {
  const [resumeRuns, setResumeRuns] = useState(null);
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const [runs, docs] = await Promise.all([
        api.listPendingResumeApprovals(),
        api.listPendingDocuments(),
      ]);
      setResumeRuns(runs);
      setDocuments(docs);
    } catch (e) {
      setError(e.detail || "Failed to load pending items");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleResumeDecide(runId, decision) {
    await api.decideResumeApproval(runId, { decision });
    setResumeRuns((prev) => prev.filter((r) => r.id !== runId));
  }

  async function handleDocumentDecide(docId, decision) {
    await api.decideDocument(docId, { decision });
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  }

  const nothingPending = resumeRuns?.length === 0 && documents?.length === 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Resumes & documents</h1>
        <p className="text-sm text-ink/60 mt-0.5">
          Resume file updates and supporting documents (passport, visa, I-94, etc.) — held here until
          approved, separate from the skills approval queue.
        </p>
      </div>

      <SelfApprovalDisclaimer />

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {nothingPending && (
        <div className="rounded-xl border border-dashed border-black/15 p-8 text-center">
          <p className="text-sm text-ink/50">Nothing pending.</p>
        </div>
      )}

      {resumeRuns?.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-ink/70">Resume updates</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {resumeRuns.map((r) => (
              <ResumeApprovalCard key={r.id} item={r} onDecide={handleResumeDecide} />
            ))}
          </div>
        </div>
      )}

      {documents?.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-ink/70">Documents</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {documents.map((d) => (
              <DocumentCard key={d.id} doc={d} onDecide={handleDocumentDecide} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
