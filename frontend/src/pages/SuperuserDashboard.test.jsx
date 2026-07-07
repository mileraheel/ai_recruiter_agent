import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client.js", () => ({
  api: {
    getPlatformSummary: vi.fn(),
    getStaffPerformance: vi.fn(),
    createStaff: vi.fn(),
    createOrganization: vi.fn(),
  },
}));

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

import { api } from "../api/client.js";
import SuperuserDashboard from "./SuperuserDashboard.jsx";

const SAMPLE_SUMMARY = {
  organization_count: 1,
  total_candidates: 2,
  total_jobs_posted: 3,
  total_applications_sent: 4,
  total_interviews: 1,
  organizations: [
    {
      organization_id: 1,
      organization_name: "Acme Staffing",
      candidate_count: 2,
      admin_count: 1,
      jobs_posted: 3,
      applications_sent: 4,
      interviews_scheduled: 1,
      created_at: "2026-01-01T00:00:00Z",
      sales_person: "staffer1",
      trial_expires_at: "2026-07-10",
      trial_days_remaining: 3,
    },
  ],
};

describe("SuperuserDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getPlatformSummary.mockResolvedValue(SAMPLE_SUMMARY);
    api.getStaffPerformance.mockResolvedValue([]);
  });

  it("shows sales_person attribution and trial info in the organizations table", async () => {
    render(<SuperuserDashboard />);

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    expect(screen.getByText("staffer1")).toBeInTheDocument();
    expect(screen.getByText("2026-07-10 (3d)")).toBeInTheDocument();
  });

  it("creates an organization directly, attributing the superuser as sales person", async () => {
    api.createOrganization.mockResolvedValue({
      organization_id: 5,
      organization_name: "Solo Jane",
      invited_email: "jane@example.com",
      trial_expires_at: "2026-08-06",
    });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Organization name"), "Solo Jane");
    await user.type(screen.getByPlaceholderText("Admin/candidate email"), "jane@example.com");
    await user.selectOptions(screen.getByDisplayValue("Agency"), "individual");
    await user.click(screen.getByRole("button", { name: /create & send invite/i }));

    await waitFor(() =>
      expect(api.createOrganization).toHaveBeenCalledWith({
        organization_name: "Solo Jane",
        admin_email: "jane@example.com",
        account_type: "individual",
        trial_days: 14,
      })
    );
    await waitFor(() =>
      expect(screen.getByText(/'Solo Jane' created — invite sent to jane@example\.com/i)).toBeInTheDocument()
    );
  });

  it("shows an error when creating an organization with a duplicate name", async () => {
    api.createOrganization.mockRejectedValue({ detail: "An organization named 'Acme Staffing' already exists." });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Organization name"), "Acme Staffing");
    await user.type(screen.getByPlaceholderText("Admin/candidate email"), "x@acme.com");
    await user.click(screen.getByRole("button", { name: /create & send invite/i }));

    await waitFor(() =>
      expect(screen.getByText("An organization named 'Acme Staffing' already exists.")).toBeInTheDocument()
    );
  });

  it("creates a staff account", async () => {
    api.createStaff.mockResolvedValue({ id: 1, username: "newstaffer", is_active: true });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Username"), "newstaffer");
    await user.type(screen.getByPlaceholderText(/10\+ characters/i), "SuperSecret123");
    await user.click(screen.getByRole("button", { name: /create staff account/i }));

    await waitFor(() =>
      expect(api.createStaff).toHaveBeenCalledWith("newstaffer", "SuperSecret123")
    );
    await waitFor(() => expect(screen.getByText(/'newstaffer' created/i)).toBeInTheDocument());
  });
});
