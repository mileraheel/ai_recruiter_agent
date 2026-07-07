import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client.js", () => ({
  api: {
    listApplications: vi.fn(),
    getReportsSummary: vi.fn(),
    getApplication: vi.fn(),
    updatePipeline: vi.fn(),
    addInterview: vi.fn(),
  },
}));

import { api } from "../api/client.js";
import Applications from "./Applications.jsx";

const SAMPLE_APP = {
  email_id: 1,
  candidate_slug: "john_smith",
  candidate_full_name: "John Smith",
  job_id: 7,
  job_title: "Java Architect",
  company_name: "BigCo",
  to_email: "recruiter@bigco.com",
  send_status: "sent",
  pipeline_stage: "interviewing",
  submitted_to_client_at: null,
  interview_count: 2,
  latest_interview_at: null,
  sent_at: "2026-07-01T10:00:00Z",
  created_at: "2026-07-01T09:00:00Z",
};

describe("Applications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getReportsSummary.mockResolvedValue(null);
  });

  it("renders an application row with candidate, role, and stage", async () => {
    api.listApplications.mockResolvedValue([SAMPLE_APP]);
    render(<Applications />);

    await waitFor(() => expect(screen.getByText("John Smith")).toBeInTheDocument());
    expect(screen.getByText("Java Architect")).toBeInTheDocument();
    expect(screen.getByText("BigCo")).toBeInTheDocument();
    expect(screen.getByText("Interviewing")).toBeInTheDocument();
  });

  it("shows the empty state when there are no applications", async () => {
    api.listApplications.mockResolvedValue([]);
    render(<Applications />);

    await waitFor(() => expect(screen.getByText(/post a job to get started/i)).toBeInTheDocument());
  });

  it("expands a row to load and show its detail on click", async () => {
    api.listApplications.mockResolvedValue([SAMPLE_APP]);
    api.getApplication.mockResolvedValue({
      ...SAMPLE_APP,
      subject: "Application to BigCo",
      body: "Dear recruiter...",
      resume_file_name: "john_smith.docx",
      pipeline_notes: null,
      interviews: [{ id: 1, round_name: "Phone Screen", status: "completed", scheduled_at: null, notes: null, created_at: "2026-07-01T00:00:00Z" }],
    });
    const user = userEvent.setup();
    render(<Applications />);

    await waitFor(() => expect(screen.getByText("John Smith")).toBeInTheDocument());
    await user.click(screen.getByText("John Smith"));

    await waitFor(() => expect(api.getApplication).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.getByText(/Subject: Application to BigCo/)).toBeInTheDocument());
    expect(screen.getByText("Phone Screen")).toBeInTheDocument();
  });

  it("saves an updated pipeline stage from the expanded detail", async () => {
    api.listApplications.mockResolvedValue([SAMPLE_APP]);
    api.getApplication.mockResolvedValue({
      ...SAMPLE_APP,
      subject: "Application to BigCo",
      body: "...",
      resume_file_name: null,
      pipeline_notes: null,
      interviews: [],
    });
    api.updatePipeline.mockResolvedValue({});
    const user = userEvent.setup();
    render(<Applications />);

    await waitFor(() => expect(screen.getByText("John Smith")).toBeInTheDocument());
    await user.click(screen.getByText("John Smith"));
    await waitFor(() => expect(screen.getByText(/None logged yet/)).toBeInTheDocument());

    await user.selectOptions(screen.getByDisplayValue("Interviewing"), "offer");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(api.updatePipeline).toHaveBeenCalledWith(1, { pipeline_stage: "offer", pipeline_notes: null })
    );
  });

  it("filters applications by candidate name", async () => {
    api.listApplications.mockResolvedValue([
      SAMPLE_APP,
      { ...SAMPLE_APP, email_id: 2, candidate_full_name: "Jane Doe" },
    ]);
    const user = userEvent.setup();
    render(<Applications />);

    await waitFor(() => expect(screen.getByText("Jane Doe")).toBeInTheDocument());
    await user.type(screen.getByLabelText("Filter Candidate"), "Jane");

    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.queryByText("John Smith")).not.toBeInTheDocument();
  });

  it("shows the summary stat cards when available", async () => {
    api.listApplications.mockResolvedValue([]);
    api.getReportsSummary.mockResolvedValue({
      total_prepared: 5,
      total_sent: 4,
      total_client_submitted: 2,
      total_interviewing: 1,
      total_offers: 0,
      total_rejected: 1,
      by_candidate: {},
    });
    render(<Applications />);

    await waitFor(() => expect(screen.getByText("Prepared")).toBeInTheDocument());
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
