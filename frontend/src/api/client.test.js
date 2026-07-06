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
});
