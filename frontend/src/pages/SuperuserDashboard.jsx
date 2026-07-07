import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import DataTable from "../components/DataTable";

function StatCard({ label, value }) {
  return (
    <div className="rounded-xl border border-black/10 p-4">
      <p className="text-2xl font-semibold tracking-tight">{value}</p>
      <p className="text-xs text-ink/50 mt-0.5">{label}</p>
    </div>
  );
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
        active ? "bg-ink text-paper" : "text-ink/60 hover:bg-black/5"
      }`}
    >
      {children}
    </button>
  );
}

const ORG_COLUMNS = [
  {
    key: "organization_name",
    label: "Organization",
    sortValue: (r) => r.organization_name?.toLowerCase() || "",
    filterValue: (r) => r.organization_name,
    render: (r) => <span className="font-medium">{r.organization_name}</span>,
  },
  {
    key: "sales_person",
    label: "Sales person",
    sortValue: (r) => r.sales_person?.toLowerCase() || "",
    filterValue: (r) => r.sales_person,
    render: (r) => <span className="text-xs text-ink/60">{r.sales_person || "—"}</span>,
  },
  { key: "candidate_count", label: "Candidates", sortValue: (r) => r.candidate_count, filterValue: (r) => r.candidate_count },
  { key: "admin_count", label: "Admins", sortValue: (r) => r.admin_count, filterValue: (r) => r.admin_count },
  { key: "jobs_posted", label: "Jobs", sortValue: (r) => r.jobs_posted, filterValue: (r) => r.jobs_posted },
  { key: "applications_sent", label: "Sent", sortValue: (r) => r.applications_sent, filterValue: (r) => r.applications_sent },
  { key: "interviews_scheduled", label: "Interviews", sortValue: (r) => r.interviews_scheduled, filterValue: (r) => r.interviews_scheduled },
  {
    key: "trial",
    label: "Trial",
    sortValue: (r) => (r.trial_days_remaining === null || r.trial_days_remaining === undefined ? null : r.trial_days_remaining),
    filterValue: (r) => r.trial_expires_at,
    render: (r) => (
      <span className="text-xs">
        {r.trial_expires_at
          ? `${r.trial_expires_at}${r.trial_days_remaining !== null && r.trial_days_remaining !== undefined ? ` (${r.trial_days_remaining}d)` : ""}`
          : "—"}
      </span>
    ),
  },
];

const STAFF_COLUMNS = [
  { key: "username", label: "Username", sortValue: (r) => r.username?.toLowerCase() || "", filterValue: (r) => r.username, render: (r) => <span className="font-medium">{r.username}</span> },
  { key: "is_active", label: "Status", sortValue: (r) => (r.is_active ? 1 : 0), filterValue: (r) => (r.is_active ? "active" : "inactive"), render: (r) => (r.is_active ? "Active" : "Inactive") },
  { key: "organizations_onboarded", label: "Orgs onboarded", sortValue: (r) => r.organizations_onboarded, filterValue: (r) => r.organizations_onboarded },
  { key: "active_organizations", label: "Active orgs", sortValue: (r) => r.active_organizations, filterValue: (r) => r.active_organizations },
  { key: "total_candidates_across_orgs", label: "Candidates (across orgs)", sortValue: (r) => r.total_candidates_across_orgs, filterValue: (r) => r.total_candidates_across_orgs },
];

const INVITE_COLUMNS = [
  { key: "email", label: "Email", sortValue: (r) => r.email.toLowerCase(), filterValue: (r) => r.email, render: (r) => <span className="font-medium">{r.email}</span> },
  { key: "role", label: "Role", sortValue: (r) => r.role, filterValue: (r) => r.role },
  { key: "organization_name", label: "Organization", sortValue: (r) => r.organization_name?.toLowerCase() || "", filterValue: (r) => r.organization_name, render: (r) => r.organization_name || "—" },
  { key: "invited_by_type", label: "Invited by", sortValue: (r) => r.invited_by_type, filterValue: (r) => r.invited_by_type },
  {
    key: "expires_at",
    label: "Expires",
    sortValue: (r) => r.expires_at,
    filterValue: (r) => r.expires_at,
    render: (r) => new Date(r.expires_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }),
  },
  { key: "attempts", label: "Attempts", sortValue: (r) => r.attempts, filterValue: (r) => `${r.attempts}/${r.max_attempts}`, render: (r) => `${r.attempts}/${r.max_attempts}` },
];

export default function SuperuserDashboard() {
  const { logout } = useAuth();
  const [tab, setTab] = useState("manage"); // "manage" | "reports"

  const [summary, setSummary] = useState(null);
  const [staffList, setStaffList] = useState(null);
  const [pendingInvites, setPendingInvites] = useState(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState(null);
  const [reportsLoadedOnce, setReportsLoadedOnce] = useState(false);

  const [staffEmail, setStaffEmail] = useState("");
  const [invitingStaff, setInvitingStaff] = useState(false);
  const [staffError, setStaffError] = useState(null);
  const [staffSuccess, setStaffSuccess] = useState(null);

  const [orgName, setOrgName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [accountType, setAccountType] = useState("agency");
  const [trialDays, setTrialDays] = useState("14");
  const [creatingOrg, setCreatingOrg] = useState(false);
  const [orgError, setOrgError] = useState(null);
  const [orgSuccess, setOrgSuccess] = useState(null);

  const [inviteExpireDays, setInviteExpireDays] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsError, setSettingsError] = useState(null);
  const [settingsSuccess, setSettingsSuccess] = useState(null);

  useEffect(() => {
    // Cheap single-row fetch needed for the default-visible Manage tab's
    // settings form -- unlike the Reports tab's heavier data (org list,
    // staff performance, pending invites), which only loads when that
    // tab is actually opened, this is negligible enough to just load
    // once on mount.
    api.getPlatformSettings().then((s) => setInviteExpireDays(s.invite_expire_days)).catch(() => {});
  }, []);

  async function loadReports() {
    setReportsLoading(true);
    setReportsError(null);
    try {
      const [summaryRes, staffRes, invitesRes] = await Promise.all([
        api.getPlatformSummary(),
        api.getStaffPerformance(),
        api.listPendingInvites(),
      ]);
      setSummary(summaryRes);
      setStaffList(staffRes);
      setPendingInvites(invitesRes);
      setReportsLoadedOnce(true);
    } catch (e) {
      setReportsError(e.detail || "Failed to load reports");
    } finally {
      setReportsLoading(false);
    }
  }

  function handleReportsTabClick() {
    setTab("reports");
    // Only hits the backend the first time this tab is opened -- switching
    // back and forth afterward reuses what's already in state. Use
    // "Refresh" to explicitly re-fetch.
    if (!reportsLoadedOnce) loadReports();
  }

  async function handleInviteStaff(e) {
    e.preventDefault();
    setInvitingStaff(true);
    setStaffError(null);
    setStaffSuccess(null);
    try {
      const res = await api.inviteStaff(staffEmail);
      setStaffSuccess(`Invite sent to ${res.invited_email}.`);
      setStaffEmail("");
      if (reportsLoadedOnce) loadReports();
    } catch (err) {
      setStaffError(err.detail || "Failed to invite staff member");
    } finally {
      setInvitingStaff(false);
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
      if (reportsLoadedOnce) loadReports();
    } catch (err) {
      setOrgError(err.detail || "Failed to create organization");
    } finally {
      setCreatingOrg(false);
    }
  }

  async function handleSaveSettings(e) {
    e.preventDefault();
    setSavingSettings(true);
    setSettingsError(null);
    setSettingsSuccess(null);
    try {
      const res = await api.updatePlatformSettings({ invite_expire_days: Number(inviteExpireDays) });
      setInviteExpireDays(res.invite_expire_days);
      setSettingsSuccess("Saved. New invites will use this expiry going forward.");
    } catch (err) {
      setSettingsError(err.detail || "Failed to save settings");
    } finally {
      setSavingSettings(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Platform overview</h1>
        <button onClick={logout} className="text-xs font-medium text-ink/50">
          Log out
        </button>
      </div>

      <div className="flex items-center gap-1 border-b border-black/10 pb-2">
        <TabButton active={tab === "manage"} onClick={() => setTab("manage")}>
          Manage
        </TabButton>
        <TabButton active={tab === "reports"} onClick={handleReportsTabClick}>
          Reports
        </TabButton>
      </div>

      {tab === "reports" && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <p className="text-xs text-ink/40">
              {reportsLoadedOnce && !reportsLoading && "Loaded once for this visit — use Refresh to update."}
            </p>
            <button
              onClick={loadReports}
              disabled={reportsLoading}
              className="text-xs font-medium underline text-ink/50 disabled:opacity-50"
            >
              {reportsLoading ? "Loading…" : "Refresh"}
            </button>
          </div>

          {reportsError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{reportsError}</div>}
          {reportsLoading && !summary && <p className="text-sm text-ink/40">Loading reports…</p>}

          {summary && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <StatCard label="Organizations" value={summary.organization_count} />
                <StatCard label="Candidates" value={summary.total_candidates} />
                <StatCard label="Jobs posted" value={summary.total_jobs_posted} />
                <StatCard label="Applications sent" value={summary.total_applications_sent} />
                <StatCard label="Interviews" value={summary.total_interviews} />
              </div>

              <div>
                <h2 className="text-sm font-semibold tracking-tight mb-2">Organizations</h2>
                <DataTable
                  columns={ORG_COLUMNS}
                  rows={summary.organizations}
                  rowKey={(r) => r.organization_id}
                  emptyMessage="No organizations yet."
                />
              </div>
            </>
          )}

          {staffList && (
            <div>
              <h2 className="text-sm font-semibold tracking-tight mb-2">Staff performance</h2>
              <DataTable
                columns={STAFF_COLUMNS}
                rows={staffList}
                rowKey={(r) => r.staff_id}
                emptyMessage="No staff accounts yet."
              />
            </div>
          )}

          {pendingInvites && (
            <div>
              <h2 className="text-sm font-semibold tracking-tight mb-2">Pending invites</h2>
              <DataTable
                columns={INVITE_COLUMNS}
                rows={pendingInvites}
                rowKey={(r) => r.id}
                emptyMessage="No pending invites."
              />
            </div>
          )}
        </div>
      )}

      {tab === "manage" && (
        <div className="space-y-6">
          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight">Onboard an organization directly</h2>
            <form onSubmit={handleCreateOrganization} className="rounded-xl border border-black/10 p-4 space-y-3">
              <p className="text-sm font-medium">Create an organization or standalone candidate</p>
              <p className="text-xs text-ink/50">
                You'll be recorded as the sales person for this account. Choose 'Individual' to onboard a
                single standalone candidate (one person, self-managed — no separate staffing agency). They'll
                receive an OTP invite email to set their own password.
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
            <form onSubmit={handleInviteStaff} className="rounded-xl border border-black/10 p-4 space-y-3">
              <p className="text-sm font-medium">Invite a staff member</p>
              <p className="text-xs text-ink/50">
                Just their email — they'll receive an OTP code by email and choose their own
                username and password when they redeem it (they sign in separately at /staff/login).
              </p>
              <input
                type="email"
                value={staffEmail}
                onChange={(e) => setStaffEmail(e.target.value)}
                placeholder="Email address"
                required
                className="w-full sm:w-80 rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              />
              <div>
                <button
                  type="submit"
                  disabled={invitingStaff}
                  className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                  {invitingStaff ? "Sending…" : "Send invite"}
                </button>
              </div>
              {staffError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{staffError}</div>}
              {staffSuccess && (
                <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{staffSuccess}</div>
              )}
            </form>
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight">Platform settings</h2>
            <form onSubmit={handleSaveSettings} className="rounded-xl border border-black/10 p-4 space-y-3">
              <p className="text-sm font-medium">Invite expiry</p>
              <p className="text-xs text-ink/50">
                How long an OTP invite (staff, organization, or candidate) stays valid before it
                expires. Applies to every new invite sent from now on — doesn't change invites
                already sent.
              </p>
              <label className="flex items-center gap-2 text-sm text-ink/70">
                <span>Days</span>
                <input
                  type="number"
                  min="1"
                  value={inviteExpireDays ?? ""}
                  onChange={(e) => setInviteExpireDays(e.target.value)}
                  placeholder="e.g. 7"
                  className="w-24 rounded-lg border border-black/15 px-2 py-1.5 text-sm"
                />
              </label>
              <button
                type="submit"
                disabled={savingSettings || inviteExpireDays === null}
                className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
              >
                {savingSettings ? "Saving…" : "Save"}
              </button>
              {settingsError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{settingsError}</div>}
              {settingsSuccess && (
                <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{settingsSuccess}</div>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
