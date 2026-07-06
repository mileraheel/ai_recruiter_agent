import { useEffect, useState } from "react";
import { api } from "../api/client";
import SelfApprovalDisclaimer from "../components/SelfApprovalDisclaimer";

const TIER_LABELS = {
  core: { label: "Core", cls: "bg-accentSoft text-accent" },
  component: { label: "Component", cls: "bg-accentSoft text-accent" },
  secondary: { label: "Secondary", cls: "bg-warnSoft text-warn" },
  exposure: { label: "Exposure only", cls: "bg-black/5 text-ink/60" },
};

const TIER_OPTIONS = ["core", "component", "secondary", "exposure"];

function TierBadge({ tier }) {
  const meta = TIER_LABELS[tier] || { label: tier, cls: "bg-black/5 text-ink/60" };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${meta.cls}`}>
      {meta.label}
    </span>
  );
}

function ApprovalCard({ item, onDecide }) {
  const [tierOverride, setTierOverride] = useState(item.tier);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function decide(decision) {
    setBusy(true);
    try {
      await onDecide(item.id, {
        decision,
        tier_override: decision === "approve" ? tierOverride : null,
        review_notes: notes || null,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-black/10 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{item.skill_name}</p>
          {item.source_project_or_role && (
            <p className="text-xs text-ink/50 mt-0.5">{item.source_project_or_role}</p>
          )}
        </div>
        <TierBadge tier={item.tier} />
      </div>

      {item.source_bullet && (
        <blockquote className="text-sm text-ink/70 border-l-2 border-black/10 pl-3 italic">
          "{item.source_bullet}"
        </blockquote>
      )}

      <div className="flex items-center gap-2 text-xs text-ink/40">
        <span>Suggested by {item.suggested_by === "claude_extraction" ? "resume extraction" : item.suggested_by}</span>
        {item.confidence != null && <span>· confidence {Math.round(item.confidence * 100)}%</span>}
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <label className="text-xs text-ink/50">Tier:</label>
        <select
          value={tierOverride}
          onChange={(e) => setTierOverride(e.target.value)}
          className="rounded-md border border-black/15 text-xs px-2 py-1"
        >
          {TIER_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {TIER_LABELS[t].label}
            </option>
          ))}
        </select>
      </div>

      <input
        type="text"
        placeholder="Review notes (optional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="w-full rounded-md border border-black/15 px-2.5 py-1.5 text-xs"
      />

      <div className="flex gap-2 pt-1">
        <button
          disabled={busy}
          onClick={() => decide("approve")}
          className="flex-1 rounded-lg bg-accent text-white text-sm font-medium py-2 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => decide("reject")}
          className="flex-1 rounded-lg bg-dangerSoft text-danger text-sm font-medium py-2 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function ApprovalQueue() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const data = await api.listApprovalQueue();
      setItems(data);
    } catch (e) {
      setError(e.detail || "Failed to load approval queue");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleDecide(itemId, decision) {
    await api.decideApproval(itemId, decision);
    setItems((prev) => prev.filter((i) => i.id !== itemId));
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Approval queue</h1>
        <p className="text-sm text-ink/60 mt-0.5">
          Skills detected from resume changes, held here until you confirm the provenance tier. Nothing
          below is used for job matching or tailoring until approved.
        </p>
      </div>

      <SelfApprovalDisclaimer />

      {error && <div className="rounded-lg bg-dangerSoft text-danger text-sm px-3 py-2">{error}</div>}

      {items === null && !error && <p className="text-sm text-ink/50">Loading…</p>}

      {items !== null && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-black/15 p-8 text-center">
          <p className="text-sm text-ink/50">Nothing pending. New skill suggestions will show up here.</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {items?.map((item) => (
          <ApprovalCard key={item.id} item={item} onDecide={handleDecide} />
        ))}
      </div>
    </div>
  );
}
