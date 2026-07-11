import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockUseAuth = vi.fn();

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../api/client.js", () => ({
  api: {
    getOrgSettings: vi.fn(),
    getMySubscription: vi.fn(),
  },
}));

import { api } from "../api/client.js";
import TrialBanner from "./TrialBanner.jsx";

describe("TrialBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("shows the banner for an admin whose org trial expires within 7 days", async () => {
    mockUseAuth.mockReturnValue({ role: "admin" });
    api.getOrgSettings.mockResolvedValue({ trial_expires_at: "2026-07-10", trial_days_remaining: 3, trial_banner_window_days: 7 });

    render(<TrialBanner />);

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    expect(screen.getByText(/expires on/i)).toBeInTheDocument();
    expect(screen.getByText(/3 days left/i)).toBeInTheDocument();
  });

  it("shows the banner for a candidate using getMySubscription instead of getOrgSettings", async () => {
    mockUseAuth.mockReturnValue({ role: "candidate" });
    api.getMySubscription.mockResolvedValue({ trial_expires_at: "2026-07-08", trial_days_remaining: 1, trial_banner_window_days: 7 });

    render(<TrialBanner />);

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    expect(api.getMySubscription).toHaveBeenCalled();
    expect(api.getOrgSettings).not.toHaveBeenCalled();
  });

  it("does not show anything when trial_days_remaining is more than 7 days out", async () => {
    mockUseAuth.mockReturnValue({ role: "admin" });
    api.getOrgSettings.mockResolvedValue({ trial_expires_at: "2026-08-01", trial_days_remaining: 25, trial_banner_window_days: 7 });

    render(<TrialBanner />);

    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not show anything when there is no trial expiry set at all", async () => {
    mockUseAuth.mockReturnValue({ role: "admin" });
    api.getOrgSettings.mockResolvedValue({ trial_expires_at: null, trial_days_remaining: null });

    render(<TrialBanner />);

    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not fetch anything for staff or superuser roles", async () => {
    mockUseAuth.mockReturnValue({ role: "staff" });
    render(<TrialBanner />);

    await new Promise((r) => setTimeout(r, 50));
    expect(api.getOrgSettings).not.toHaveBeenCalled();
    expect(api.getMySubscription).not.toHaveBeenCalled();
  });

  it("shows an already-expired message when days remaining is negative", async () => {
    mockUseAuth.mockReturnValue({ role: "admin" });
    api.getOrgSettings.mockResolvedValue({ trial_expires_at: "2026-07-01", trial_days_remaining: -2, trial_banner_window_days: 7 });

    render(<TrialBanner />);

    await waitFor(() => expect(screen.getByText(/expired on/i)).toBeInTheDocument());
  });

  it("can be dismissed manually before the auto-dismiss timer fires", async () => {
    mockUseAuth.mockReturnValue({ role: "admin" });
    api.getOrgSettings.mockResolvedValue({ trial_expires_at: "2026-07-10", trial_days_remaining: 3, trial_banner_window_days: 7 });
    const user = userEvent.setup();

    render(<TrialBanner />);

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("only fetches once per session -- does not re-show on a second mount without a logout", async () => {
    mockUseAuth.mockReturnValue({ role: "admin" });
    api.getOrgSettings.mockResolvedValue({ trial_expires_at: "2026-07-10", trial_days_remaining: 3, trial_banner_window_days: 7 });

    const { unmount } = render(<TrialBanner />);
    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    unmount();

    render(<TrialBanner />);
    await new Promise((r) => setTimeout(r, 50));
    expect(api.getOrgSettings).toHaveBeenCalledTimes(1);
  });
});
