import type { AnomalyDetail } from "../types/api";
import { TrendingUp, TrendingDown, Clock } from "lucide-react";

// Calibrated against backend ANOMALY_SCORE_SCALE=10.0 on the 80-athlete
// seeded cohort (15 synthetic anomalies / 65 clean). EPO and steroid
// micro-dosing patterns score lower than transfusion patterns under this
// single-sample Mahalanobis detector — a known, documented limitation
// addressed by the planned CUSUM cumulative detector, not a threshold bug.
const SEVERITY_THRESHOLDS = { moderate: 0.55, elevated: 0.70 };

function severityLabel(anomalyScore: number): { label: string; cls: string } {
  if (anomalyScore >= SEVERITY_THRESHOLDS.elevated) return { label: "Elevated Priority", cls: "badge-elevated" };
  if (anomalyScore >= SEVERITY_THRESHOLDS.moderate) return { label: "Moderate Priority", cls: "badge-moderate" };
  return { label: "Low Priority", cls: "badge-clean" };
}

// Safe formatter — returns "—" for undefined/null values
function fmt(val: number | undefined | null, digits = 2): string {
  if (val == null || !isFinite(val)) return "—";
  return val.toFixed(digits);
}

interface ExplanationPanelProps {
  anomalies: AnomalyDetail[];
}

function ExplanationPanel({ anomalies }: ExplanationPanelProps) {
  if (anomalies.length === 0) {
    return (
      <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", margin: 0 }}>
        No anomaly history yet for this athlete.
      </p>
    );
  }

  const [mostRecent, ...older] = anomalies;
  const sev = severityLabel(mostRecent.anomaly_score);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Most recent */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <span className={`badge ${sev.cls}`}>{sev.label}</span>
          <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            score {fmt(mostRecent.anomaly_score, 3)} · d={fmt(mostRecent.mahalanobis_distance, 2)}
          </span>
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginBottom: 10 }}>
          {mostRecent.created_at}
        </div>

        {mostRecent.contributing_biomarkers.length > 0 && (
          <div
            style={{
              background: "var(--muted)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            {mostRecent.contributing_biomarkers.map((b, i) => (
              <div
                key={b.biomarker}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  gap: 8,
                  borderBottom: i < mostRecent.contributing_biomarkers.length - 1
                    ? "1px solid var(--border)"
                    : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  {b.deviation_direction === "above" ? (
                    <TrendingUp size={13} color="#ef4444" />
                  ) : b.deviation_direction === "below" ? (
                    <TrendingDown size={13} color="#3b82f6" />
                  ) : (
                    <TrendingUp size={13} color="var(--muted-foreground)" />
                  )}
                  <span style={{ fontSize: "0.8125rem", fontWeight: 500, color: "var(--foreground)" }}>
                    {b.biomarker.toUpperCase()}
                  </span>
                  {b.deviation_direction && (
                    <span
                      style={{
                        fontSize: "0.6875rem",
                        color: b.deviation_direction === "above" ? "#ef4444" : "#3b82f6",
                        fontWeight: 600,
                      }}
                    >
                      {b.deviation_direction} baseline
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 12, flexShrink: 0 }}>
                  <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                    obs <strong style={{ color: "var(--foreground)" }}>{b.observed_value}</strong>
                  </span>
                  {b.posterior_mean != null && (
                    <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                      mean {fmt(b.posterior_mean, 2)}
                    </span>
                  )}
                  {b.z_score_squared != null && (
                    <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                      z² {fmt(b.z_score_squared, 2)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Older entries */}
      {older.length > 0 && (
        <div>
          <div style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 8 }}>
            Historical Records
          </div>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", margin: "0 0 8px" }}>
            Biomarker detail is only shown for the most recent anomaly detection.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {older.map((anomaly) => {
              const s = severityLabel(anomaly.anomaly_score);
              return (
                <div key={anomaly.id} className="timeline-item">
                  <div
                    className="timeline-dot"
                    style={{
                      background: s.cls.includes("elevated")
                        ? "#f97316"
                        : s.cls.includes("moderate")
                        ? "#f59e0b"
                        : "#22c55e",
                    }}
                  />
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                      <Clock size={11} color="var(--muted-foreground)" />
                      <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                        {anomaly.created_at}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className={`badge ${s.cls}`} style={{ fontSize: "0.625rem" }}>{s.label}</span>
                      <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                        {fmt(anomaly.anomaly_score, 3)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default ExplanationPanel;
