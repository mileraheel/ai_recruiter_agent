import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client.js", () => ({
  api: {
    getPlatformSummary: vi.fn(),
    getStaffPerformance: vi.fn(),
    listPendingInvites: vi.fn(),
    getPlatformSettings: vi.fn(),
    updatePlatformSettings: vi.fn(),
    inviteStaff: vi.fn(),
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

function setDefaultMocks() {
  api.getPlatformSummary.mockResolvedValue(SAMPLE_SUMMARY);
  api.getStaffPerformance.mockResolvedValue([]);
  api.listPendingInvites.mockResolvedValue([]);
  api.getPlatformSettings.mockResolvedValue({ invite_expire_days: 7 });
}

describe("SuperuserDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDefaultMocks();
  });

  it("shows the Manage tab by default and does NOT fetch reports data on initial load", async () => {
    render(<SuperuserDashboard />);

    expect(screen.getByText("Onboard an organization directly")).toBeInTheDocument();
    await waitFor(() => expect(api.getPlatformSettings).toHaveBeenCalled()); // the one cheap mount-time fetch
    expect(api.getPlatformSummary).not.toHaveBeenCalled();
    expect(api.getStaffPerformance).not.toHaveBeenCalled();
    expect(api.listPendingInvites).not.toHaveBeenCalled();
  });

  it("only fetches reports data when the Reports tab is clicked", async () => {
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    await user.click(screen.getByRole("button", { name: "Reports" }));

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    expect(api.getPlatformSummary).toHaveBeenCalledTimes(1);
    expect(api.getStaffPerformance).toHaveBeenCalledTimes(1);
  });

  it("does not re-fetch when switching back to Reports a second time -- only Refresh does", async () => {
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    await user.click(screen.getByRole("button", { name: "Reports" }));
    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Manage" }));
    await user.click(screen.getByRole("button", { name: "Reports" }));

    expect(api.getPlatformSummary).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(api.getPlatformSummary).toHaveBeenCalledTimes(2));
  });

  it("shows sales_person attribution and trial info in the sortable organizations table", async () => {
    const user = userEvent.setup();
    render(<SuperuserDashboard />);
    await user.click(screen.getByRole("button", { name: "Reports" }));

    await waitFor(() => expect(screen.getByText("Acme Staffing")).toBeInTheDocument());
    expect(screen.getByText("staffer1")).toBeInTheDocument();
    expect(screen.getByText("2026-07-10 (3d)")).toBeInTheDocument();
  });

  it("filters the organizations table by a column search", async () => {
    api.getPlatformSummary.mockResolvedValue({
      ...SAMPLE_SUMMARY,
      organizations: [
        SAMPLE_SUMMARY.organizations[0],
        { ...SAMPLE_SUMMARY.organizations[0], organization_id: 2, organization_name: "Beta Corp", sales_person: "staffer2" },
      ],
    });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);
    await user.click(screen.getByRole("button", { name: "Reports" }));

    await waitFor(() => expect(screen.getByText("Beta Corp")).toBeInTheDocument());
    const orgHeading = screen.getByRole("heading", { name: "Organizations" });
    const orgTable = orgHeading.parentElement.querySelector("table");
    await user.type(within(orgTable).getByLabelText("Filter Organization"), "Acme");

    expect(screen.getByText("Acme Staffing")).toBeInTheDocument();
    expect(screen.queryByText("Beta Corp")).not.toBeInTheDocument();
  });

  it("sorts the organizations table when a column header is clicked", async () => {
    api.getPlatformSummary.mockResolvedValue({
      ...SAMPLE_SUMMARY,
      organizations: [
        { ...SAMPLE_SUMMARY.organizations[0], organization_id: 1, organization_name: "Zebra Corp" },
        { ...SAMPLE_SUMMARY.organizations[0], organization_id: 2, organization_name: "Acme Corp" },
      ],
    });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);
    await user.click(screen.getByRole("button", { name: "Reports" }));
    await waitFor(() => expect(screen.getByText("Zebra Corp")).toBeInTheDocument());

    const orgHeading = screen.getByRole("heading", { name: "Organizations" });
    const orgTable = orgHeading.parentElement.querySelector("table");
    await user.click(within(orgTable).getByRole("button", { name: /^Organization/ }));

    const cells = within(orgTable)
      .getAllByRole("row")
      .map((r) => r.textContent);
    const zebraIdx = cells.findIndex((c) => c.includes("Zebra Corp"));
    const acmeIdx = cells.findIndex((c) => c.includes("Acme Corp"));
    expect(acmeIdx).toBeLessThan(zebraIdx);
  });

  it("invites a staff member by email only -- no username/password fields", async () => {
    api.inviteStaff.mockResolvedValue({ invited_email: "newstaffer@example.com", expires_at: "2026-07-14T00:00:00Z" });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    expect(screen.queryByPlaceholderText(/username/i)).not.toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Email address"), "newstaffer@example.com");
    await user.click(screen.getByRole("button", { name: "Send invite" }));

    await waitFor(() => expect(api.inviteStaff).toHaveBeenCalledWith("newstaffer@example.com"));
    await waitFor(() => expect(screen.getByText(/invite sent to newstaffer@example\.com/i)).toBeInTheDocument());
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

    await user.type(screen.getByPlaceholderText("Organization name"), "Acme Staffing");
    await user.type(screen.getByPlaceholderText("Admin/candidate email"), "x@acme.com");
    await user.click(screen.getByRole("button", { name: /create & send invite/i }));

    await waitFor(() =>
      expect(screen.getByText("An organization named 'Acme Staffing' already exists.")).toBeInTheDocument()
    );
  });

  it("saves updated invite-expiry platform settings", async () => {
    api.updatePlatformSettings.mockResolvedValue({ invite_expire_days: 10 });
    const user = userEvent.setup();
    render(<SuperuserDashboard />);

    await waitFor(() => expect(api.getPlatformSettings).toHaveBeenCalled());
    const daysInput = await screen.findByDisplayValue("7");
    await user.clear(daysInput);
    await user.type(daysInput, "10");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(api.updatePlatformSettings).toHaveBeenCalledWith({ invite_expire_days: 10 }));
    await waitFor(() => expect(screen.getByText(/new invites will use this expiry/i)).toBeInTheDocument());
  });

  it("shows pending invites in the reports tab", async () => {
    api.listPendingInvites.mockResolvedValue([
      {
        id: 1,
        email: "pending@example.com",
        role: "staff",
        organization_name: null,
        invited_by_type: "superuser",
        expires_at: "2026-07-14T00:00:00Z",
        used_at: null,
        attempts: 0,
        max_attempts: 5,
      },
    ]);
    const user = userEvent.setup();
    render(<SuperuserDashboard />);
    await user.click(screen.getByRole("button", { name: "Reports" }));

    await waitFor(() => expect(screen.getByText("pending@example.com")).toBeInTheDocument());
    expect(screen.getByText("staff")).toBeInTheDocument();
  });
});
