import { useState } from "react";
import { createCase, postDecision } from "../api/client";
import type { AuditLog, Case, DecisionAction } from "../types/api";

const DECISION_ACTIONS: { value: DecisionAction; label: string }[] = [
  { value: "escalate", label: "Escalate" },
  { value: "clear", label: "Clear" },
  { value: "request_more_testing", label: "Request more testing" },
  { value: "close_case", label: "Close case" },
];

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
    <div>
      <h2 className="text-lg font-medium">Investigator Decision</h2>

      <div className="mt-2 rounded border border-gray-300 p-3">
        {!caseData && (
          <div className="flex flex-col gap-2">
            <label htmlFor="case-notes" className="text-sm text-gray-600">
              Notes (optional)
            </label>
            <textarea
              id="case-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Initial notes for this case…"
              className="rounded border border-gray-300 p-2 text-sm"
            />
            <button
              onClick={handleOpenCase}
              disabled={openingCase}
              className="w-fit rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-gray-700 disabled:bg-gray-300"
            >
              {openingCase ? "Opening…" : "Open Case"}
            </button>
            {openCaseError && (
              <p className="text-sm font-medium text-red-600">Unable to open case</p>
            )}
          </div>
        )}

        {caseData && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full px-2.5 py-1 text-sm font-medium ${
                  caseData.status === "closed"
                    ? "bg-gray-200 text-gray-600"
                    : "bg-green-100 text-green-700"
                }`}
              >
                Case {caseData.status}
              </span>
              <span className="text-sm text-gray-500">
                Opened {caseData.opened_at}
                {caseData.closed_at ? ` · Closed ${caseData.closed_at}` : ""}
              </span>
            </div>

            {caseData.investigator_notes && (
              <p className="text-sm text-gray-700">{caseData.investigator_notes}</p>
            )}

            {auditLogs.length > 0 && (
              <ul className="flex flex-col gap-1 text-sm text-gray-600">
                {auditLogs.map((log) => (
                  <li key={log.id}>
                    {log.timestamp} — {log.actor}: {log.action}
                  </li>
                ))}
              </ul>
            )}

            {caseData.status === "open" && (
              <div className="flex flex-col gap-2 border-t border-gray-200 pt-3">
                <label htmlFor="decision-action" className="text-sm text-gray-600">
                  Action
                </label>
                <select
                  id="decision-action"
                  value={action}
                  onChange={(e) => setAction(e.target.value as DecisionAction)}
                  className="rounded border border-gray-300 p-2 text-sm"
                >
                  {DECISION_ACTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>

                <label htmlFor="decision-investigator" className="text-sm text-gray-600">
                  Investigator
                </label>
                <input
                  id="decision-investigator"
                  type="text"
                  value={investigator}
                  onChange={(e) => setInvestigator(e.target.value)}
                  placeholder="Your name"
                  className="rounded border border-gray-300 p-2 text-sm"
                />

                <button
                  onClick={handleLogDecision}
                  disabled={loggingDecision || !investigator.trim()}
                  className="w-fit rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-gray-700 disabled:bg-gray-300"
                >
                  {loggingDecision ? "Logging…" : "Log Decision"}
                </button>
                {decisionError && (
                  <p className="text-sm font-medium text-red-600">Unable to log decision</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default DecisionPanel;
