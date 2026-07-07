import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "../context/AuthContext.jsx";

vi.mock("../api/client.js", async () => {
  const actual = await vi.importActual("../api/client.js");
  return {
    ...actual,
    api: {
      login: vi.fn(),
      candidateLogin: vi.fn(),
      superuserLogin: vi.fn(),
      staffLogin: vi.fn(),
      candidateSignup: vi.fn(),
    },
  };
});

import { api, getRole, getToken } from "../api/client.js";

function Probe() {
  const { isAuthed, role, loginAdmin, loginCandidate, loginSuperuser, loginStaff, logout } = useAuth();
  return (
    <div>
      <span data-testid="authed">{String(isAuthed)}</span>
      <span data-testid="role">{role || "none"}</span>
      <button onClick={() => loginAdmin("admin1", "pw")}>login-admin</button>
      <button onClick={() => loginCandidate("c@x.com", "pw")}>login-candidate</button>
      <button onClick={() => loginSuperuser("root", "pw")}>login-super</button>
      <button onClick={() => loginStaff("staffer", "pw")}>login-staff</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>
  );
}

describe("AuthContext role handling", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("starts unauthenticated with no role", () => {
    renderProbe();
    expect(screen.getByTestId("authed").textContent).toBe("false");
    expect(screen.getByTestId("role").textContent).toBe("none");
  });

  it("sets role='admin' after a successful admin login, and persists the token", async () => {
    api.login.mockResolvedValue({ access_token: "admin-token-123" });
    const user = userEvent.setup();
    renderProbe();

    await user.click(screen.getByText("login-admin"));

    await waitFor(() => expect(screen.getByTestId("role").textContent).toBe("admin"));
    expect(screen.getByTestId("authed").textContent).toBe("true");
    expect(getRole()).toBe("admin");
    expect(getToken()).toBe("admin-token-123");
  });

  it("sets role='candidate' after a successful candidate login -- distinct from admin", async () => {
    api.candidateLogin.mockResolvedValue({ access_token: "cand-token-456" });
    const user = userEvent.setup();
    renderProbe();

    await user.click(screen.getByText("login-candidate"));

    await waitFor(() => expect(screen.getByTestId("role").textContent).toBe("candidate"));
    expect(getRole()).toBe("candidate");
  });

  it("sets role='superuser' after a successful superuser login", async () => {
    api.superuserLogin.mockResolvedValue({ access_token: "super-token-789" });
    const user = userEvent.setup();
    renderProbe();

    await user.click(screen.getByText("login-super"));

    await waitFor(() => expect(screen.getByTestId("role").textContent).toBe("superuser"));
  });

  it("sets role='staff' after a successful staff login -- distinct from admin/superuser", async () => {
    api.staffLogin.mockResolvedValue({ access_token: "staff-token-321" });
    const user = userEvent.setup();
    renderProbe();

    await user.click(screen.getByText("login-staff"));

    await waitFor(() => expect(screen.getByTestId("role").textContent).toBe("staff"));
    expect(getRole()).toBe("staff");
  });

  it("clears role and token on logout", async () => {
    api.login.mockResolvedValue({ access_token: "admin-token-123" });
    const user = userEvent.setup();
    renderProbe();

    await user.click(screen.getByText("login-admin"));
    await waitFor(() => expect(screen.getByTestId("authed").textContent).toBe("true"));

    await user.click(screen.getByText("logout"));
    expect(screen.getByTestId("authed").textContent).toBe("false");
    expect(getToken()).toBeNull();
    expect(getRole()).toBeNull();
  });

  it("does not authenticate on a failed login", async () => {
    api.login.mockRejectedValue({ detail: "Incorrect username or password" });
    const user = userEvent.setup();
    renderProbe();

    await user.click(screen.getByText("login-admin"));

    await waitFor(() => expect(screen.getByTestId("authed").textContent).toBe("false"));
    expect(getToken()).toBeNull();
  });
});
