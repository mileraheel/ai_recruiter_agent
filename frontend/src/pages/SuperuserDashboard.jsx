import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

function StatCard({ label, value }) {
  return (
    <div className="rounded-xl border border-black/10 p-4">
      <p className="text-2xl font-semibold tracking-tight">{value}</p>
      <p className="text-xs text-ink/50 mt-0.5">{label}</p>
    </div>
  );
}

export default function SuperuserDashboard() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const { logout } = useAuth();

  useEffect(() => {
    api.getPlatformSummary().then(setSummary).catch((e) => setError(e.detail || "Failed to load"));
  }, []);

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Platform overview</h1>
        <button onClick={logout} className="text-xs font-medium text-ink/50">
          Log out
        </button>
      </div>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {summary && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <StatCard label="Organizations" value={summary.organization_count} />
            <StatCard label="Candidates" value={summary.total_candidates} />
            <StatCard label="Jobs posted" value={summary.total_jobs_posted} />
            <StatCard label="Applications sent" value={summary.total_applications_sent} />
            <StatCard label="Interviews" value={summary.total_interviews} />
          </div>

          <div className="rounded-xl border border-black/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-black/5 text-left text-xs text-ink/50">
                <tr>
                  <th className="px-3 py-2 font-medium">Organization</th>
                  <th className="px-3 py-2 font-medium">Candidates</th>
                  <th className="px-3 py-2 font-medium">Admins</th>
                  <th className="px-3 py-2 font-medium">Jobs</th>
                  <th className="px-3 py-2 font-medium">Sent</th>
                  <th className="px-3 py-2 font-medium">Interviews</th>
                </tr>
              </thead>
              <tbody>
                {summary.organizations.map((org) => (
                  <tr key={org.organization_id} className="border-t border-black/10">
                    <td className="px-3 py-2 font-medium">{org.organization_name}</td>
                    <td className="px-3 py-2">{org.candidate_count}</td>
                    <td className="px-3 py-2">{org.admin_count}</td>
                    <td className="px-3 py-2">{org.jobs_posted}</td>
                    <td className="px-3 py-2">{org.applications_sent}</td>
                    <td className="px-3 py-2">{org.interviews_scheduled}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
