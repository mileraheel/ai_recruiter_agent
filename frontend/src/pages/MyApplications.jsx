import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import TrialBanner from "../components/TrialBanner";

const STAGE_STYLES = {
  contacted: "bg-black/5 text-ink/60",
  client_submitted: "bg-warnSoft text-warn",
  interviewing: "bg-accentSoft text-accent",
  offer: "bg-accentSoft text-accent",
  rejected: "bg-dangerSoft text-danger",
  withdrawn: "bg-black/5 text-ink/40",
};

const STAGE_LABELS = {
  contacted: "Contacted",
  client_submitted: "Submitted to client",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Not selected",
  withdrawn: "Withdrawn",
};

function formatDateTime(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function MyApplications() {
  const { logout } = useAuth();
  const [applications, setApplications] = useState(null);
  const [upcoming, setUpcoming] = useState(null);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);

  async function load() {
    try {
      setError(null);
      const [apps, interviews] = await Promise.all([api.listMyApplications(), api.listMyUpcomingInterviews()]);
      setApplications(apps);
      setUpcoming(interviews);
    } catch (e) {
      setError(e.detail || "Failed to load your applications");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleExpand(emailId) {
    if (expandedId === emailId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(emailId);
    setDetail(null);
    try {
      setDetail(await api.getMyApplication(emailId));
    } catch (e) {
      setError(e.detail || "Failed to load application detail");
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8 pb-20 space-y-6">
      <TrialBanner />
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Your progress</h1>
          <p className="text-sm text-ink/60 mt-0.5">Applications submitted on your behalf, and where each stands.</p>
        </div>
        <button onClick={logout} className="text-xs font-medium text-ink/50 shrink-0">
          Log out
        </button>
      </div>

      <Link to="/candidate/profile" className="text-xs font-medium underline text-ink/50">
        ← Back to your profile
      </Link>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {/* Upcoming interviews */}
      <div className="rounded-xl border border-black/10 p-4 space-y-3">
        <h2 className="text-sm font-semibold">Upcoming interviews</h2>
        {upcoming === null && <p className="text-xs text-ink/40">Loading…</p>}
        {upcoming?.length === 0 && <p className="text-xs text-ink/40">Nothing scheduled right now.</p>}
        {upcoming?.map((iv) => (
          <div key={iv.id} className="flex items-center justify-between gap-3 text-sm">
            <span>{iv.round_name || "Interview"}</span>
            <span className="text-xs text-ink/50">{formatDateTime(iv.scheduled_at) || "Time TBD"}</span>
          </div>
        ))}
      </div>

      {/* Applications list */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold px-1">Applications</h2>
        {applications === null && <p className="text-xs text-ink/40 px-1">Loading…</p>}
        {applications?.length === 0 && (
          <p className="text-xs text-ink/40 px-1">No applications submitted yet.</p>
        )}
        {applications?.map((app) => (
          <div key={app.email_id} className="rounded-xl border border-black/10 p-4 space-y-2">
            <button
              onClick={() => toggleExpand(app.email_id)}
              className="w-full flex items-center justify-between gap-3 text-left"
            >
              <div>
                <p className="font-medium text-sm">{app.job_title || "Untitled role"}</p>
                <p className="text-xs text-ink/50 mt-0.5">{app.company_name || "Company not on file"}</p>
              </div>
              <span
                className={`shrink-0 text-xs rounded-full px-2 py-0.5 font-medium ${
                  STAGE_STYLES[app.pipeline_stage] || "bg-black/5 text-ink/50"
                }`}
              >
                {STAGE_LABELS[app.pipeline_stage] || "Prepared"}
              </span>
            </button>

            {app.interview_count > 0 && (
              <p className="text-xs text-ink/50">
                {app.interview_count} interview{app.interview_count === 1 ? "" : "s"}
                {app.latest_interview_at && ` · latest ${formatDateTime(app.latest_interview_at)}`}
              </p>
            )}

            {expandedId === app.email_id && (
              <div className="pt-2 border-t border-black/10 space-y-2">
                {detail === null && <p className="text-xs text-ink/40">Loading details…</p>}
                {detail && (
                  <>
                    {detail.sent_at && (
                      <p className="text-xs text-ink/50">Applied {formatDateTime(detail.sent_at)}</p>
                    )}
                    {detail.interviews.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        {detail.interviews.map((iv) => (
                          <div key={iv.id} className="flex items-center justify-between text-xs">
                            <span>{iv.round_name || "Interview"}</span>
                            <span className="text-ink/50">
                              {formatDateTime(iv.scheduled_at) || "Time TBD"} · {iv.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
