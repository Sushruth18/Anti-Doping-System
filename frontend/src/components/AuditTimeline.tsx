import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { getAuditTimeline } from "../api/client";
import type { AuditEvent, AuditTimelineResponse } from "../types/api";

interface AuditTimelineProps {
  athleteId: number;
}

// Same moderate/elevated cutoffs ExplanationPanel.tsx already applies to
// anomaly_score — reused here so an anomaly event's accent color agrees
// with how the Anomaly History panel labels that same score.
const ANOMALY_SEVERITY = { moderate: 0.55, elevated: 0.7 };

interface EventMeta {
  label: string;
  borderClass: string;
  body: ReactNode;
}

function describeEvent(event: AuditEvent): EventMeta | null {
  switch (event.type) {
    case "sample": {
      const s = event.data;
      const flags = [
        s.competition_flag && "competition",
        s.altitude_flag && "altitude",
        s.injury_flag && "injury",
      ].filter((flag): flag is string => Boolean(flag));
      return {
        label: "Sample",
        borderClass: "border-l-gray-300",
        body: (
          <>
            <div>
              Hb {s.hb.toFixed(1)} g/dL · HCT {s.hct.toFixed(1)}% · RET% {s.ret_pct.toFixed(1)} ·
              OFF {s.off_score.toFixed(1)} · T/E {s.te_ratio.toFixed(2)}
            </div>
            {flags.length > 0 && (
              <div className="mt-1 text-xs text-gray-500">Flags: {flags.join(", ")}</div>
            )}
          </>
        ),
      };
    }

    case "anomaly": {
      const a = event.data;
      const elevated = a.anomaly_score >= ANOMALY_SEVERITY.elevated;
      const moderate = a.anomaly_score >= ANOMALY_SEVERITY.moderate;
      return {
        label: "Anomaly score",
        borderClass: elevated
          ? "border-l-red-500"
          : moderate
            ? "border-l-amber-500"
            : "border-l-gray-300",
        body: (
          <div>
            score {a.anomaly_score.toFixed(2)} (raw distance {a.mahalanobis_distance.toFixed(2)},{" "}
            {a.method})
          </div>
        ),
      };
    }

    case "case_opened": {
      const c = event.data;
      return {
        label: "Case opened",
        borderClass: "border-l-orange-500",
        body: c.investigator_notes ? (
          <div>{c.investigator_notes}</div>
        ) : (
          <div className="text-gray-500">No notes provided.</div>
        ),
      };
    }

    case "case_closed": {
      const c = event.data;
      return {
        label: "Case closed",
        borderClass: "border-l-gray-400",
        body: c.investigator_notes ? (
          <div>{c.investigator_notes}</div>
        ) : (
          <div className="text-gray-500">No notes provided.</div>
        ),
      };
    }

    case "decision": {
      const d = event.data;
      const notes = typeof d.details.notes === "string" ? d.details.notes : null;
      return {
        label: "Decision",
        borderClass: "border-l-blue-500",
        body: (
          <div>
            <span className="font-medium">{d.actor}</span> — {d.action}
            {notes && <div className="mt-1 text-gray-600">{notes}</div>}
          </div>
        ),
      };
    }

    default:
      // `recommendation` is a member of the contract's AuditEvent union
      // (docs/api-contract.md) but the backend doesn't emit it yet — see
      // the comment above get_audit_timeline in backend/app/routes/cases.py
      // for why. No dedicated UI is built for a type that can never
      // currently arrive; falling through to `null` (skipped by the
      // caller below) keeps this safe if/when it eventually does.
      return null;
  }
}

function AuditTimeline({ athleteId }: AuditTimelineProps) {
  const [result, setResult] = useState<AuditTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    setResult(null);
    getAuditTimeline(athleteId)
      .then((data) => setResult(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [athleteId]);

  if (loading) {
    return (
      <div>
        <h2 className="text-lg font-medium">Audit Timeline</h2>
        <div className="mt-2 flex items-center justify-center gap-3 rounded border border-gray-300 py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-gray-200 border-t-gray-600" />
          <span className="text-sm text-gray-500">Loading audit timeline…</span>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div>
        <h2 className="text-lg font-medium">Audit Timeline</h2>
        <div className="mt-2 rounded border border-gray-300 p-8 text-center">
          <p className="text-sm font-medium text-red-600">Unable to load audit timeline</p>
        </div>
      </div>
    );
  }

  if (result.events.length === 0) {
    return (
      <div>
        <h2 className="text-lg font-medium">Audit Timeline</h2>
        <p className="mt-2 text-sm text-gray-500">No history yet for this athlete.</p>
      </div>
    );
  }

  // docs/api-contract.md returns events ascending (oldest first). Displayed
  // newest-first here instead: this is an activity/audit log, and an
  // investigator opening it cares most about what just happened, not what
  // happened first — the same convention most activity-feed UIs use.
  const eventsNewestFirst = [...result.events].reverse();

  return (
    <div>
      <h2 className="text-lg font-medium">Audit Timeline</h2>
      <ol className="mt-2 flex flex-col gap-2">
        {eventsNewestFirst.map((event) => {
          const meta = describeEvent(event);
          if (!meta) return null;
          return (
            <li
              key={`${event.type}-${event.data.id}`}
              className={`rounded border border-gray-300 border-l-4 p-3 text-sm ${meta.borderClass}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  {meta.label}
                </span>
                <span className="text-xs text-gray-400">{event.timestamp}</span>
              </div>
              <div className="mt-1">{meta.body}</div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default AuditTimeline;
