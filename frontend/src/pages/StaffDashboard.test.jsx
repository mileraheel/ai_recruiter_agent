import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client.js", () => ({
  api: {
    listMyOrganizations: vi.fn(),
    inviteOrganization: vi.fn(),
    deactivateOrganization: vi.fn(),
  },
}));

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

import { api } from "../api/client.js";
import StaffDashboard from "./StaffDashboard.jsx";

const SAMPLE_ORG = {
  organization_id: 7,
  organization_name: "Acme Staffing",
  account_type: "agency",
  is_active: true,
  candidate_count: 3,
  admin_count: 1,
  jobs_posted: 12,
  created_at: "2026-01-01T00:00:00Z",
};

describe("StaffDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

  it("lists organizations this staff member has onboarded", async () => {
    api.listMyOrganizations.mockResolvedValue([SAMPLE_ORG]);
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows an empty state when no organizations have been onboarded yet", async () => {
    api.listMyOrganizations.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText(/no organizations onboarded yet/i)).toBeInTheDocument());
  });

  it("submits the onboarding form with organization name, admin email, account type, and default trial_days", async () => {
    api.listMyOrganizations.mockResolvedValue([]);
    api.inviteOrganization.mockResolvedValue({
      organization_id: 8,
      organization_name: "Beta Corp",
      invited_email: "admin@beta.com",
      trial_expires_at: "2026-07-21",
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText(/no organizations onboarded yet/i)).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Organization name"), "Beta Corp");
    await user.type(screen.getByPlaceholderText("First admin's email"), "admin@beta.com");
    await user.click(screen.getByRole("button", { name: /create organization/i }));

    await waitFor(() =>
      expect(api.inviteOrganization).toHaveBeenCalledWith({
        organization_name: "Beta Corp",
        admin_email: "admin@beta.com",
        account_type: "agency",
        trial_days: 14,
      })
    );
    await waitFor(() =>
      expect(screen.getByText(/'Beta Corp' created — invite sent to admin@beta\.com/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/Trial expires 2026-07-21/i)).toBeInTheDocument();
  });

  it("sends trial_days: null when the trial-days field is cleared (no expiry)", async () => {
    api.listMyOrganizations.mockResolvedValue([]);
    api.inviteOrganization.mockResolvedValue({
      organization_id: 9,
      organization_name: "Gamma LLC",
      invited_email: "admin@gamma.com",
      trial_expires_at: null,
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText(/no organizations onboarded yet/i)).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Organization name"), "Gamma LLC");
    await user.type(screen.getByPlaceholderText("First admin's email"), "admin@gamma.com");
    await user.clear(screen.getByPlaceholderText("e.g. 14"));
    await user.click(screen.getByRole("button", { name: /create organization/i }));

    await waitFor(() =>
      expect(api.inviteOrganization).toHaveBeenCalledWith({
        organization_name: "Gamma LLC",
        admin_email: "admin@gamma.com",
        account_type: "agency",
        trial_days: null,
      })
    );
    expect(screen.getByText(/no trial expiry set/i)).toBeInTheDocument();
  });

  it("shows the trial expiry and days remaining in the organizations table", async () => {
    api.listMyOrganizations.mockResolvedValue([
      { ...SAMPLE_ORG, trial_expires_at: "2026-07-10", trial_days_remaining: 3 },
    ]);
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    expect(screen.getByText("2026-07-10 (3d)")).toBeInTheDocument();
  });

  it("shows the server error when the organization name is already taken", async () => {
    api.listMyOrganizations.mockResolvedValue([]);
    api.inviteOrganization.mockRejectedValue({
      detail: "An organization named 'Beta Corp' already exists.",
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText(/no organizations onboarded yet/i)).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Organization name"), "Beta Corp");
    await user.type(screen.getByPlaceholderText("First admin's email"), "admin@beta.com");
    await user.click(screen.getByRole("button", { name: /create organization/i }));

    await waitFor(() =>
      expect(screen.getByText("An organization named 'Beta Corp' already exists.")).toBeInTheDocument()
    );
  });

  it("deactivates an organization after confirmation", async () => {
    api.listMyOrganizations.mockResolvedValue([SAMPLE_ORG]);
    api.deactivateOrganization.mockResolvedValue({ organization_id: 7, is_active: false });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /deactivate/i }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(api.deactivateOrganization).toHaveBeenCalledWith(7));
  });

  it("does not deactivate when the confirmation is cancelled", async () => {
    window.confirm = vi.fn(() => false);
    api.listMyOrganizations.mockResolvedValue([SAMPLE_ORG]);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StaffDashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /deactivate/i }));

    expect(api.deactivateOrganization).not.toHaveBeenCalled();
  });
});
