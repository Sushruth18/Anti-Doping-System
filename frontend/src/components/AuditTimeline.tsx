import { useEffect, useState, useMemo } from "react";
import { getAuditTimeline } from "../api/client";
import type { AuditTimelineResponse } from "../types/api";
import {
  AlertTriangle,
  Clock,
  TestTube2,
  Activity,
  FolderOpen,
  FolderLock,
  ShieldCheck,
  Flag,
} from "lucide-react";

interface AuditTimelineProps {
  athleteId: number;
}

const ANOMALY_SEVERITY = { moderate: 0.55, elevated: 0.70, critical: 0.90 };

export function AuditTimeline({ athleteId }: AuditTimelineProps) {
  const [result, setResult] = useState<AuditTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filterType, setFilterType] = useState<"all" | "sample" | "anomaly" | "case">("all");

  useEffect(() => {
    setLoading(true);
    setError(false);
    setResult(null);
    getAuditTimeline(athleteId)
      .then((data) => setResult(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [athleteId]);

  const events = useMemo(() => {
    if (!result?.events) return [];
    const reversed = [...result.events].reverse();
    if (filterType === "all") return reversed;
    if (filterType === "sample") return reversed.filter((e) => e.type === "sample");
    if (filterType === "anomaly") return reversed.filter((e) => e.type === "anomaly");
    if (filterType === "case") return reversed.filter((e) => e.type === "case_opened" || e.type === "case_closed" || e.type === "decision");
    return reversed;
  }, [result, filterType]);

  if (loading) {
    return (
      <div className="panel animate-fade-in">
        <div className="panel-header">
          <div className="panel-title">
            <Clock size={16} color="var(--primary)" />
            Audit Timeline
          </div>
        </div>
        <div className="panel-body">
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: 64, borderRadius: 8 }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">
            <Clock size={16} color="var(--primary)" />
            Audit Timeline
          </div>
        </div>
        <div className="panel-body">
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#ef4444" }}>
            <AlertTriangle size={18} />
            <span style={{ fontSize: "0.8125rem", fontWeight: 600 }}>Unable to load audit timeline events</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel animate-fade-in">
      <div className="panel-header">
        <div>
          <div className="panel-title">
            <Clock size={16} color="var(--primary)" />
            Audit Timeline & Evidence Dossier
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: 2 }}>
            Chronological audit trail · {result.events.length} total logged event{result.events.length !== 1 ? "s" : ""} (newest first)
          </div>
        </div>

        {/* Filter buttons */}
        <div className="print-hide" style={{ display: "flex", gap: 4 }}>
          {[
            { id: "all", label: "All" },
            { id: "sample", label: "Samples" },
            { id: "anomaly", label: "Anomalies" },
            { id: "case", label: "Cases & Decisions" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterType(tab.id as typeof filterType)}
              className={`filter-chip ${filterType === tab.id ? "active" : ""}`}
              style={{ fontSize: "0.6875rem", padding: "3px 8px" }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="panel-body" style={{ padding: "20px 24px" }}>
        {events.length === 0 ? (
          <div style={{ textAlign: "center", padding: "30px 0", color: "var(--muted-foreground)", fontSize: "0.8125rem" }}>
            No timeline events match the selected filter.
          </div>
        ) : (
          <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 0 }}>
            {/* Vertical connector line */}
            <div
              style={{
                position: "absolute",
                left: "15px",
                top: "16px",
                bottom: "20px",
                width: "2px",
                background: "var(--border)",
                zIndex: 0,
              }}
            />

            {events.map((event, idx) => {
              let icon = <TestTube2 size={13} color="var(--primary)" />;
              let dotBg = "var(--muted)";
              let dotBorder = "var(--primary)";
              let badgeCls = "badge-neutral";
              let badgeLabel = "Event";
              let cardBg = "var(--card)";
              let cardBorder = "var(--border)";

              if (event.type === "sample") {
                icon = <TestTube2 size={13} color="var(--primary)" />;
                dotBorder = "var(--primary)";
                badgeCls = "badge-neutral";
                badgeLabel = `Sample #${event.data.id}`;
              } else if (event.type === "anomaly") {
                const isCrit = event.data.anomaly_score >= ANOMALY_SEVERITY.critical;
                const isElev = event.data.anomaly_score >= ANOMALY_SEVERITY.elevated;
                const isMod = event.data.anomaly_score >= ANOMALY_SEVERITY.moderate;
                icon = <Activity size={13} color={isElev ? "var(--destructive)" : "var(--warning)"} />;
                dotBorder = isElev ? "var(--destructive)" : isMod ? "var(--warning)" : "var(--success)";
                badgeCls = isCrit ? "badge-critical" : isElev ? "badge-elevated" : isMod ? "badge-moderate" : "badge-clean";
                badgeLabel = isCrit ? "Critical Anomaly" : isElev ? "Elevated Anomaly" : isMod ? "Moderate Anomaly" : "Normal Evaluation";
                cardBg = isElev ? "var(--severity-critical-bg)" : "var(--card)";
                cardBorder = isElev ? "var(--severity-critical-border)" : "var(--border)";
              } else if (event.type === "case_opened") {
                icon = <FolderOpen size={13} color="#f59e0b" />;
                dotBorder = "#f59e0b";
                badgeCls = "badge-moderate";
                badgeLabel = "Case Opened";
              } else if (event.type === "case_closed") {
                icon = <FolderLock size={13} color="#94a3b8" />;
                dotBorder = "#94a3b8";
                badgeCls = "badge-closed";
                badgeLabel = "Case Closed";
              } else if (event.type === "decision") {
                icon = <ShieldCheck size={13} color="#10b981" />;
                dotBorder = "#10b981";
                badgeCls = "badge-open";
                badgeLabel = "Decision Logged";
              }

              return (
                <div
                  key={`${event.type}-${event.data.id}-${idx}`}
                  style={{
                    position: "relative",
                    display: "flex",
                    gap: "16px",
                    paddingBottom: idx === events.length - 1 ? 0 : "20px",
                    zIndex: 1,
                  }}
                >
                  {/* Circular timeline node */}
                  <div
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "50%",
                      background: dotBg,
                      border: `2px solid ${dotBorder}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      boxShadow: "0 0 10px rgba(0,0,0,0.4)",
                    }}
                  >
                    {icon}
                  </div>

                  {/* Card Content */}
                  <div
                    style={{
                      flex: 1,
                      background: cardBg,
                      border: `1px solid ${cardBorder}`,
                      borderRadius: "8px",
                      padding: "12px 16px",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: 8,
                        marginBottom: 8,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className={`badge ${badgeCls}`} style={{ fontSize: "0.6875rem" }}>
                          {badgeLabel}
                        </span>
                        <span
                          style={{
                            fontSize: "0.6875rem",
                            color: "var(--muted-foreground)",
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          ID #{event.data.id}
                        </span>
                      </div>

                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--muted-foreground)",
                          fontFamily: "var(--font-mono)",
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <Clock size={11} />
                        {event.timestamp}
                      </div>
                    </div>

                    {/* Event Detail Rendering */}
                    {event.type === "sample" && (
                      <div>
                        {/* Biomarker Grid */}
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
                            gap: "8px",
                            background: "var(--muted)",
                            padding: "8px 12px",
                            borderRadius: "6px",
                            border: "1px solid var(--border)",
                            fontSize: "0.75rem",
                          }}
                        >
                          <div>
                            <span style={{ color: "var(--muted-foreground)", fontSize: "0.6875rem" }}>Hb: </span>
                            <strong style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
                              {event.data.hb.toFixed(1)} g/dL
                            </strong>
                          </div>
                          <div>
                            <span style={{ color: "var(--muted-foreground)", fontSize: "0.6875rem" }}>HCT: </span>
                            <strong style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
                              {event.data.hct.toFixed(1)}%
                            </strong>
                          </div>
                          <div>
                            <span style={{ color: "var(--muted-foreground)", fontSize: "0.6875rem" }}>RET%: </span>
                            <strong style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
                              {event.data.ret_pct.toFixed(1)}%
                            </strong>
                          </div>
                          <div>
                            <span style={{ color: "var(--muted-foreground)", fontSize: "0.6875rem" }}>OFF-Score: </span>
                            <strong style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
                              {event.data.off_score.toFixed(1)}
                            </strong>
                          </div>
                          <div>
                            <span style={{ color: "var(--muted-foreground)", fontSize: "0.6875rem" }}>T/E Ratio: </span>
                            <strong style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
                              {event.data.te_ratio.toFixed(2)}
                            </strong>
                          </div>
                        </div>

                        {/* Flags */}
                        {(event.data.competition_flag || event.data.altitude_flag || event.data.injury_flag) && (
                          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                            {event.data.competition_flag && (
                              <span className="badge badge-info" style={{ fontSize: "0.625rem" }}>
                                <Flag size={10} /> Competition Sample
                              </span>
                            )}
                            {event.data.altitude_flag && (
                              <span className="badge badge-moderate" style={{ fontSize: "0.625rem" }}>
                                <Flag size={10} /> High Altitude
                              </span>
                            )}
                            {event.data.injury_flag && (
                              <span className="badge badge-critical" style={{ fontSize: "0.625rem" }}>
                                <Flag size={10} /> Injury Reported
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {event.type === "anomaly" && (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          background: "var(--muted)",
                          padding: "10px 14px",
                          borderRadius: "6px",
                          border: "1px solid var(--border)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                          <div>
                            <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>Score: </span>
                            <strong
                              style={{
                                fontFamily: "var(--font-mono)",
                                fontSize: "0.9375rem",
                                color: event.data.anomaly_score >= 0.7 ? "#ef4444" : event.data.anomaly_score >= 0.55 ? "#f59e0b" : "#10b981",
                              }}
                            >
                              {event.data.anomaly_score.toFixed(3)}
                            </strong>
                          </div>
                          <div>
                            <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>Raw Distance: </span>
                            <strong style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem", color: "var(--foreground)" }}>
                              {event.data.mahalanobis_distance.toFixed(2)}
                            </strong>
                          </div>
                          <div>
                            <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>Method: </span>
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#60a5fa" }}>
                              {event.data.method}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {(event.type === "case_opened" || event.type === "case_closed") && (
                      <div style={{ fontSize: "0.8125rem", color: "var(--foreground)", background: "var(--muted)", padding: "8px 12px", borderRadius: 6 }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", textTransform: "uppercase", fontWeight: 600, marginBottom: 2 }}>
                          Investigator Notes
                        </div>
                        {event.data.investigator_notes || "No initial case notes recorded."}
                      </div>
                    )}

                    {event.type === "decision" && (
                      <div style={{ fontSize: "0.8125rem", color: "var(--foreground)", background: "var(--muted)", padding: "8px 12px", borderRadius: 6 }}>
                        <div>
                          <strong style={{ color: "var(--primary)" }}>{event.data.actor}</strong>
                          <span style={{ color: "var(--muted-foreground)" }}> executed decision: </span>
                          <strong style={{ textTransform: "uppercase", letterSpacing: "0.02em" }}>
                            {event.data.action.replace(/_/g, " ")}
                          </strong>
                        </div>
                        {event.data.details && typeof event.data.details.notes === "string" && (
                          <div style={{ marginTop: 4, color: "var(--muted-foreground)", fontSize: "0.75rem" }}>
                            {event.data.details.notes}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default AuditTimeline;
