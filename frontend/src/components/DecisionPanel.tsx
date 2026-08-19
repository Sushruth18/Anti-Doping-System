import { useState } from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { createCase, postDecision } from "../api/client";
import type { AuditLog, Case, DecisionAction } from "../types/api";

const DECISION_ACTIONS: { value: DecisionAction; label: string }[] = [
  { value: "escalate", label: "Escalate" },
  { value: "clear", label: "Clear" },
  { value: "request_more_testing", label: "Request more testing" },
  { value: "close_case", label: "Close case" },
];

// Native <select> kept deliberately rather than swapped for the shadcn
// Select: Base UI's Select is a composite widget driven by `onValueChange`,
// and adopting it would mean rewriting this field's existing onChange
// handler. These classes mirror ui/input.tsx so it still reads as part of
// the same form.
const NATIVE_SELECT_CLASSES =
  "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

interface DecisionPanelProps {
  athleteId: number;
}

function DecisionPanel({ athleteId }: DecisionPanelProps) {
  // Not fetched on mount like the read-only panels -- no case exists until
  // the investigator opens one, so this is a form/state-machine (no case ->
  // case open -> decisions logged), not a data/loading/error triple.
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const [notes, setNotes] = useState("");
  const [openingCase, setOpeningCase] = useState(false);
  const [openCaseError, setOpenCaseError] = useState(false);

  const [action, setAction] = useState<DecisionAction>("escalate");
  const [investigator, setInvestigator] = useState("");
  const [loggingDecision, setLoggingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState(false);

  const handleOpenCase = async () => {
    setOpeningCase(true);
    setOpenCaseError(false);
    try {
      const created = await createCase({ athlete_id: athleteId, notes: notes.trim() || undefined });
      setCaseData(created);
    } catch {
      setOpenCaseError(true);
    } finally {
      setOpeningCase(false);
    }
  };

  const handleLogDecision = async () => {
    if (!caseData || !investigator.trim()) return;
    setLoggingDecision(true);
    setDecisionError(false);
    try {
      const result = await postDecision(caseData.id, { action, investigator: investigator.trim() });
      setCaseData(result.case);
      setAuditLogs((prev) => [...prev, result.audit_log]);
    } catch {
      setDecisionError(true);
    } finally {
      setLoggingDecision(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Investigator Decision</CardTitle>
      </CardHeader>

      <CardContent>
        {!caseData && (
          <div className="flex flex-col gap-2">
            <Label htmlFor="case-notes" className="text-muted-foreground">
              Notes (optional)
            </Label>
            <Textarea
              id="case-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Initial notes for this case…"
            />
            <Button onClick={handleOpenCase} disabled={openingCase} className="w-fit">
              {openingCase ? "Opening…" : "Open Case"}
            </Button>
            {openCaseError && (
              <Alert variant="destructive">
                <AlertTitle>Unable to open case</AlertTitle>
              </Alert>
            )}
          </div>
        )}

        {caseData && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                className={
                  caseData.status === "closed"
                    ? "bg-muted text-muted-foreground"
                    : "bg-success/10 text-success"
                }
              >
                Case {caseData.status}
              </Badge>
              <span className="text-sm text-muted-foreground">
                Opened <span className="font-mono tabular-nums">{caseData.opened_at}</span>
                {caseData.closed_at ? (
                  <>
                    {" · "}Closed{" "}
                    <span className="font-mono tabular-nums">{caseData.closed_at}</span>
                  </>
                ) : (
                  ""
                )}
              </span>
            </div>

            {caseData.investigator_notes && (
              <p className="text-sm text-foreground">{caseData.investigator_notes}</p>
            )}

            {auditLogs.length > 0 && (
              <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                {auditLogs.map((log) => (
                  <li key={log.id}>
                    <span className="font-mono tabular-nums">{log.timestamp}</span> — {log.actor}:{" "}
                    {log.action}
                  </li>
                ))}
              </ul>
            )}

            {caseData.status === "open" && (
              <>
                <Separator />
                <div className="flex flex-col gap-2">
                  <Label htmlFor="decision-action" className="text-muted-foreground">
                    Action
                  </Label>
                  <select
                    id="decision-action"
                    value={action}
                    onChange={(e) => setAction(e.target.value as DecisionAction)}
                    className={NATIVE_SELECT_CLASSES}
                  >
                    {DECISION_ACTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>

                  <Label htmlFor="decision-investigator" className="text-muted-foreground">
                    Investigator
                  </Label>
                  <Input
                    id="decision-investigator"
                    type="text"
                    value={investigator}
                    onChange={(e) => setInvestigator(e.target.value)}
                    placeholder="Your name"
                  />

                  <Button
                    onClick={handleLogDecision}
                    disabled={loggingDecision || !investigator.trim()}
                    className="w-fit"
                  >
                    {loggingDecision ? "Logging…" : "Log Decision"}
                  </Button>
                  {decisionError && (
                    <Alert variant="destructive">
                      <AlertTitle>Unable to log decision</AlertTitle>
                    </Alert>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default DecisionPanel;
