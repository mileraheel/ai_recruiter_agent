import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../api/client.js", () => ({
  api: { getOrgSettings: vi.fn() },
}));

import { api } from "../api/client.js";
import SelfApprovalDisclaimer from "./SelfApprovalDisclaimer.jsx";

describe("SelfApprovalDisclaimer", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the warning for an individual account", async () => {
    api.getOrgSettings.mockResolvedValue({ account_type: "individual" });
    render(<SelfApprovalDisclaimer />);
    await waitFor(() => expect(screen.getByText(/you're approving your own submission/i)).toBeInTheDocument());
  });

  it("renders nothing for a regular agency account", async () => {
    api.getOrgSettings.mockResolvedValue({ account_type: "agency" });
    const { container } = render(<SelfApprovalDisclaimer />);
    await waitFor(() => expect(api.getOrgSettings).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
