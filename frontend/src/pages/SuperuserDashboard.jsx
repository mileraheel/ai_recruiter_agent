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

  const [staffList, setStaffList] = useState(null);
  const [staffUsername, setStaffUsername] = useState("");
  const [staffPassword, setStaffPassword] = useState("");
  const [creatingStaff, setCreatingStaff] = useState(false);
  const [staffError, setStaffError] = useState(null);
  const [staffSuccess, setStaffSuccess] = useState(null);

  const [orgName, setOrgName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [accountType, setAccountType] = useState("agency");
  const [trialDays, setTrialDays] = useState("14");
  const [creatingOrg, setCreatingOrg] = useState(false);
  const [orgError, setOrgError] = useState(null);
  const [orgSuccess, setOrgSuccess] = useState(null);

  async function loadStaff() {
    try {
      setStaffList(await api.getStaffPerformance());
    } catch (e) {
      setStaffError(e.detail || "Failed to load staff");
    }
  }

  useEffect(() => {
    api.getPlatformSummary().then(setSummary).catch((e) => setError(e.detail || "Failed to load"));
    loadStaff();
  }, []);

  async function handleCreateStaff(e) {
    e.preventDefault();
    setCreatingStaff(true);
    setStaffError(null);
    setStaffSuccess(null);
    try {
      const res = await api.createStaff(staffUsername, staffPassword);
      setStaffSuccess(`Staff account '${res.username}' created.`);
      setStaffUsername("");
      setStaffPassword("");
      await loadStaff();
    } catch (err) {
      setStaffError(err.detail || "Failed to create staff account");
    } finally {
      setCreatingStaff(false);
    }
  }

  async function handleCreateOrganization(e) {
    e.preventDefault();
    setCreatingOrg(true);
    setOrgError(null);
    setOrgSuccess(null);
    try {
      const res = await api.createOrganization({
        organization_name: orgName,
        admin_email: adminEmail,
        account_type: accountType,
        trial_days: trialDays === "" ? null : Number(trialDays),
      });
      setOrgSuccess(
        `'${res.organization_name}' created — invite sent to ${res.invited_email}.` +
          (res.trial_expires_at ? ` Trial expires ${res.trial_expires_at}.` : " No trial expiry set.")
      );
      setOrgName("");
      setAdminEmail("");
      setAccountType("agency");
      setTrialDays("14");
      api.getPlatformSummary().then(setSummary).catch(() => {});
    } catch (err) {
      setOrgError(err.detail || "Failed to create organization");
    } finally {
      setCreatingOrg(false);
    }
  }

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
                  <th className="px-3 py-2 font-medium">Sales person</th>
                  <th className="px-3 py-2 font-medium">Candidates</th>
                  <th className="px-3 py-2 font-medium">Admins</th>
                  <th className="px-3 py-2 font-medium">Jobs</th>
                  <th className="px-3 py-2 font-medium">Sent</th>
                  <th className="px-3 py-2 font-medium">Interviews</th>
                  <th className="px-3 py-2 font-medium">Trial</th>
                </tr>
              </thead>
              <tbody>
                {summary.organizations.map((org) => (
                  <tr key={org.organization_id} className="border-t border-black/10">
                    <td className="px-3 py-2 font-medium">{org.organization_name}</td>
                    <td className="px-3 py-2 text-xs text-ink/60">{org.sales_person || "—"}</td>
                    <td className="px-3 py-2">{org.candidate_count}</td>
                    <td className="px-3 py-2">{org.admin_count}</td>
                    <td className="px-3 py-2">{org.jobs_posted}</td>
                    <td className="px-3 py-2">{org.applications_sent}</td>
                    <td className="px-3 py-2">{org.interviews_scheduled}</td>
                    <td className="px-3 py-2 text-xs">
                      {org.trial_expires_at
                        ? `${org.trial_expires_at}${
                            org.trial_days_remaining !== null && org.trial_days_remaining !== undefined
                              ? ` (${org.trial_days_remaining}d)`
                              : ""
                          }`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight">Onboard an organization directly</h2>
        <form onSubmit={handleCreateOrganization} className="rounded-xl border border-black/10 p-4 space-y-3">
          <p className="text-sm font-medium">Create an organization or standalone candidate</p>
          <p className="text-xs text-ink/50">
            You'll be recorded as the sales person for this account. Choose 'Individual' to onboard a
            single standalone candidate (one person, self-managed — no separate staffing agency).
          </p>
          <div className="grid sm:grid-cols-2 gap-3">
            <input
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Organization name"
              required
              className="rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
            <input
              type="email"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              placeholder="Admin/candidate email"
              required
              className="rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-ink/70">
              <span>Account type</span>
              <select
                value={accountType}
                onChange={(e) => setAccountType(e.target.value)}
                className="rounded-lg border border-black/15 px-2 py-1.5 text-sm"
              >
                <option value="agency">Agency</option>
                <option value="individual">Individual (standalone candidate)</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-ink/70">
              <span>Free trial (days)</span>
              <input
                type="number"
                min="0"
                value={trialDays}
                onChange={(e) => setTrialDays(e.target.value)}
                placeholder="e.g. 14"
                className="w-24 rounded-lg border border-black/15 px-2 py-1.5 text-sm"
              />
            </label>
            <span className="text-xs text-ink/40">Leave blank for no trial expiry</span>
          </div>
          <button
            type="submit"
            disabled={creatingOrg}
            className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {creatingOrg ? "Creating…" : "Create & send invite"}
          </button>
          {orgError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{orgError}</div>}
          {orgSuccess && <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{orgSuccess}</div>}
        </form>
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight">Staff accounts</h2>
        <form onSubmit={handleCreateStaff} className="rounded-xl border border-black/10 p-4 space-y-3">
          <p className="text-sm font-medium">Create a staff account</p>
          <p className="text-xs text-ink/50">
            Staff members onboard organizations onto the platform (they sign in separately at
            /staff/login).
          </p>
          <div className="grid sm:grid-cols-2 gap-3">
            <input
              type="text"
              value={staffUsername}
              onChange={(e) => setStaffUsername(e.target.value)}
              placeholder="Username"
              required
              className="rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
            <input
              type="password"
              value={staffPassword}
              onChange={(e) => setStaffPassword(e.target.value)}
              placeholder="Password (10+ characters)"
              required
              minLength={10}
              className="rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>
          <button
            type="submit"
            disabled={creatingStaff}
            className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {creatingStaff ? "Creating…" : "Create staff account"}
          </button>
          {staffError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{staffError}</div>}
          {staffSuccess && (
            <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{staffSuccess}</div>
          )}
        </form>

        {staffList && staffList.length > 0 && (
          <div className="rounded-xl border border-black/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-black/5 text-left text-xs text-ink/50">
                <tr>
                  <th className="px-3 py-2 font-medium">Username</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Orgs onboarded</th>
                  <th className="px-3 py-2 font-medium">Active orgs</th>
                  <th className="px-3 py-2 font-medium">Candidates (across orgs)</th>
                </tr>
              </thead>
              <tbody>
                {staffList.map((s) => (
                  <tr key={s.staff_id} className="border-t border-black/10">
                    <td className="px-3 py-2 font-medium">{s.username}</td>
                    <td className="px-3 py-2">{s.is_active ? "Active" : "Inactive"}</td>
                    <td className="px-3 py-2">{s.organizations_onboarded}</td>
                    <td className="px-3 py-2">{s.active_organizations}</td>
                    <td className="px-3 py-2">{s.total_candidates_across_orgs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
