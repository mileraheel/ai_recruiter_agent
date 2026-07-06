import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client.js", () => ({
  api: {
    listApprovalQueue: vi.fn(),
    decideApproval: vi.fn(),
    getOrgSettings: vi.fn().mockResolvedValue({ account_type: "agency" }),
  },
}));

import { api } from "../api/client.js";
import ApprovalQueue from "./ApprovalQueue.jsx";

const SAMPLE_ITEM = {
  id: 42,
  candidate_id: 1,
  skill_name: "Terraform",
  tier: "secondary",
  source_bullet: "Supported DevOps team with Terraform configs",
  source_project_or_role: "Mashreq Bank",
  suggested_by: "claude_extraction",
  confidence: 0.8,
  status: "pending",
};

describe("ApprovalQueue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders pending items with their skill name and source context", async () => {
    api.listApprovalQueue.mockResolvedValue([SAMPLE_ITEM]);
    render(<ApprovalQueue />);

    await waitFor(() => expect(screen.getByText("Terraform")).toBeInTheDocument());
    expect(screen.getByText("Mashreq Bank")).toBeInTheDocument();
  });

  it("shows an empty state when nothing is pending", async () => {
    api.listApprovalQueue.mockResolvedValue([]);
    render(<ApprovalQueue />);

    await waitFor(() => expect(screen.getByText(/nothing pending/i)).toBeInTheDocument());
  });

  it("calls decideApproval with 'approve' and removes the item from the list", async () => {
    api.listApprovalQueue.mockResolvedValue([SAMPLE_ITEM]);
    api.decideApproval.mockResolvedValue({});
    const user = userEvent.setup();
    render(<ApprovalQueue />);

    await waitFor(() => expect(screen.getByText("Terraform")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => {
      expect(api.decideApproval).toHaveBeenCalledWith(
        42,
        expect.objectContaining({ decision: "approve" })
      );
    });
    await waitFor(() => expect(screen.queryByText("Terraform")).not.toBeInTheDocument());
  });

  it("calls decideApproval with 'reject' when rejected", async () => {
    api.listApprovalQueue.mockResolvedValue([SAMPLE_ITEM]);
    api.decideApproval.mockResolvedValue({});
    const user = userEvent.setup();
    render(<ApprovalQueue />);

    await waitFor(() => expect(screen.getByText("Terraform")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /reject/i }));

    await waitFor(() => {
      expect(api.decideApproval).toHaveBeenCalledWith(
        42,
        expect.objectContaining({ decision: "reject" })
      );
    });
  });
});
