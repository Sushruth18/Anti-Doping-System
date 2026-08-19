import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
        borderClass: "border-l-border",
        body: (
          <>
            <div className="font-mono tabular-nums">
              Hb {s.hb.toFixed(1)} g/dL · HCT {s.hct.toFixed(1)}% · RET% {s.ret_pct.toFixed(1)} ·
              OFF {s.off_score.toFixed(1)} · T/E {s.te_ratio.toFixed(2)}
            </div>
            {flags.length > 0 && (
              <div className="mt-1 text-xs text-muted-foreground">Flags: {flags.join(", ")}</div>
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
          ? "border-l-destructive"
          : moderate
            ? "border-l-warning"
            : "border-l-border",
        body: (
          <div>
            score <span className="font-mono tabular-nums">{a.anomaly_score.toFixed(2)}</span> (raw
            distance{" "}
            <span className="font-mono tabular-nums">{a.mahalanobis_distance.toFixed(2)}</span>,{" "}
            {a.method})
          </div>
        ),
      };
    }

    case "case_opened": {
      const c = event.data;
      return {
        label: "Case opened",
        borderClass: "border-l-warning",
        body: c.investigator_notes ? (
          <div>{c.investigator_notes}</div>
        ) : (
          <div className="text-muted-foreground">No notes provided.</div>
        ),
      };
    }

    case "case_closed": {
      const c = event.data;
      return {
        label: "Case closed",
        borderClass: "border-l-muted-foreground",
        body: c.investigator_notes ? (
          <div>{c.investigator_notes}</div>
        ) : (
          <div className="text-muted-foreground">No notes provided.</div>
        ),
      };
    }

    case "decision": {
      const d = event.data;
      const notes = typeof d.details.notes === "string" ? d.details.notes : null;
      return {
        label: "Decision",
        borderClass: "border-l-primary",
        body: (
          <div>
            <span className="font-medium">{d.actor}</span> — {d.action}
            {notes && <div className="mt-1 text-muted-foreground">{notes}</div>}
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
      <Card>
        <CardHeader>
          <CardTitle>Audit Timeline</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {/* Shape-matched to a real event row (label line + body line). */}
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg border border-border border-l-4 p-3">
              <div className="flex items-center justify-between gap-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-3 w-40" />
              </div>
              <Skeleton className="mt-2 h-4 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error || !result) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Audit Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTitle>Unable to load audit timeline</AlertTitle>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (result.events.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Audit Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No history yet for this athlete.</p>
        </CardContent>
      </Card>
    );
  }

  // docs/api-contract.md returns events ascending (oldest first). Displayed
  // newest-first here instead: this is an activity/audit log, and an
  // investigator opening it cares most about what just happened, not what
  // happened first — the same convention most activity-feed UIs use.
  const eventsNewestFirst = [...result.events].reverse();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-2">
          {eventsNewestFirst.map((event) => {
            const meta = describeEvent(event);
            if (!meta) return null;
            return (
              <li
                key={`${event.type}-${event.data.id}`}
                className={`rounded-lg border border-border border-l-4 p-3 text-sm ${meta.borderClass}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    {meta.label}
                  </span>
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    {event.timestamp}
                  </span>
                </div>
                <div className="mt-1">{meta.body}</div>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

export default AuditTimeline;
