import { useEffect, useState } from "react";
import { api } from "../api/client";

/**
 * Shown only when the logged-in account is an "individual" (self-service,
 * one person acting as both admin and candidate) approving their own
 * skill/resume/document submissions -- a real, distinct risk from an
 * agency admin reviewing someone else's claims. Nobody else is checking
 * this person's work, so the disclaimer makes that explicit rather than
 * assuming they'll remember on their own.
 */
export default function SelfApprovalDisclaimer() {
  const [isIndividual, setIsIndividual] = useState(false);

  useEffect(() => {
    api.getOrgSettings().then((s) => setIsIndividual(s.account_type === "individual")).catch(() => {});
  }, []);

  if (!isIndividual) return null;

  return (
    <div className="rounded-xl bg-warnSoft text-warn text-sm px-4 py-3 flex gap-2">
      <span className="shrink-0">⚠️</span>
      <p>
        You're approving your own submission — nobody else double-checks this. Only approve skills you
        genuinely have hands-on experience with. Claiming something you don't know wastes your own time,
        application credits, and reputation with recruiters — e.g. applying to .NET roles as a Java
        developer helps no one, least of all you.
      </p>
    </div>
  );
}
