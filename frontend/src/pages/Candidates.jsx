import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Candidates() {
  const [candidates, setCandidates] = useState(null);
  const [error, setError] = useState(null);
  const [checking, setChecking] = useState(false);

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

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Candidates</h1>
          <p className="text-sm text-ink/60 mt-0.5">
            Synced from config/candidate.yaml. Add a candidate there and drop their resume in
            resumes/&lt;slug&gt;.docx — this list picks it up automatically.
          </p>
        </div>
      </div>

      <button
        onClick={handleCheckNow}
        disabled={checking}
        className="rounded-lg border border-black/15 px-3 py-2 text-sm font-medium disabled:opacity-50"
      >
        {checking ? "Checking…" : "Check for updates"}
      </button>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      <div className="space-y-2">
        {candidates?.map((c) => (
          <div key={c.slug} className="rounded-xl border border-black/10 p-4 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium">{c.full_name}</p>
                <p className="text-xs text-ink/50 mt-0.5">{c.slug}</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span
                  className={`text-xs rounded-full px-2 py-0.5 font-medium ${
                    c.resume_exists ? "bg-accentSoft text-accent" : "bg-dangerSoft text-danger"
                  }`}
                >
                  {c.resume_exists ? "Resume found" : "Resume missing"}
                </span>
                {c.pending_skill_count > 0 && (
                  <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-warnSoft text-warn">
                    {c.pending_skill_count} pending skill{c.pending_skill_count === 1 ? "" : "s"}
                  </span>
                )}
                {c.status === "ok" && (
                  <span className="text-xs text-ink/40">
                    {c.strict_skill_match_required ? "Strict match" : "Broad match"}
                  </span>
                )}
              </div>
            </div>
            {c.status !== "ok" && (
              <div className="text-xs rounded-lg bg-warnSoft text-warn px-2.5 py-1.5">
                {c.status === "pending_approval" && "Profile submitted, awaiting admin approval."}
                {c.status === "needs_search_config" && "Approved — needs a search config block in candidate.yaml."}
                {c.status === "not_found" && "No profile on record."}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
