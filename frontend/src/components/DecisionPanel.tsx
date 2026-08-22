import { useState } from "react";
import { createCase, postDecision } from "../api/client";
import type { AuditLog, Case, DecisionAction } from "../types/api";
import {
  FolderOpen,
  CheckCircle,
  TestTubeDiagonal,
  XCircle,
  ArrowUpCircle,
  Clock,
} from "lucide-react";

const DECISION_ACTIONS: { value: DecisionAction; label: string; icon: React.ReactNode }[] = [
  { value: "escalate",           label: "Escalate",            icon: <ArrowUpCircle size={13} /> },
  { value: "clear",              label: "Clear",               icon: <CheckCircle size={13} /> },
  { value: "request_more_testing", label: "Request More Testing", icon: <TestTubeDiagonal size={13} /> },
  { value: "close_case",         label: "Close Case",          icon: <XCircle size={13} /> },
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
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* No case yet */}
      {!caseData && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", margin: 0, lineHeight: 1.5 }}>
            Open a case to begin the formal investigation workflow for this athlete.
          </p>
          <div>
            <label htmlFor="case-notes" className="form-label">Case Notes (optional)</label>
            <textarea
              id="case-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Initial notes for this case…"
              className="form-textarea"
            />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              onClick={handleOpenCase}
              disabled={openingCase}
              className="btn btn-primary"
            >
              <FolderOpen size={14} />
              {openingCase ? "Opening…" : "Open Investigation Case"}
            </button>
            {openCaseError && (
              <span style={{ fontSize: "0.8125rem", color: "#ef4444" }}>Failed to open case</span>
            )}
          </div>
        </div>
      )}

      {/* Case open */}
      {caseData && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Status */}
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
            <span className={`badge ${caseData.status === "closed" ? "badge-closed" : "badge-open"}`}>
              Case {caseData.status}
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              #{caseData.id}
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>
              Opened {caseData.opened_at}
              {caseData.closed_at ? ` · Closed ${caseData.closed_at}` : ""}
            </span>
          </div>

          {/* Notes */}
          {caseData.investigator_notes && (
            <p
              style={{
                fontSize: "0.8125rem",
                color: "var(--foreground)",
                margin: 0,
                padding: "10px 12px",
                background: "var(--muted)",
                borderRadius: 6,
                border: "1px solid var(--border)",
                lineHeight: 1.5,
              }}
            >
              {caseData.investigator_notes}
            </p>
          )}

          {/* Audit trail */}
          {auditLogs.length > 0 && (
            <div>
              <div style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 8 }}>
                Audit Trail
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {auditLogs.map((log) => (
                  <div key={log.id} className="timeline-item">
                    <div className="timeline-dot" style={{ background: "var(--primary)" }} />
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
                        <Clock size={11} color="var(--muted-foreground)" />
                        <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                          {log.timestamp}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.8125rem", color: "var(--foreground)" }}>
                        <strong style={{ fontWeight: 600 }}>{log.actor}</strong>
                        <span style={{ color: "var(--muted-foreground)" }}> — </span>
                        {log.action}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Decision form */}
          {caseData.status === "open" && (
            <div
              style={{
                borderTop: "1px solid var(--border)",
                paddingTop: 14,
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--muted-foreground)" }}>
                Log Decision
              </div>

              <div>
                <label htmlFor="decision-action" className="form-label">Action</label>
                <select
                  id="decision-action"
                  value={action}
                  onChange={(e) => setAction(e.target.value as DecisionAction)}
                  className="form-select"
                >
                  {DECISION_ACTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="decision-investigator" className="form-label">Investigator Name</label>
                <input
                  id="decision-investigator"
                  type="text"
                  value={investigator}
                  onChange={(e) => setInvestigator(e.target.value)}
                  placeholder="Your name"
                  className="form-input"
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <button
                  onClick={handleLogDecision}
                  disabled={loggingDecision || !investigator.trim()}
                  className="btn btn-primary"
                >
                  {loggingDecision ? (
                    <>
                      <div className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
                      Logging…
                    </>
                  ) : (
                    <>
                      <CheckCircle size={13} />
                      Log Decision
                    </>
                  )}
                </button>
                {decisionError && (
                  <span style={{ fontSize: "0.8125rem", color: "#ef4444" }}>Failed to log decision</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DecisionPanel;
