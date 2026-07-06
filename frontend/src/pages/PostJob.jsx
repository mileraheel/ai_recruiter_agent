import { useState } from "react";
import { api } from "../api/client";

const STATUS_META = {
  eligible: { label: "Eligible", cls: "bg-accentSoft text-accent" },
  skipped: { label: "Skipped", cls: "bg-black/5 text-ink/50" },
  needs_human_review: { label: "Needs review", cls: "bg-warnSoft text-warn" },
  not_active: { label: "Not active", cls: "bg-black/5 text-ink/40" },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status, cls: "bg-black/5" };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${meta.cls}`}>{meta.label}</span>
  );
}

function MatchCard({ result, selected, onToggle, sendStatus }) {
  const eligible = result.eligibility_status === "eligible";
  const hasEmail = !!result.email_id;

  return (
    <div className="rounded-xl border border-black/10 p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          {eligible && hasEmail && !sendStatus && (
            <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1 rounded" />
          )}
          <div>
            <p className="font-medium">{result.candidate_full_name}</p>
            <p className="text-xs text-ink/50">{result.candidate_slug}</p>
          </div>
        </div>
        <StatusBadge status={result.eligibility_status} />
      </div>

      {result.reason && <p className="text-xs text-ink/60">{result.reason}</p>}
      {result.prepare_error && (
        <p className="text-xs text-danger bg-dangerSoft rounded-lg px-2 py-1">{result.prepare_error}</p>
      )}

      {hasEmail && (
        <div className="text-xs text-ink/60 space-y-1 pt-1">
          <p>To: {result.to_email || "no recruiter email found"}</p>
          <p>Subject: {result.subject}</p>
          <p>Resume: {result.resume_file_name}</p>
          {result.resume_human_review_required && (
            <p className="text-warn bg-warnSoft rounded px-2 py-1">Resume flagged for review before sending.</p>
          )}
          <details className="pt-1">
            <summary className="cursor-pointer text-ink/50">Preview email</summary>
            <pre className="whitespace-pre-wrap bg-black/5 rounded-lg p-2 mt-1 max-h-48 overflow-y-auto">
              {result.body}
            </pre>
          </details>
        </div>
      )}

      {sendStatus && (
        <div
          className={`text-xs rounded-lg px-2 py-1 ${
            sendStatus.error ? "bg-dangerSoft text-danger" : "bg-accentSoft text-accent"
          }`}
        >
          {sendStatus.error || (sendStatus.status === "sent" ? "Sent." : "Drafted in Gmail.")}
        </div>
      )}
    </div>
  );
}

export default function PostJob() {
  const [jobText, setJobText] = useState("");
  const [posting, setPosting] = useState(false);
  const [batchResult, setBatchResult] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [sendResults, setSendResults] = useState({});
  const [sending, setSending] = useState(false);

  async function handlePost(e) {
    e.preventDefault();
    setPosting(true);
    setError(null);
    setBatchResult(null);
    setSelected(new Set());
    setSendResults({});
    try {
      const res = await api.postAndMatch(jobText);
      setBatchResult(res);
      // Pre-select every eligible, successfully-prepared match.
      const preselect = new Set(
        res.results.filter((r) => r.eligibility_status === "eligible" && r.email_id).map((r) => r.email_id)
      );
      setSelected(preselect);
    } catch (e) {
      setError(e.detail || "Failed to post job");
    } finally {
      setPosting(false);
    }
  }

  function toggle(emailId) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(emailId)) next.delete(emailId);
      else next.add(emailId);
      return next;
    });
  }

  async function handleBatchSend() {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    if (!window.confirm(`Send ${ids.length} application${ids.length === 1 ? "" : "s"}? Each goes through that candidate's own connected Gmail.`)) {
      return;
    }
    setSending(true);
    setError(null);
    try {
      const res = await api.batchSend(ids, true);
      const byId = {};
      res.results.forEach((r) => (byId[r.email_id] = r));
      setSendResults(byId);
    } catch (e) {
      setError(e.detail || "Batch send failed");
    } finally {
      setSending(false);
    }
  }

  const eligibleCount = batchResult?.results.filter((r) => r.eligibility_status === "eligible").length || 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Post a job</h1>
        <p className="text-sm text-ink/60 mt-0.5">
          Paste a job posting once. It's checked against every candidate, and a resume + email is
          automatically prepared (not sent) for each match — you review and choose what to send.
        </p>
      </div>

      <form onSubmit={handlePost} className="space-y-3">
        <textarea
          value={jobText}
          onChange={(e) => setJobText(e.target.value)}
          rows={10}
          required
          className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm font-mono"
          placeholder="Paste the full job posting here…"
        />
        <button
          type="submit"
          disabled={posting}
          className="w-full rounded-lg bg-ink text-paper py-2.5 text-sm font-medium disabled:opacity-50"
        >
          {posting ? "Matching against all candidates…" : "Post & match"}
        </button>
      </form>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {batchResult && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink/60">
              {eligibleCount} of {batchResult.results.length} candidate{batchResult.results.length === 1 ? "" : "s"}{" "}
              matched
            </p>
            {selected.size > 0 && (
              <button
                onClick={handleBatchSend}
                disabled={sending}
                className="rounded-lg bg-accent text-white px-4 py-2 text-sm font-medium disabled:opacity-50"
              >
                {sending ? "Sending…" : `Send ${selected.size} selected`}
              </button>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {batchResult.results.map((r) => (
              <MatchCard
                key={r.candidate_slug}
                result={r}
                selected={r.email_id ? selected.has(r.email_id) : false}
                onToggle={() => r.email_id && toggle(r.email_id)}
                sendStatus={r.email_id ? sendResults[r.email_id] : null}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
