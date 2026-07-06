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

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

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

  if (res.status === 401) {
    const role = getRole();
    clearToken();
    window.location.href = role === "candidate" ? "/candidate/login" : "/login";
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

  // Admin review of candidate profile submissions
  listCandidateSubmissions: () => request("/candidate-review?limit=100").then((r) => r.items),
  decideCandidateSubmission: (submissionId, decision) =>
    request(`/candidate-review/${submissionId}/decision`, { method: "POST", body: decision }),

  // Gmail connection
  getEmailAccountStatus: () => request("/me/email-account"),
  getEmailConnectUrl: () => request("/me/email-account/connect-url"),
  disconnectEmailAccount: () => request("/me/email-account", { method: "DELETE" }),

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
