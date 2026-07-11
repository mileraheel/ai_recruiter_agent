import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const AUTO_DISMISS_MS = 6000;
const SESSION_KEY = "ai_recruiter_trial_banner_shown";

function formatDate(isoDate) {
  try {
    return new Date(isoDate + "T00:00:00").toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return isoDate;
  }
}

/**
 * Shows a short-lived top banner once per login session when the
 * signed-in account's trial/subscription is within the platform-wide
 * configured window (PlatformSettings.trial_banner_window_days,
 * returned alongside trial_days_remaining by both endpoints below) of
 * expiring. Admins see their organization's trial; candidates see
 * whichever of their own subscription or their org's trial expires
 * sooner (see api/routers/candidate_self.py::get_my_subscription).
 * Staff and superusers don't have a personal trial, so this renders
 * nothing for those roles.
 */
export default function TrialBanner() {
  const { role } = useAuth();
  const [info, setInfo] = useState(null); // { daysRemaining, expiresAt } | null
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (role !== "admin" && role !== "candidate") return;
    if (sessionStorage.getItem(SESSION_KEY)) return;

    const fetcher = role === "admin" ? api.getOrgSettings : api.getMySubscription;
    fetcher()
      .then((data) => {
        const daysRemaining = data.trial_days_remaining;
        const expiresAt = data.trial_expires_at;
        if (daysRemaining === null || daysRemaining === undefined) return;
        if (daysRemaining > data.trial_banner_window_days) return;

        setInfo({ daysRemaining, expiresAt });
        setVisible(true);
        sessionStorage.setItem(SESSION_KEY, "1");
      })
      .catch(() => {
        // Silent -- a trial-status check failing shouldn't block the
        // rest of the app or surface as a scary error to the user.
      });
  }, [role]);

  useEffect(() => {
    if (!visible) return undefined;
    const timer = setTimeout(() => setVisible(false), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [visible]);

  if (!visible || !info) return null;

  const { daysRemaining, expiresAt } = info;
  const urgent = daysRemaining <= 2;
  const message =
    daysRemaining < 0
      ? `Your subscription expired on ${formatDate(expiresAt)}.`
      : daysRemaining === 0
        ? "Your subscription expires today."
        : `Your subscription expires on ${formatDate(expiresAt)} (${daysRemaining} day${daysRemaining === 1 ? "" : "s"} left).`;

  return (
    <div
      role="status"
      className={`fixed top-0 left-0 right-0 z-30 flex items-center justify-center gap-3 px-4 py-2.5 text-sm font-medium text-center ${
        urgent ? "bg-danger text-paper" : "bg-amber text-ink"
      }`}
    >
      <span>{message} Please contact your sales person to renew.</span>
      <button
        onClick={() => setVisible(false)}
        aria-label="Dismiss"
        className="shrink-0 rounded-full w-5 h-5 flex items-center justify-center hover:bg-ink/10"
      >
        ×
      </button>
    </div>
  );
}
