import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client.js", () => ({
  api: {
    listMyApplications: vi.fn(),
    listMyUpcomingInterviews: vi.fn(),
    getMyApplication: vi.fn(),
    getOrgSettings: vi.fn(),
    getMySubscription: vi.fn().mockResolvedValue({ trial_days_remaining: null, trial_expires_at: null }),
  },
}));

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: () => ({ logout: vi.fn(), role: "candidate" }),
}));

import { api } from "../api/client.js";
import MyApplications from "./MyApplications.jsx";

const SAMPLE_APP = {
  email_id: 42,
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
  latest_interview_at: "2026-07-10T15:00:00Z",
  sent_at: "2026-07-01T10:00:00Z",
  created_at: "2026-07-01T09:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <MyApplications />
    </MemoryRouter>
  );
}

describe("MyApplications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMySubscription.mockResolvedValue({ trial_days_remaining: null, trial_expires_at: null });
  });

  it("renders an application with its pipeline stage and interview count", async () => {
    api.listMyApplications.mockResolvedValue([SAMPLE_APP]);
    api.listMyUpcomingInterviews.mockResolvedValue([]);
    renderPage();

    await waitFor(() => expect(screen.getByText("Java Architect")).toBeInTheDocument());
    expect(screen.getByText("BigCo")).toBeInTheDocument();
    expect(screen.getByText("Interviewing")).toBeInTheDocument();
    expect(screen.getByText(/2 interviews/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no applications yet", async () => {
    api.listMyApplications.mockResolvedValue([]);
    api.listMyUpcomingInterviews.mockResolvedValue([]);
    renderPage();

    await waitFor(() => expect(screen.getByText(/no applications submitted yet/i)).toBeInTheDocument());
  });

  it("lists upcoming interviews separately from the applications history", async () => {
    api.listMyApplications.mockResolvedValue([]);
    api.listMyUpcomingInterviews.mockResolvedValue([
      { id: 1, round_name: "Final round", scheduled_at: "2026-07-15T14:00:00Z", status: "scheduled", notes: null, created_at: "2026-07-01T00:00:00Z" },
    ]);
    renderPage();

    await waitFor(() => expect(screen.getByText("Final round")).toBeInTheDocument());
  });

  it("shows 'nothing scheduled' when there are no upcoming interviews", async () => {
    api.listMyApplications.mockResolvedValue([]);
    api.listMyUpcomingInterviews.mockResolvedValue([]);
    renderPage();

    await waitFor(() => expect(screen.getByText(/nothing scheduled right now/i)).toBeInTheDocument());
  });

  it("expands an application to show interview detail on click", async () => {
    api.listMyApplications.mockResolvedValue([SAMPLE_APP]);
    api.listMyUpcomingInterviews.mockResolvedValue([]);
    api.getMyApplication.mockResolvedValue({
      ...SAMPLE_APP,
      subject: "Application to BigCo",
      body: "...",
      resume_file_name: "john_smith.docx",
      pipeline_notes: null,
      interviews: [
        { id: 1, round_name: "Phone Screen", scheduled_at: "2026-07-05T10:00:00Z", status: "completed", notes: null, created_at: "2026-07-01T00:00:00Z" },
        { id: 2, round_name: "Final", scheduled_at: "2026-07-15T14:00:00Z", status: "scheduled", notes: null, created_at: "2026-07-01T00:00:00Z" },
      ],
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Java Architect")).toBeInTheDocument());
    await user.click(screen.getByText("Java Architect"));

    await waitFor(() => expect(api.getMyApplication).toHaveBeenCalledWith(42));
    await waitFor(() => expect(screen.getByText("Phone Screen")).toBeInTheDocument());
    expect(screen.getByText("Final")).toBeInTheDocument();
  });

  it("shows an error message if loading applications fails", async () => {
    api.listMyApplications.mockRejectedValue({ detail: "Session expired" });
    api.listMyUpcomingInterviews.mockResolvedValue([]);
    renderPage();

    await waitFor(() => expect(screen.getByText("Session expired")).toBeInTheDocument());
  });
});
