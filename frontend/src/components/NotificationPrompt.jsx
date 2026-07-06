import { useEffect, useState } from "react";
import { isPushSupported, subscribeToPush } from "../services/push";

const DISMISSED_KEY = "ai_recruiter_push_prompt_dismissed";

export default function NotificationPrompt() {
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isPushSupported()) return;
    if (localStorage.getItem(DISMISSED_KEY)) return;
    if (Notification.permission === "granted" || Notification.permission === "denied") return;
    setVisible(true);
  }, []);

  async function handleEnable() {
    try {
      await subscribeToPush();
      setVisible(false);
    } catch (e) {
      setError(e.message || "Couldn't enable notifications.");
    }
  }

  function handleDismiss() {
    localStorage.setItem(DISMISSED_KEY, "1");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-16 md:bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 rounded-xl border border-black/10 bg-paper shadow-lg p-4 space-y-2 z-20">
      <p className="text-sm font-medium">Get notified instantly</p>
      <p className="text-xs text-ink/60">
        Enable notifications so you know right away when something needs your approval — instead of an
        email, or checking back later.
      </p>
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button onClick={handleEnable} className="flex-1 rounded-lg bg-ink text-paper text-xs font-medium py-2">
          Enable
        </button>
        <button onClick={handleDismiss} className="flex-1 rounded-lg border border-black/15 text-xs font-medium py-2">
          Not now
        </button>
      </div>
    </div>
  );
}
