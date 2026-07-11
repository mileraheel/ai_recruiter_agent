import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import DataTable from "../components/DataTable";

const ORG_COLUMNS = (onDeactivate, onExtendTrial) => [
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
    label: "Active",
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
    key: "status",
    label: "Status",
    sortValue: (r) => r.status_label || "",
    filterValue: (r) => r.status_label,
    render: (r) => (
      <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-ink/5 text-ink/70">
        {r.status_label || "—"}
      </span>
    ),
  },
  {
    key: "actions",
    label: "",
    render: (r) => (
      <div className="flex items-center gap-3">
        <button onClick={() => onExtendTrial(r.organization_id, r.organization_name)} className="text-xs font-medium text-accent">
          Extend trial
        </button>
        {r.is_active && (
          <button onClick={() => onDeactivate(r.organization_id, r.organization_name)} className="text-xs font-medium text-danger">
            Deactivate
          </button>
        )}
      </div>
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
  const [defaultTrialDays, setDefaultTrialDays] = useState(null);
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
    api
      .getStaffTrialDefault()
      .then((s) => {
        setDefaultTrialDays(s.default_trial_days);
        setTrialDays(String(s.default_trial_days));
      })
      .catch(() => {});
  }, []);

  async function handleInvite(e) {
    e.preventDefault();
    setInviting(true);
    setInviteError(null);
    setInviteSuccess(null);
    try {
      const res = await api.inviteOrganization({
        organization_name: accountType === "individual" ? null : orgName,
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
      setTrialDays(defaultTrialDays !== null ? String(defaultTrialDays) : "14");
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

  async function handleExtendTrial(organizationId, organizationName) {
    const input = window.prompt(`Extend trial for '${organizationName}' by how many days?`, "14");
    if (!input) return;
    const days = Number(input);
    if (!Number.isFinite(days) || days <= 0) return;
    try {
      await api.extendMyOrganizationTrial(organizationId, days);
      await load();
    } catch (e) {
      setError(e.detail || "Failed to extend trial");
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Organizations you've onboarded</h1>
        <div className="flex items-center gap-3">
          <Link to="/staff/profile" className="text-xs font-medium text-ink/50">
            Update profile
          </Link>
          <button onClick={logout} className="text-xs font-medium text-ink/50">
            Log out
          </button>
        </div>
      </div>

      <form onSubmit={handleInvite} className="rounded-xl border border-ink/10 p-4 space-y-3">
        <p className="text-sm font-medium">Onboard a new organization</p>
        <input
          type="email"
          value={adminEmail}
          onChange={(e) => setAdminEmail(e.target.value)}
          placeholder="First admin's email"
          required
          className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
        />
        <label className="flex items-center gap-2 text-sm text-ink/70">
          <span>Account type</span>
          <select
            value={accountType}
            onChange={(e) => {
              const next = e.target.value;
              setAccountType(next);
              if (next === "individual") setOrgName("");
            }}
            className="rounded-lg border border-ink/15 px-2 py-1.5 text-sm"
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
            className="w-24 rounded-lg border border-ink/15 px-2 py-1.5 text-sm"
          />
          <span className="text-xs text-ink/40">
            {defaultTrialDays !== null ? `Defaults to ${defaultTrialDays}` : "Leave blank for no trial expiry"}
          </span>
        </label>
        <input
          type="text"
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          placeholder={accountType === "individual" ? "Not needed for individual accounts" : "Organization name"}
          required={accountType === "agency"}
          disabled={accountType === "individual"}
          className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:bg-ink/5 disabled:text-ink/40"
        />
        <button
          type="submit"
          disabled={inviting}
          className="btn btn-primary btn-small disabled:opacity-50"
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
        columns={ORG_COLUMNS(handleDeactivate, handleExtendTrial)}
        rows={orgs || []}
        rowKey={(r) => r.organization_id}
        emptyMessage="No organizations onboarded yet."
      />
    </div>
  );
}
