import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client.js", () => ({
  api: {
    listCandidates: vi.fn(),
    triggerWatchCycle: vi.fn(),
    inviteCandidate: vi.fn(),
  },
}));

import { api } from "../api/client.js";
import Candidates from "./Candidates.jsx";

const SAMPLE_CANDIDATE = {
  id: 1,
  slug: "john_smith",
  full_name: "John Smith",
  resume_path: "resumes/acme/john_smith.docx",
  resume_exists: true,
  strict_skill_match_required: true,
  pending_skill_count: 0,
  status: "ok",
  status_message: null,
};

describe("Candidates invite form", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listCandidates.mockResolvedValue([SAMPLE_CANDIDATE]);
  });

  it("renders the invite form alongside the existing candidate list", async () => {
    render(<Candidates />);

    await waitFor(() => expect(screen.getByText("John Smith")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("candidate@email.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send invite/i })).toBeInTheDocument();
  });

  it("calls inviteCandidate with the entered email and shows a success message", async () => {
    api.inviteCandidate.mockResolvedValue({ invited_email: "new.candidate@example.com" });
    const user = userEvent.setup();
    render(<Candidates />);

    await waitFor(() => expect(screen.getByText("John Smith")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("candidate@email.com"), "new.candidate@example.com");
    await user.click(screen.getByRole("button", { name: /send invite/i }));

    await waitFor(() => expect(api.inviteCandidate).toHaveBeenCalledWith("new.candidate@example.com"));
    await waitFor(() =>
      expect(screen.getByText(/invite sent to new\.candidate@example\.com/i)).toBeInTheDocument()
    );
    // The field clears after a successful send.
    expect(screen.getByPlaceholderText("candidate@email.com").value).toBe("");
  });

  it("shows the server error message when the invite fails", async () => {
    api.inviteCandidate.mockRejectedValue({ detail: "A candidate with this email already exists." });
    const user = userEvent.setup();
    render(<Candidates />);

    await waitFor(() => expect(screen.getByText("John Smith")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("candidate@email.com"), "dup@example.com");
    await user.click(screen.getByRole("button", { name: /send invite/i }));

    await waitFor(() =>
      expect(screen.getByText("A candidate with this email already exists.")).toBeInTheDocument()
    );
  });

  it("filters the candidate table by name via the DataTable search box", async () => {
    api.listCandidates.mockResolvedValue([
      SAMPLE_CANDIDATE,
      { ...SAMPLE_CANDIDATE, slug: "jane_doe", full_name: "Jane Doe" },
    ]);
    const user = userEvent.setup();
    render(<Candidates />);

    await waitFor(() => expect(screen.getByText("Jane Doe")).toBeInTheDocument());
    await user.type(screen.getByLabelText("Filter Candidate"), "Jane");

    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.queryByText("John Smith")).not.toBeInTheDocument();
  });

  it("sorts the candidate table by resume status when that column header is clicked", async () => {
    api.listCandidates.mockResolvedValue([
      { ...SAMPLE_CANDIDATE, slug: "has_resume", full_name: "Has Resume", resume_exists: true },
      { ...SAMPLE_CANDIDATE, slug: "no_resume", full_name: "No Resume", resume_exists: false },
    ]);
    const user = userEvent.setup();
    render(<Candidates />);

    await waitFor(() => expect(screen.getByText("Has Resume")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Resume" }));

    const rows = screen.getAllByRole("row").slice(2);
    expect(rows[0].textContent).toContain("No Resume"); // resume_exists=false sorts first ascending (0 before 1)
  });
});
