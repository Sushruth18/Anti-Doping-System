import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getAthlete,
  getAthleteAnomalies,
  getAthleteRecommendation,
  getAthleteTrajectory,
} from "../api/client";
import DecisionPanel from "../components/DecisionPanel";
import ExplanationPanel from "../components/ExplanationPanel";
import RecommendationPanel from "../components/RecommendationPanel";
import TrajectoryChart from "../components/TrajectoryChart";
import EvasionSim from "../components/EvasionSim";
import AuditTimeline from "../components/AuditTimeline";
import type {
  AnomalyDetail,
  AthleteDetail,
  BiomarkerTrajectory,
  Recommendation,
  TrajectoryResponse,
} from "../types/api";
import {
  ChevronLeft,
  Printer,
  ShieldAlert,
  Dna,
  Calendar,
  Layers,
  Activity,
  AlertTriangle,
  FileText,
  UserCheck,
  CheckCircle2,
} from "lucide-react";

/* ── Severity from anomaly score ───────────────────────────── */
function getSeverityFromScore(score: number): "critical" | "elevated" | "moderate" | "clean" {
  if (score >= 0.90) return "critical";
  if (score >= 0.70) return "elevated";
  if (score >= 0.55) return "moderate";
  return "clean";
}

const SEVERITY_DISPLAY: Record<string, { label: string; cls: string; desc: string }> = {
  critical: { label: "CRITICAL RISK", cls: "badge-critical", desc: "Immediate passport review / target testing advised" },
  elevated: { label: "ELEVATED RISK", cls: "badge-elevated", desc: "Significant deviation from Bayesian baseline" },
  moderate: { label: "MODERATE RISK", cls: "badge-moderate", desc: "Elevated biomarker drift requires monitoring" },
  clean:    { label: "NORMAL / CLEAN", cls: "badge-clean", desc: "All biological parameters within expected intervals" },
};

const BIOMARKER_LABELS: Record<string, string> = {
  hb:        "Hemoglobin (Hb)",
  hct:       "Hematocrit (HCT)",
  ret_pct:   "Reticulocyte % (RET%)",
  off_score: "OFF-Score",
  te_ratio:  "T/E Ratio",
};

/* ── Main component ────────────────────────────────────────── */
function AthleteProfile() {
  const { id } = useParams<{ id: string }>();
  const athleteId = Number(id);

  const [athlete, setAthlete] = useState<AthleteDetail | null>(null);
  const [athleteLoading, setAthleteLoading] = useState(true);

  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [selectedBiomarker, setSelectedBiomarker] = useState<string | null>(null);
  const [trajectoryLoading, setTrajectoryLoading] = useState(true);
  const [trajectoryError, setTrajectoryError] = useState(false);

  const [anomalies, setAnomalies] = useState<AnomalyDetail[] | null>(null);
  const [anomaliesLoading, setAnomaliesLoading] = useState(true);
  const [anomaliesError, setAnomaliesError] = useState(false);

  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recommendationLoading, setRecommendationLoading] = useState(true);

  useEffect(() => {
    if (!athleteId) return;

    // 1. Fetch Athlete profile info & baseline
    setAthleteLoading(true);
    getAthlete(athleteId)
      .then(setAthlete)
      .catch((err) => console.error("Error fetching athlete:", err))
      .finally(() => setAthleteLoading(false));

    // 2. Fetch Trajectory series
    setTrajectoryLoading(true);
    setTrajectoryError(false);
    getAthleteTrajectory(athleteId)
      .then((data) => {
        setTrajectory(data);
        setSelectedBiomarker(data.series[0]?.biomarker ?? null);
      })
      .catch(() => setTrajectoryError(true))
      .finally(() => setTrajectoryLoading(false));

    // 3. Fetch Anomalies
    setAnomaliesLoading(true);
    setAnomaliesError(false);
    getAthleteAnomalies(athleteId)
      .then(setAnomalies)
      .catch(() => setAnomaliesError(true))
      .finally(() => setAnomaliesLoading(false));

    // 4. Fetch Recommendation
    setRecommendationLoading(true);
    getAthleteRecommendation(athleteId)
      .then(setRecommendation)
      .catch((err) => console.error("Error fetching recommendation:", err))
      .finally(() => setRecommendationLoading(false));
  }, [athleteId]);

  const handlePrint = () => {
    window.print();
  };

  if (trajectoryLoading && athleteLoading) {
    return (
      <div style={{ padding: "28px 32px", maxWidth: "1400px", margin: "0 auto" }}>
        <div className="skeleton" style={{ width: 140, height: 20, marginBottom: 20 }} />
        <div className="skeleton" style={{ width: 340, height: 36, marginBottom: 12 }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: 96, borderRadius: 10 }} />
          ))}
        </div>
        <div className="skeleton" style={{ height: 380, borderRadius: 10 }} />
      </div>
    );
  }

  if (trajectoryError && !trajectory) {
    return (
      <div style={{ padding: "28px 32px", maxWidth: "1400px", margin: "0 auto" }}>
        <Link to="/" className="btn btn-secondary" style={{ marginBottom: 20 }}>
          <ChevronLeft size={14} /> Back to Dashboard
        </Link>
        <div
          className="panel"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "60px 20px",
            gap: 12,
          }}
        >
          <AlertTriangle size={32} color="#ef4444" />
          <h2 style={{ fontSize: "1.125rem", fontWeight: 700, margin: 0 }}>Unable to Load Athlete Dossier</h2>
          <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", margin: 0 }}>
            Could not retrieve data for Athlete #{athleteId}. Please verify that the backend API is running.
          </p>
        </div>
      </div>
    );
  }

  const series: BiomarkerTrajectory[] = trajectory?.series ?? [];
  const selected = series.find((s) => s.biomarker === selectedBiomarker) ?? series[0];

  /* Derive primary anomaly & risk status */
  const latestAnomaly = anomalies?.[0];
  const latestScore = latestAnomaly?.anomaly_score ?? recommendation?.anomaly_score ?? 0;
  const severityKey = getSeverityFromScore(latestScore);
  const severityInfo = SEVERITY_DISPLAY[severityKey] ?? SEVERITY_DISPLAY.clean;

  const sampleCount = athlete?.samples?.length ?? trajectory?.series[0]?.points?.length ?? 0;
  const latestSample = athlete?.samples && athlete.samples.length > 0 ? athlete.samples[athlete.samples.length - 1] : null;
  const earliestSample = athlete?.samples && athlete.samples.length > 0 ? athlete.samples[0] : null;

  return (
    <div style={{ padding: "24px 32px 60px", maxWidth: "1440px", margin: "0 auto" }}>
      {/* ── Official Print Header (Visible on print only) ─────── */}
      <div className="print-dossier-header" style={{ display: "none", marginBottom: 20, borderBottom: "2px solid #0f172a", paddingBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#64748b" }}>
              CONFIDENTIAL · NATIONAL ANTI-DOPING AGENCY (NADA)
            </div>
            <h1 style={{ fontSize: "1.375rem", fontWeight: 800, margin: "4px 0 2px", color: "#0f172a" }}>
              BIOLOGICAL PASSPORT INVESTIGATION DOSSIER
            </h1>
            <div style={{ fontSize: "0.8125rem", color: "#475569" }}>
              Subject: {athlete?.name ?? `Athlete #${athleteId}`} · ID: #{String(athleteId).padStart(3, "0")} · Sport: {athlete?.sport ?? "Athletics"}
            </div>
          </div>
          <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
            <div>DOSSIER REF: NADA-BP-{athleteId}-{new Date().getFullYear()}</div>
            <div>PRINTED: {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</div>
          </div>
        </div>
      </div>

      {/* ── Top Navigation & Actions Bar ─────────────────────── */}
      <div
        className="print-hide"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 18,
        }}
      >
        <Link
          to="/"
          className="btn btn-ghost"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 12px",
            fontSize: "0.8125rem",
          }}
        >
          <ChevronLeft size={16} />
          Back to Roster Dashboard
        </Link>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={handlePrint}
            className="btn btn-primary"
            title="Print Complete Athlete Dossier"
            style={{
              padding: "7px 16px",
              boxShadow: "0 2px 10px rgba(59, 130, 246, 0.3)",
              fontWeight: 600,
            }}
          >
            <Printer size={15} />
            Print Athlete Report
          </button>
        </div>
      </div>

      {/* ── SECTION A: ATHLETE HEADER & RISK ASSESSMENT ──────── */}
      <div
        className="panel animate-fade-in"
        style={{
          marginBottom: 20,
          background: "var(--header-gradient)",
          border: severityKey === "critical" ? "1px solid rgba(239, 68, 68, 0.4)" : "1px solid var(--border)",
        }}
      >
        <div style={{ padding: "24px 28px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 20,
            }}
          >
            {/* Left: Athlete Identity */}
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: "12px",
                  background: severityKey === "critical" ? "rgba(239, 68, 68, 0.15)" : "rgba(59, 130, 246, 0.15)",
                  border: severityKey === "critical" ? "1px solid rgba(239, 68, 68, 0.35)" : "1px solid rgba(59, 130, 246, 0.35)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Dna size={26} color={severityKey === "critical" ? "#ef4444" : "#3b82f6"} />
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <h1
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 800,
                      color: "var(--foreground)",
                      letterSpacing: "-0.02em",
                      margin: 0,
                      lineHeight: 1.1,
                    }}
                  >
                    {athlete?.name ? athlete.name : `Athlete #${athleteId}`}
                  </h1>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8125rem",
                      color: "var(--muted-foreground)",
                      background: "var(--muted)",
                      padding: "2px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--border)",
                    }}
                  >
                    #{String(athleteId).padStart(3, "0")}
                  </span>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    fontSize: "0.8125rem",
                    color: "var(--muted-foreground)",
                    marginTop: 6,
                    flexWrap: "wrap",
                  }}
                >
                  <span>Sport: <strong style={{ color: "var(--foreground)" }}>{athlete?.sport ?? "Athletics"}</strong></span>
                  <span>·</span>
                  <span>Age: <strong style={{ color: "var(--foreground)" }}>{athlete?.age ?? "—"} yrs</strong></span>
                  <span>·</span>
                  <span>Passport: <strong style={{ color: "#38bdf8" }}>Adaptive Bayesian Tracked</strong></span>
                  <span>·</span>
                  <span>Samples: <strong style={{ color: "var(--foreground)" }}>{sampleCount} recorded</strong></span>
                </div>
              </div>
            </div>

            {/* Right: Risk Assessment Block */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 18,
                background: "rgba(13, 20, 36, 0.8)",
                padding: "14px 20px",
                borderRadius: "10px",
                border: "1px solid var(--border)",
                boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
              }}
            >
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.6875rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted-foreground)" }}>
                  Risk Assessment
                </div>
                <div
                  style={{
                    fontSize: "1.75rem",
                    fontWeight: 800,
                    fontFamily: "var(--font-mono)",
                    lineHeight: 1.1,
                    color: severityKey === "critical" ? "#ef4444" : severityKey === "elevated" ? "#f97316" : severityKey === "moderate" ? "#f59e0b" : "#10b981",
                  }}
                >
                  {latestScore.toFixed(2)}
                </div>
                <div style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
                  Normalized Anomaly Score (0–1.0)
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
                <span
                  className={`badge ${severityInfo.cls} ${severityKey === "critical" ? "pulse-critical" : ""}`}
                  style={{ fontSize: "0.8125rem", padding: "5px 12px", fontWeight: 700 }}
                >
                  <ShieldAlert size={14} />
                  {severityInfo.label}
                </span>
                <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", maxWidth: 190 }}>
                  {severityInfo.desc}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── SECTION B: SUMMARY / KEY METRICS ─────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "14px",
          marginBottom: "22px",
        }}
      >
        {/* Metric 1: Anomaly Score */}
        <div className="stat-card">
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <Activity size={12} color={severityKey === "critical" ? "#ef4444" : "var(--primary)"} />
            Current Anomaly Score
          </div>
          <div
            className="stat-card-value"
            style={{
              fontFamily: "var(--font-mono)",
              color: severityKey === "critical" ? "#ef4444" : severityKey === "elevated" ? "#f97316" : severityKey === "moderate" ? "#f59e0b" : "#10b981",
            }}
          >
            {latestScore.toFixed(3)}
          </div>
          <div className="score-bar-wrap" style={{ marginTop: 2 }}>
            <div className="score-bar-track">
              <div
                className="score-bar-fill"
                style={{
                  width: `${Math.round(latestScore * 100)}%`,
                  background: severityKey === "critical" ? "#ef4444" : severityKey === "elevated" ? "#f97316" : severityKey === "moderate" ? "#f59e0b" : "#10b981",
                }}
              />
            </div>
          </div>
          <div className="stat-card-sub" style={{ marginTop: 2 }}>
            Threshold: 0.55 · Scale: 0.0 – 1.0
          </div>
        </div>

        {/* Metric 2: Raw Distance */}
        <div className="stat-card">
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <Layers size={12} color="#38bdf8" />
            Raw Mahalanobis Distance
          </div>
          <div className="stat-card-value" style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
            {latestAnomaly ? latestAnomaly.mahalanobis_distance.toFixed(2) : "—"}
          </div>
          <div className="stat-card-sub">
            Method: <strong style={{ color: "#60a5fa" }}>{latestAnomaly?.method ?? "mahalanobis_baseline"}</strong>
          </div>
        </div>

        {/* Metric 3: Baseline Prior */}
        <div className="stat-card">
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <UserCheck size={12} color="#10b981" />
            Baseline Model
          </div>
          <div className="stat-card-value" style={{ fontSize: "1.1875rem", color: "var(--foreground)", paddingTop: 2 }}>
            Adaptive Bayesian
          </div>
          <div className="stat-card-sub">
            5 Biomarkers correlated prior
          </div>
        </div>

        {/* Metric 4: Total Samples */}
        <div className="stat-card">
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <Calendar size={12} color="#f59e0b" />
            Tracked Samples
          </div>
          <div className="stat-card-value" style={{ fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
            {sampleCount}
          </div>
          <div className="stat-card-sub">
            {earliestSample && latestSample ? `${earliestSample.date} → ${latestSample.date}` : "Historical timeline"}
          </div>
        </div>
      </div>

      {/* ── SECTION C: BIOMARKER TRAJECTORY & EXPLANATION ────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 380px",
          gap: "20px",
          alignItems: "start",
          marginBottom: "24px",
        }}
      >
        {/* Left: Biomarker Trajectory Chart */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <Activity size={16} color="var(--primary)" />
                Biomarker Trajectory & Bayesian Confidence Bands
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: 2 }}>
                Observed sample points vs. 95% Bayesian posterior expectation interval
              </div>
            </div>

            {/* Biomarker Selector Tabs */}
            <div className="print-hide" style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {series.map((s) => (
                <button
                  key={s.biomarker}
                  onClick={() => setSelectedBiomarker(s.biomarker)}
                  className="btn"
                  style={{
                    padding: "4px 10px",
                    fontSize: "0.6875rem",
                    borderRadius: "5px",
                    background: s.biomarker === selected?.biomarker ? "var(--primary)" : "var(--muted)",
                    color: s.biomarker === selected?.biomarker ? "#ffffff" : "var(--muted-foreground)",
                    border: s.biomarker === selected?.biomarker ? "none" : "1px solid var(--border)",
                    fontWeight: s.biomarker === selected?.biomarker ? 600 : 500,
                  }}
                >
                  {s.biomarker.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {selected && (
            <div className="panel-body" style={{ padding: "16px 16px 12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, padding: "0 4px" }}>
                <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>
                  {BIOMARKER_LABELS[selected.biomarker] ?? selected.biomarker}
                  {selected.unit ? ` (${selected.unit})` : ""}
                </span>
                <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
                  {selected.points.length} observed samples plotted
                </span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <TrajectoryChart points={selected.points} />
              </div>
            </div>
          )}
        </div>

        {/* Right: Anomaly History & Biomarker Contributions */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <FileText size={15} color="#f59e0b" />
                Contributing Biomarker Breakdown
              </div>
            </div>
            <div className="panel-body">
              {anomaliesLoading && (
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 0" }}>
                  <div className="spinner" />
                  <span style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>Loading anomaly detail…</span>
                </div>
              )}
              {!anomaliesLoading && anomaliesError && (
                <p style={{ fontSize: "0.8125rem", color: "#ef4444", margin: 0 }}>Unable to load anomaly analysis.</p>
              )}
              {!anomaliesLoading && !anomaliesError && anomalies && (
                <ExplanationPanel anomalies={anomalies} />
              )}
            </div>
          </div>

          {/* Recommendation summary card */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <CheckCircle2 size={15} color="#10b981" />
                Recommended Action
              </div>
            </div>
            <div className="panel-body">
              {recommendationLoading ? (
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0" }}>
                  <div className="spinner" />
                  <span style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>Loading recommendation…</span>
                </div>
              ) : recommendation ? (
                <RecommendationPanel recommendation={recommendation} />
              ) : (
                <span style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>No recommendation generated.</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── SECTION D: THE TWO DETECTION GRAPHS ──────────────── */}
      <div style={{ marginBottom: "24px" }}>
        <div style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: "var(--foreground)", letterSpacing: "-0.01em", margin: 0 }}>
            Statistical Detection Analytics
          </h2>
          <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", margin: "3px 0 0" }}>
            Single-sample Mahalanobis score distribution alongside cumulative CUSUM drift detection
          </p>
        </div>

        <EvasionSim athleteId={athleteId} />
      </div>

      {/* ── SECTION E: AUDIT TIMELINE & DECISION WORKFLOW ────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 380px",
          gap: "20px",
          alignItems: "start",
        }}
      >
        {/* Left: Complete Audit Timeline */}
        <div>
          <AuditTimeline athleteId={athleteId} />
        </div>

        {/* Right: Investigator Decision Panel */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <ShieldAlert size={15} color="var(--primary)" />
              Investigator Decision Workflow
            </div>
          </div>
          <div className="panel-body">
            <DecisionPanel athleteId={athleteId} />
          </div>
        </div>
      </div>

      {/* ── Official Print Footer & Signatures (Visible on print only) ── */}
      <div
        className="print-dossier-footer"
        style={{
          display: "none",
          marginTop: 28,
          paddingTop: 16,
          borderTop: "2px solid #0f172a",
          pageBreakInside: "avoid",
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24, fontSize: "0.75rem", color: "#334155" }}>
          <div>
            <div style={{ fontWeight: 700, textTransform: "uppercase", marginBottom: 32 }}>Lead Investigator</div>
            <div style={{ borderTop: "1px solid #94a3b8", paddingTop: 4 }}>Signature & Badge ID</div>
          </div>
          <div>
            <div style={{ fontWeight: 700, textTransform: "uppercase", marginBottom: 32 }}>Medical Review Officer (MRO)</div>
            <div style={{ borderTop: "1px solid #94a3b8", paddingTop: 4 }}>Signature & Review Date</div>
          </div>
          <div>
            <div style={{ fontWeight: 700, textTransform: "uppercase", marginBottom: 32 }}>NADA Triage Committee</div>
            <div style={{ borderTop: "1px solid #94a3b8", paddingTop: 4 }}>Official Seal / Status: {severityInfo.label}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AthleteProfile;
