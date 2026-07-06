import { useEffect, useState } from "react";
import { api } from "../api/client";

const STATUS_STYLES = {
  eligible: "bg-accentSoft text-accent",
  skipped: "bg-dangerSoft text-danger",
  needs_human_review: "bg-warnSoft text-warn",
};

export default function JobCheck() {
  const [candidates, setCandidates] = useState([]);
  const [candidateSlug, setCandidateSlug] = useState("");
  const [jobText, setJobText] = useState("");
  const [mode, setMode] = useState("paste"); // "paste" | "screenshot"
  const [screenshot, setScreenshot] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listCandidates().then((data) => {
      setCandidates(data);
      if (data.length > 0) setCandidateSlug(data[0].slug);
    });
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res =
        mode === "screenshot"
          ? await api.checkJobScreenshot(candidateSlug, screenshot)
          : await api.checkJob({ candidate_slug: candidateSlug, job_description_text: jobText, save: false });
      setResult(res);
    } catch (e) {
      setError(e.detail || "Check failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Quick check</h1>
        <p className="text-sm text-ink/60 mt-0.5">
          Test whether a job description matches one candidate — a sanity check, not the way to
          actually apply. To post a job and process it against every candidate, use{" "}
          <span className="font-medium">Post Job</span>.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">Candidate</label>
          <select
            value={candidateSlug}
            onChange={(e) => setCandidateSlug(e.target.value)}
            className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm"
          >
            {candidates.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.full_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-ink/60 mb-1">Input method</label>
          <div className="flex rounded-lg border border-black/15 p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => setMode("paste")}
              className={`flex-1 rounded-md py-1.5 ${mode === "paste" ? "bg-ink text-paper" : "text-ink/60"}`}
            >
              Paste text
            </button>
            <button
              type="button"
              onClick={() => setMode("screenshot")}
              className={`flex-1 rounded-md py-1.5 ${mode === "screenshot" ? "bg-ink text-paper" : "text-ink/60"}`}
            >
              Screenshot
            </button>
          </div>
        </div>

        {mode === "paste" ? (
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Job description</label>
            <textarea
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
              rows={10}
              required
              className="w-full rounded-lg border border-black/15 px-3 py-2.5 text-sm font-mono"
              placeholder="Paste the full job posting here…"
            />
          </div>
        ) : (
          <div>
            <label className="block text-xs font-medium text-ink/60 mb-1">Job posting screenshot</label>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => setScreenshot(e.target.files?.[0] || null)}
              required
              className="w-full text-sm"
            />
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !candidateSlug || (mode === "screenshot" && !screenshot)}
          className="w-full rounded-lg bg-ink text-paper py-2.5 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Checking…" : "Check eligibility"}
        </button>
      </form>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {result && (
        <div className="rounded-xl border border-black/10 p-4 space-y-2">
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
              STATUS_STYLES[result.status] || "bg-black/5"
            }`}
          >
            {result.status.replace(/_/g, " ")}
          </span>
          {result.job_title && <p className="text-sm font-medium">{result.job_title}</p>}
          {result.company_name && <p className="text-xs text-ink/50">{result.company_name}</p>}
          {result.location && <p className="text-xs text-ink/50">{result.location}</p>}
          {result.reason && <p className="text-sm text-ink/70">{result.reason}</p>}
          {result.recruiter_email && (
            <p className="text-xs text-ink/50">
              Recruiter: {result.recruiter_name ? `${result.recruiter_name} — ` : ""}
              {result.recruiter_email}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
