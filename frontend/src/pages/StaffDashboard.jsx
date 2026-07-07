import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import DataTable from "../components/DataTable";

const ORG_COLUMNS = (onDeactivate) => [
  {
    key: "organization_name",
    label: "Organization",
    sortValue: (r) => r.organization_name?.toLowerCase() || "",
    filterValue: (r) => r.organization_name,
    render: (r) => <span className="font-medium">{r.organization_name}</span>,
  },
  { key: "account_type", label: "Type", sortValue: (r) => r.account_type, filterValue: (r) => r.account_type },
  { key: "candidate_count", label: "Candidates", sortValue: (r) => r.candidate_count, filterValue: (r) => r.candidate_count },
  { key: "admin_count", label: "Admins", sortValue: (r) => r.admin_count, filterValue: (r) => r.admin_count },
  { key: "jobs_posted", label: "Jobs", sortValue: (r) => r.jobs_posted, filterValue: (r) => r.jobs_posted },
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
  {
    key: "is_active",
    label: "Status",
    sortValue: (r) => (r.is_active ? 1 : 0),
    filterValue: (r) => (r.is_active ? "active" : "deactivated"),
    render: (r) => (
      <span
        className={`text-xs rounded-full px-2 py-0.5 font-medium ${
          r.is_active ? "bg-accentSoft text-accent" : "bg-dangerSoft text-danger"
        }`}
      >
        {r.is_active ? "Active" : "Deactivated"}
      </span>
    ),
  },
  {
    key: "actions",
    label: "",
    render: (r) =>
      r.is_active && (
        <button onClick={() => onDeactivate(r.organization_id, r.organization_name)} className="text-xs font-medium text-danger">
          Deactivate
        </button>
      ),
  },
];

export default function StaffDashboard() {
  const [orgs, setOrgs] = useState(null);
  const [error, setError] = useState(null);
  const { logout } = useAuth();

  const [orgName, setOrgName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [accountType, setAccountType] = useState("agency");
  const [trialDays, setTrialDays] = useState("14");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState(null);
  const [inviteSuccess, setInviteSuccess] = useState(null);

  async function load() {
    try {
      setError(null);
      setOrgs(await api.listMyOrganizations());
    } catch (e) {
      setError(e.detail || "Failed to load organizations");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleInvite(e) {
    e.preventDefault();
    setInviting(true);
    setInviteError(null);
    setInviteSuccess(null);
    try {
      const res = await api.inviteOrganization({
        organization_name: orgName,
        admin_email: adminEmail,
        account_type: accountType,
        trial_days: trialDays === "" ? null : Number(trialDays),
      });
      setInviteSuccess(
        `'${res.organization_name}' created — invite sent to ${res.invited_email}.` +
          (res.trial_expires_at ? ` Trial expires ${res.trial_expires_at}.` : " No trial expiry set.")
      );
      setOrgName("");
      setAdminEmail("");
      setAccountType("agency");
      setTrialDays("14");
      await load();
    } catch (err) {
      setInviteError(err.detail || "Failed to create organization");
    } finally {
      setInviting(false);
    }
  }

  async function handleDeactivate(organizationId, organizationName) {
    if (!window.confirm(`Deactivate '${organizationName}'? Its data is kept, but it stops resolving for login/matching.`)) {
      return;
    }
    try {
      await api.deactivateOrganization(organizationId);
      await load();
    } catch (e) {
      setError(e.detail || "Failed to deactivate organization");
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Organizations you've onboarded</h1>
        <button onClick={logout} className="text-xs font-medium text-ink/50">
          Log out
        </button>
      </div>

      <form onSubmit={handleInvite} className="rounded-xl border border-black/10 p-4 space-y-3">
        <p className="text-sm font-medium">Onboard a new organization</p>
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
            placeholder="First admin's email"
            required
            className="rounded-lg border border-black/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-ink/70">
          <span>Account type</span>
          <select
            value={accountType}
            onChange={(e) => setAccountType(e.target.value)}
            className="rounded-lg border border-black/15 px-2 py-1.5 text-sm"
          >
            <option value="agency">Agency (staffing company with a bench of candidates)</option>
            <option value="individual">Individual (one person, self-managed)</option>
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
          <span className="text-xs text-ink/40">Leave blank for no trial expiry</span>
        </label>
        <button
          type="submit"
          disabled={inviting}
          className="rounded-lg bg-ink text-paper px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {inviting ? "Creating…" : "Create organization & send invite"}
        </button>
        {inviteError && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{inviteError}</div>}
        {inviteSuccess && (
          <div className="rounded-lg bg-accentSoft text-accent text-sm px-3 py-2">{inviteSuccess}</div>
        )}
      </form>

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      <DataTable
        columns={ORG_COLUMNS(handleDeactivate)}
        rows={orgs || []}
        rowKey={(r) => r.organization_id}
        emptyMessage="No organizations onboarded yet."
      />
    </div>
  );
}
