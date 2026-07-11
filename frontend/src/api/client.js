const TOKEN_KEY = "ai_recruiter_token";
const ROLE_KEY = "ai_recruiter_role";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function setRole(role) {
  localStorage.setItem(ROLE_KEY, role);
}

/**
 * Reads the 'role' claim out of a JWT's payload -- no signature
 * verification, since this is only ever called on a token this same
 * browser just received directly from our own backend a moment ago
 * (see AcceptInvite.jsx, the one place the frontend doesn't already
 * know the role ahead of time the way every role-specific login call
 * does). Never use this to make a trust decision about a token from
 * anywhere else.
 */
export function decodeJwtRole(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.role || null;
  } catch {
    return null;
  }
}

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

// Endpoints where a 401 means "wrong credentials", not "your session
// expired" -- there's no session yet at all when hitting these, so the
// generic 401 handler below must not treat it as one. Redirecting here
// wipes the login form (and its error state) out from under the user
// via a full page navigation before they ever see why it failed.
const AUTH_ENDPOINTS = new Set([
  "/auth/login",
  "/auth/signup",
  "/auth/signin",
  "/auth/password-reset/request",
  "/auth/password-reset/confirm",
  "/superuser-auth/login",
  "/candidate-auth/login",
  "/candidate-auth/signup",
  "/staff-auth/login",
  "/invite/register",
]);

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form);
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload });

  if (res.status === 401 && !AUTH_ENDPOINTS.has(path)) {
    // Single login page for every role now, so there's no per-role
    // redirect target to pick between anymore.
    clearToken();
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (username, password) => request("/auth/login", { method: "POST", form: { username, password } }),
  adminSignup: (payload) => request("/auth/signup", { method: "POST", body: payload }),

  // Unified sign-in -- one identifier field (username or email), backend
  // tries every account type and returns whichever matches. Role isn't
  // known ahead of time, so callers decode it from the token (see
  // decodeJwtRole above) the same way AcceptInvite.jsx already does.
  signin: (identifier, password) => request("/auth/signin", { method: "POST", form: { username: identifier, password } }),
  requestPasswordReset: (email) => request("/auth/password-reset/request", { method: "POST", body: { email } }),
  confirmPasswordReset: (payload) => request("/auth/password-reset/confirm", { method: "POST", body: payload }),
  listCandidates: () => request("/candidates?limit=100").then((r) => r.items),
  triggerWatchCycle: () => request("/candidates/watch-cycle", { method: "POST" }),
  listApprovalQueue: (candidateId) =>
    request(`/approval-queue?limit=100${candidateId ? `&candidate_id=${candidateId}` : ""}`).then((r) => r.items),
  decideApproval: (itemId, decision) =>
    request(`/approval-queue/${itemId}/decision`, { method: "POST", body: decision }),
  checkJob: (payload) => request("/jobs/check", { method: "POST", body: payload }),
  checkJobScreenshot: async (candidateSlug, file) => {
    const form = new FormData();
    form.append("candidate_slug", candidateSlug);
    form.append("file", file);
    const headers = {};
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch("/api/jobs/check-screenshot", { method: "POST", headers, body: form });
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },

  // Candidate self-service
  candidateSignup: (payload) => request("/candidate-auth/signup", { method: "POST", body: payload }),
  candidateLogin: (login_email, password) =>
    request("/candidate-auth/login", { method: "POST", body: { login_email, password } }),
  getMe: () => request("/me"),
  submitMyProfile: (payload) => request("/me/profile", { method: "PUT", body: payload }),
  getMySubscription: () => request("/me/subscription"),
  pauseMySubscription: () => request("/me/subscription/pause", { method: "POST" }),
  resumeMySubscription: () => request("/me/subscription/resume", { method: "POST" }),
  listMyApplications: (params = {}) => {
    const qs = new URLSearchParams({ limit: "100", ...params }).toString();
    return request(`/me/applications${qs ? `?${qs}` : ""}`).then((r) => r.items);
  },
  getMyApplication: (emailId) => request(`/me/applications/${emailId}`),
  listMyUpcomingInterviews: () => request("/me/interviews/upcoming"),
  uploadMyResume: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const headers = {};
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch("/api/me/resume", { method: "POST", headers, body: form });
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },
  changeMyPassword: (payload) => request("/me/password", { method: "PUT", body: payload }),

  // Admin self-service (own profile -- distinct from admin managing candidates)
  getAdminMe: () => request("/admin/me"),
  updateAdminProfile: (payload) => request("/admin/me", { method: "PUT", body: payload }),
  changeAdminPassword: (payload) => request("/admin/me/password", { method: "PUT", body: payload }),

  // Staff self-service (own profile)
  getStaffMe: () => request("/staff/me"),
  updateStaffProfile: (payload) => request("/staff/me", { method: "PUT", body: payload }),
  changeStaffPassword: (payload) => request("/staff/me/password", { method: "PUT", body: payload }),

  // Superuser self-service (own profile)
  getSuperuserMe: () => request("/superuser/me"),
  updateSuperuserProfile: (payload) => request("/superuser/me", { method: "PUT", body: payload }),
  changeSuperuserPassword: (payload) => request("/superuser/me/password", { method: "PUT", body: payload }),

  // Admin review of candidate profile submissions
  listCandidateSubmissions: () => request("/candidate-review?limit=100").then((r) => r.items),
  decideCandidateSubmission: (submissionId, decision) =>
    request(`/candidate-review/${submissionId}/decision`, { method: "POST", body: decision }),

  // Connected email account -- Gmail (OAuth) or SMTP (manual entry), same
  // endpoints for every role; the backend resolves who's asking.
  getEmailAccountStatus: () => request("/me/email-account"),
  getEmailConnectUrl: () => request("/me/email-account/connect-url"),
  disconnectEmailAccount: () => request("/me/email-account", { method: "DELETE" }),
  connectSmtp: (payload) => request("/me/email-account/smtp", { method: "PUT", body: payload }),

  // Applications (prepare + send)
  prepareApplication: (jobId) => request(`/applications/${jobId}/prepare`, { method: "POST" }),
  sendApplication: (emailId, confirm) =>
    request(`/applications/emails/${emailId}/send`, { method: "POST", body: { confirm } }),

  // Post a job -> fan out across all candidates
  postAndMatch: (jobDescriptionText) =>
    request("/job-posting/post-and-match", { method: "POST", body: { job_description_text: jobDescriptionText } }),
  batchSend: (emailIds, confirm) =>
    request("/job-posting/batch-send", { method: "POST", body: { email_ids: emailIds, confirm } }),

  // Applications history / reporting
  listApplications: (params = {}) => {
    const qs = new URLSearchParams({ limit: "100", ...params }).toString();
    return request(`/reports/applications${qs ? `?${qs}` : ""}`).then((r) => r.items);
  },
  getApplication: (emailId) => request(`/reports/applications/${emailId}`),
  updatePipeline: (emailId, payload) =>
    request(`/reports/applications/${emailId}/pipeline`, { method: "PATCH", body: payload }),
  addInterview: (emailId, payload) =>
    request(`/reports/applications/${emailId}/interviews`, { method: "POST", body: payload }),
  updateInterview: (interviewId, payload) =>
    request(`/reports/interviews/${interviewId}`, { method: "PATCH", body: payload }),
  getReportsSummary: () => request("/reports/summary"),

  // Candidate invites (admin inviting a candidate into their own org)
  inviteCandidate: (email) => request("/candidates/invite", { method: "POST", body: { email } }),

  // Staff auth + org onboarding
  staffLogin: (username, password) =>
    request("/staff-auth/login", { method: "POST", form: { username, password } }),
  inviteOrganization: (payload) => request("/staff/invite-organization", { method: "POST", body: payload }),
  listMyOrganizations: () => request("/staff/organizations"),
  deactivateOrganization: (organizationId) =>
    request(`/staff/organizations/${organizationId}`, { method: "DELETE" }),
  extendMyOrganizationTrial: (organizationId, additionalDays) =>
    request(`/staff/organizations/${organizationId}/trial`, { method: "PUT", body: { additional_days: additionalDays } }),
  getStaffTrialDefault: () => request("/staff/trial-default"),

  // Superuser invites staff (OTP-based, same as every other invite -- see redeemInvite)
  inviteStaff: (email) => request("/superuser/staff/invite", { method: "POST", body: { email } }),
  getStaffPerformance: () => request("/superuser/staff/performance"),
  listPendingInvites: () => request("/superuser/invites/pending"),
  getPlatformSettings: () => request("/superuser/settings"),
  updatePlatformSettings: (payload) => request("/superuser/settings", { method: "PUT", body: payload }),
  listStatuses: () => request("/superuser/statuses"),
  extendOrganizationTrial: (organizationId, additionalDays) =>
    request(`/superuser/organizations/${organizationId}/trial`, { method: "PUT", body: { additional_days: additionalDays } }),
  changeOrganizationStatus: (organizationId, statusCode) =>
    request(`/superuser/organizations/${organizationId}/status`, { method: "PUT", body: { status_code: statusCode } }),
  extendCandidateTrial: (candidateId, additionalDays) =>
    request(`/superuser/candidates/${candidateId}/trial`, { method: "PUT", body: { additional_days: additionalDays } }),
  changeCandidateStatus: (candidateId, statusCode) =>
    request(`/superuser/candidates/${candidateId}/status`, { method: "PUT", body: { status_code: statusCode } }),
  listAllCandidatesPlatformWide: () => request("/superuser/candidates"),

  // Generic OTP invite redemption -- used by staff, admin, and candidate
  // invites alike; the invite's own role/organization decide what's
  // created, never what the registrant supplies (see api/routers/invite.py)
  redeemInvite: (payload) => request("/invite/register", { method: "POST", body: payload }),

  // Superuser onboards an organization (or standalone individual/candidate) directly
  createOrganization: (payload) => request("/superuser/organizations", { method: "POST", body: payload }),
  runTrialReminders: () => request("/superuser/trial-reminders/run", { method: "POST" }),

  // Superuser
  superuserLogin: (username, password) =>
    request("/superuser-auth/login", { method: "POST", form: { username, password } }),
  getPlatformSummary: () => request("/superuser/reports/summary"),

  // Organization settings
  getOrgSettings: () => request("/organization/settings"),
  updateOrgSettings: (payload) => request("/organization/settings", { method: "PUT", body: payload }),

  // Resume/document artifact review (admin)
  listPendingDocuments: () => request("/candidates/documents"),
  decideDocument: (docId, decision) =>
    request(`/candidates/documents/${docId}/decision`, { method: "POST", body: decision }),
  listPendingResumeApprovals: () => request("/candidates/resume-approvals"),
  decideResumeApproval: (runId, decision) =>
    request(`/candidates/resume-approvals/${runId}/decision`, { method: "POST", body: decision }),

  // Push notifications
  getVapidPublicKey: () => request("/push/vapid-public-key"),
  subscribePushAdmin: (payload) => request("/push/subscribe/admin", { method: "POST", body: payload }),
  subscribePushCandidate: (payload) => request("/push/subscribe/candidate", { method: "POST", body: payload }),
  unsubscribePush: (payload) => request("/push/unsubscribe", { method: "POST", body: payload }),
};

export { ApiError };
