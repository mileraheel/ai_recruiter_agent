import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("../api/client.js", () => ({
  api: { redeemInvite: vi.fn() },
  decodeJwtRole: vi.fn(),
}));

const mockLoginWithToken = vi.fn();
vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: () => ({ loginWithToken: mockLoginWithToken }),
}));

import { api, decodeJwtRole } from "../api/client.js";
import AcceptInvite from "./AcceptInvite.jsx";

function renderPage() {
  return render(
    <MemoryRouter>
      <AcceptInvite />
    </MemoryRouter>
  );
}

describe("AcceptInvite", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits email, otp, password, and the optional username/full_name fields", async () => {
    api.redeemInvite.mockResolvedValue({ access_token: "tok-staff-1" });
    decodeJwtRole.mockReturnValue("staff");
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "staffer@example.com");
    await user.type(screen.getByLabelText("Invite code"), "123456");
    await user.type(screen.getByLabelText(/choose a password/i), "MyChosenPassword1");
    await user.type(screen.getByLabelText(/username/i), "staffer_chosen");
    await user.click(screen.getByRole("button", { name: /set password/i }));

    await waitFor(() =>
      expect(api.redeemInvite).toHaveBeenCalledWith({
        email: "staffer@example.com",
        otp: "123456",
        password: "MyChosenPassword1",
        username: "staffer_chosen",
        full_name: undefined,
      })
    );
  });

  it("logs in and navigates to the staff dashboard when the redeemed invite's role is staff", async () => {
    api.redeemInvite.mockResolvedValue({ access_token: "tok-staff-1" });
    decodeJwtRole.mockReturnValue("staff");
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "staffer@example.com");
    await user.type(screen.getByLabelText("Invite code"), "123456");
    await user.type(screen.getByLabelText(/choose a password/i), "MyChosenPassword1");
    await user.type(screen.getByLabelText(/username/i), "staffer_chosen");
    await user.click(screen.getByRole("button", { name: /set password/i }));

    await waitFor(() => expect(mockLoginWithToken).toHaveBeenCalledWith("tok-staff-1", "staff"));
    expect(mockNavigate).toHaveBeenCalledWith("/staff/dashboard");
  });

  it("navigates to the candidate profile when the redeemed invite's role is candidate", async () => {
    api.redeemInvite.mockResolvedValue({ access_token: "tok-cand-1" });
    decodeJwtRole.mockReturnValue("candidate");
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "cand@example.com");
    await user.type(screen.getByLabelText("Invite code"), "654321");
    await user.type(screen.getByLabelText(/choose a password/i), "MyChosenPassword1");
    await user.type(screen.getByLabelText(/full name/i), "Jane Candidate");
    await user.click(screen.getByRole("button", { name: /set password/i }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/candidate/profile"));
  });

  it("shows the server error message on a wrong OTP", async () => {
    api.redeemInvite.mockRejectedValue({ detail: "Incorrect code. 4 attempts remaining." });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "x@example.com");
    await user.type(screen.getByLabelText("Invite code"), "000000");
    await user.type(screen.getByLabelText(/choose a password/i), "MyChosenPassword1");
    await user.click(screen.getByRole("button", { name: /set password/i }));

    await waitFor(() =>
      expect(screen.getByText("Incorrect code. 4 attempts remaining.")).toBeInTheDocument()
    );
    expect(mockLoginWithToken).not.toHaveBeenCalled();
  });
});
