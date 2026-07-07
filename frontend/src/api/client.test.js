import { describe, it, expect, beforeEach, vi } from "vitest";

describe("api client", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("unwraps the paginated envelope for listCandidates", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [{ slug: "a" }, { slug: "b" }], total: 2, limit: 100, offset: 0 }),
    });

    const result = await api.listCandidates();
    expect(result).toEqual([{ slug: "a" }, { slug: "b" }]);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/candidates?limit=100"),
      expect.any(Object)
    );
  });

  it("throws ApiError with the server-provided detail on failure", async () => {
    const { api, setToken, ApiError } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Something specific went wrong" }),
    });

    await expect(api.checkJob({ candidate_slug: "x", job_description_text: "y" })).rejects.toMatchObject({
      status: 422,
      detail: "Something specific went wrong",
    });
  });

  it("clears the token and redirects to the role-appropriate login on 401", async () => {
    const { api, setToken, setRole } = await import("../api/client.js");
    setToken("fake-token");
    setRole("candidate");

    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });

    delete window.location;
    window.location = { href: "" };

    await expect(api.getMe()).rejects.toThrow();
    expect(localStorage.getItem("ai_recruiter_token")).toBeNull();
    expect(window.location.href).toBe("/candidate/login");
  });

  it("redirects admins to /login (not /candidate/login) on 401", async () => {
    const { api, setToken, setRole } = await import("../api/client.js");
    setToken("fake-token");
    setRole("admin");

    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });

    delete window.location;
    window.location = { href: "" };

    await expect(api.listCandidates()).rejects.toThrow();
    expect(window.location.href).toBe("/login");
  });

  it("does NOT redirect on a 401 from the login endpoint itself (wrong credentials, not an expired session)", async () => {
    const { api } = await import("../api/client.js");

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Invalid username or password" }),
    });

    delete window.location;
    window.location = { href: "" };

    await expect(api.login("wrong", "wrong")).rejects.toMatchObject({
      status: 401,
      detail: "Invalid username or password",
    });
    // The bug: this used to be set to "/login" even though the user was
    // already on the login page, wiping the form via a full reload
    // before the error banner could ever render.
    expect(window.location.href).toBe("");
  });

  it("does NOT redirect on a 401 from the superuser login endpoint", async () => {
    const { api } = await import("../api/client.js");

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Invalid username or password" }),
    });

    delete window.location;
    window.location = { href: "" };

    await expect(api.superuserLogin("raheel", "wrong")).rejects.toMatchObject({ status: 401 });
    expect(window.location.href).toBe("");
  });

  it("does NOT redirect on a 401 from the staff login endpoint either", async () => {
    const { api } = await import("../api/client.js");

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Incorrect username or password" }),
    });

    delete window.location;
    window.location = { href: "" };

    await expect(api.staffLogin("staffer", "wrong")).rejects.toMatchObject({ status: 401 });
    expect(window.location.href).toBe("");
  });

  it("inviteCandidate posts to /api/candidates/invite with the email", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ invited_email: "c@example.com" }),
    });

    const result = await api.inviteCandidate("c@example.com");
    expect(result).toEqual({ invited_email: "c@example.com" });
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/candidates/invite");
    expect(JSON.parse(options.body)).toEqual({ email: "c@example.com" });
  });

  it("inviteOrganization posts organization_name/admin_email/account_type", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ organization_id: 1, organization_name: "Acme", invited_email: "a@acme.com" }),
    });

    await api.inviteOrganization({
      organization_name: "Acme",
      admin_email: "a@acme.com",
      account_type: "agency",
    });
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/staff/invite-organization");
    expect(JSON.parse(options.body)).toEqual({
      organization_name: "Acme",
      admin_email: "a@acme.com",
      account_type: "agency",
    });
  });

  it("inviteStaff posts email to /api/superuser/staff/invite", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ invited_email: "staffer@example.com", expires_at: "2026-07-14T00:00:00Z" }),
    });

    await api.inviteStaff("staffer@example.com");
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/superuser/staff/invite");
    expect(JSON.parse(options.body)).toEqual({ email: "staffer@example.com" });
  });

  it("listPendingInvites fetches /api/superuser/invites/pending", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] });

    await api.listPendingInvites();
    expect(global.fetch.mock.calls[0][0]).toContain("/api/superuser/invites/pending");
  });

  it("getPlatformSettings and updatePlatformSettings hit /api/superuser/settings", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ invite_expire_days: 7 }),
    });
    await api.getPlatformSettings();
    expect(global.fetch.mock.calls[0][0]).toContain("/api/superuser/settings");
    expect(global.fetch.mock.calls[0][1].method).toBe("GET");

    await api.updatePlatformSettings({ invite_expire_days: 10 });
    const [url, options] = global.fetch.mock.calls[1];
    expect(url).toContain("/api/superuser/settings");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body)).toEqual({ invite_expire_days: 10 });
  });

  it("redeemInvite posts to /api/invite/register and does NOT redirect on a wrong-OTP 401", async () => {
    const { api } = await import("../api/client.js");

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Incorrect code. 4 attempts remaining." }),
    });
    delete window.location;
    window.location = { href: "" };

    await expect(
      api.redeemInvite({ email: "x@example.com", otp: "000000", password: "SomePassword1" })
    ).rejects.toMatchObject({ status: 401 });
    expect(window.location.href).toBe("");
    expect(global.fetch.mock.calls[0][0]).toContain("/api/invite/register");
  });

  it("createOrganization posts to /api/superuser/organizations with trial_days", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ organization_id: 1, organization_name: "Acme", invited_email: "a@acme.com", trial_expires_at: "2026-07-21" }),
    });

    await api.createOrganization({
      organization_name: "Acme",
      admin_email: "a@acme.com",
      account_type: "individual",
      trial_days: 14,
    });
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/superuser/organizations");
    expect(JSON.parse(options.body)).toEqual({
      organization_name: "Acme",
      admin_email: "a@acme.com",
      account_type: "individual",
      trial_days: 14,
    });
  });

  it("runTrialReminders posts to /api/superuser/trial-reminders/run", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ organizations_reminded: 1, organizations_failed: 0, candidates_reminded: 0, candidates_failed: 0 }),
    });

    const result = await api.runTrialReminders();
    expect(result.organizations_reminded).toBe(1);
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/superuser/trial-reminders/run");
    expect(options.method).toBe("POST");
  });

  it("getMySubscription fetches /api/me/subscription", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "active", trial_days_remaining: 3, trial_expires_at: "2026-07-10" }),
    });

    const result = await api.getMySubscription();
    expect(result.trial_days_remaining).toBe(3);
    expect(global.fetch.mock.calls[0][0]).toContain("/api/me/subscription");
  });

  it("listMyApplications fetches /api/me/applications and returns items array", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [{ email_id: 1 }], total: 1, limit: 100, offset: 0 }),
    });

    const result = await api.listMyApplications();
    expect(result).toEqual([{ email_id: 1 }]);
    expect(global.fetch.mock.calls[0][0]).toContain("/api/me/applications");
  });

  it("listMyUpcomingInterviews fetches /api/me/interviews/upcoming", async () => {
    const { api, setToken } = await import("../api/client.js");
    setToken("fake-token");

    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] });

    await api.listMyUpcomingInterviews();
    expect(global.fetch.mock.calls[0][0]).toContain("/api/me/interviews/upcoming");
  });
});
