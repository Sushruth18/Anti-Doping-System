import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
} from "recharts";
import { getSimulationEvasion } from "../api/client";
import type { EvasionSimulationResponse } from "../types/api";
import { useTheme } from "../lib/theme";
import {
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Activity,
  GitCommit,
  RefreshCw,
} from "lucide-react";

// Same cutoff applied in ExplanationPanel (0.55 = moderate/flagged threshold)
const SINGLE_SAMPLE_FLAG_THRESHOLD = 0.55;

interface EvasionSimProps {
  athleteId: number;
}

// ---------- aligned data shapes ----------

/** Entry in the single-sample chart: one row per historical sample */
interface SingleSampleDatum {
  seq: number;        // 1-based sample number
  label: string;      // "Sample N"
  score: number;
  flagged: boolean;
}

/**
 * Entry in the CUSUM chart.
 * The backend returns cusum_upper/lower starting from sample (baseline_window+1),
 * so we prepend null-padded rows for the baseline window samples so the
 * x-axis aligns with the single-sample chart.
 */
interface CusumDatum {
  seq: number;
  label: string;
  upper: number | null;
  lower: number | null;
  isBaseline: boolean;
}

// ---------- custom tooltips ----------

function SingleSampleTooltip({
  active,
  payload,
  isDark,
}: {
  active?: boolean;
  payload?: { payload: SingleSampleDatum }[];
  isDark: boolean;
}) {
  if (!active || !payload?.length) return null;
  const pt = payload[0].payload;
  return (
    <div
      style={{
        background: isDark ? "#0f172a" : "#ffffff",
        border: isDark ? "1px solid #1e293b" : "1px solid #cbd5e1",
        borderRadius: 8,
        padding: "10px 14px",
        boxShadow: isDark ? "0 8px 24px rgba(0,0,0,0.5)" : "0 4px 16px rgba(0,0,0,0.1)",
        fontSize: "0.75rem",
        color: isDark ? "#f8fafc" : "#0f172a",
        fontFamily: "var(--font-sans)",
        minWidth: 180,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{pt.label}</div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span style={{ color: "var(--muted-foreground)" }}>Anomaly Score</span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            color: pt.flagged ? "var(--destructive)" : "var(--muted-foreground)",
          }}
        >
          {pt.score.toFixed(4)}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 2 }}>
        <span style={{ color: "var(--muted-foreground)" }}>Threshold</span>
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--warning)" }}>0.5500</span>
      </div>
      <div style={{ marginTop: 6 }}>
        {pt.flagged ? (
          <span
            style={{
              color: "var(--destructive)",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <AlertTriangle size={12} /> FLAGGED — above threshold
          </span>
        ) : (
          <span
            style={{
              color: "var(--success)",
              fontWeight: 500,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <CheckCircle2 size={12} /> Within baseline range
          </span>
        )}
      </div>
    </div>
  );
}

function CusumTooltip({
  active,
  payload,
  isDark,
}: {
  active?: boolean;
  payload?: { payload: CusumDatum }[];
  isDark: boolean;
}) {
  if (!active || !payload?.length) return null;
  const pt = payload[0].payload;
  if (pt.isBaseline) {
    return (
      <div
        style={{
          background: isDark ? "#0f172a" : "#ffffff",
          border: isDark ? "1px solid #1e293b" : "1px solid #cbd5e1",
          borderRadius: 8,
          padding: "10px 14px",
          boxShadow: isDark ? "0 8px 24px rgba(0,0,0,0.5)" : "0 4px 16px rgba(0,0,0,0.1)",
          fontSize: "0.75rem",
          color: "var(--muted-foreground)",
          fontFamily: "var(--font-sans)",
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 4, color: isDark ? "#f8fafc" : "#0f172a" }}>{pt.label}</div>
        <div>Baseline window — used to establish mean &amp; std</div>
      </div>
    );
  }
  return (
    <div
      style={{
        background: isDark ? "#0f172a" : "#ffffff",
        border: isDark ? "1px solid #1e293b" : "1px solid #cbd5e1",
        borderRadius: 8,
        padding: "10px 14px",
        boxShadow: isDark ? "0 8px 24px rgba(0,0,0,0.5)" : "0 4px 16px rgba(0,0,0,0.1)",
        fontSize: "0.75rem",
        color: isDark ? "#f8fafc" : "#0f172a",
        fontFamily: "var(--font-sans)",
        minWidth: 200,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{pt.label}</div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 3 }}>
        <span style={{ color: "var(--destructive)" }}>C⁺ (Upper Sum)</span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--destructive)" }}>
          {pt.upper?.toFixed(3) ?? "—"}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span style={{ color: isDark ? "#3b82f6" : "#2563eb" }}>C⁻ (Lower Sum)</span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: isDark ? "#3b82f6" : "#2563eb" }}>
          {pt.lower?.toFixed(3) ?? "—"}
        </span>
      </div>
    </div>
  );
}

// ---------- main component ----------

export function EvasionSim({ athleteId }: EvasionSimProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const [result, setResult] = useState<EvasionSimulationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setErrorMsg(null);
    setResult(null);
    getSimulationEvasion(athleteId)
      .then((data) => setResult(data))
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        console.error("[EvasionSim] load failed:", msg);
        setErrorMsg(msg);
      })
      .finally(() => setLoading(false));
  }, [athleteId]);

  useEffect(() => {
    load();
  }, [load]);

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="panel animate-fade-in" style={{ padding: "36px 20px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
          }}
        >
          <div className="spinner" />
          <span style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>
            Loading detection analytics &amp; CUSUM simulation…
          </span>
        </div>
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────────────────
  if (errorMsg || !result) {
    return (
      <div className="panel" style={{ padding: "30px 24px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
          }}
        >
          <AlertTriangle
            size={20}
            color="var(--destructive)"
            style={{ flexShrink: 0, marginTop: 1 }}
          />
          <div>
            <div
              style={{
                fontSize: "0.875rem",
                fontWeight: 600,
                color: "var(--foreground)",
                marginBottom: 4,
              }}
            >
              Detection analytics unavailable
            </div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--muted-foreground)",
                marginBottom: 12,
              }}
            >
              The backend simulation endpoint could not be reached. Check that
              the API server is running and this athlete has sufficient sample
              history.
            </div>
            <button
              onClick={load}
              className="btn btn-secondary"
              style={{
                padding: "6px 14px",
                fontSize: "0.75rem",
                fontWeight: 600,
              }}
            >
              <RefreshCw size={13} />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Build chart data ───────────────────────────────────────────────────────

  // Graph 1: one entry per sample (full length = sample_count)
  const singleSampleData: SingleSampleDatum[] = result.single_sample_scores.map(
    (score, i) => ({
      seq: i + 1,
      label: `Sample ${i + 1}`,
      score,
      flagged: score >= SINGLE_SAMPLE_FLAG_THRESHOLD,
    })
  );

  // Graph 2: align cusum arrays with the full sample sequence.
  const baselineLen = result.baseline_window_used;
  const cusumData: CusumDatum[] = [];

  // Baseline placeholder rows
  for (let i = 0; i < baselineLen; i++) {
    cusumData.push({
      seq: i + 1,
      label: `Sample ${i + 1}`,
      upper: null,
      lower: null,
      isBaseline: true,
    });
  }
  // Detection window rows
  result.cusum_result.cusum_upper.forEach((upper, i) => {
    cusumData.push({
      seq: baselineLen + i + 1,
      label: `Sample ${baselineLen + i + 1}`,
      upper,
      lower: result.cusum_result.cusum_lower[i],
      isBaseline: false,
    });
  });

  // Y-domain for CUSUM chart
  const validCusum = cusumData.flatMap((d) => [d.upper ?? 0, d.lower ?? 0]);
  const cusumYDomain: [number, number] = [
    Math.min(0, ...validCusum),
    Math.max(result.cusum_result.threshold * 1.2, ...validCusum, 1),
  ];

  // Flagged trigger point for CUSUM
  const flaggedIdx = result.cusum_result.flagged_at_index;
  const flaggedPoint =
    flaggedIdx !== null && cusumData[baselineLen + flaggedIdx]
      ? cusumData[baselineLen + flaggedIdx]
      : null;

  const flaggedCount = singleSampleData.filter((d) => d.flagged).length;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* ── GRAPH 1: SINGLE-SAMPLE DETECTION ────────────────────────────── */}
      <div className="panel animate-fade-in">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <Activity size={16} color="var(--primary)" />
              Single-sample detection — per-sample anomaly score
            </div>
            <div
              style={{
                fontSize: "0.72rem",
                color: "var(--muted-foreground)",
                marginTop: 2,
              }}
            >
              Normalized Mahalanobis anomaly score per sample · Flag threshold = 0.55 ·{" "}
              {result.sample_count} samples total
            </div>
          </div>
          <span
            className={`badge ${flaggedCount > 0 ? "badge-critical" : "badge-clean"}`}
            style={{ fontSize: "0.6875rem", flexShrink: 0 }}
          >
            {flaggedCount} / {result.sample_count} Flagged
          </span>
        </div>

        <div className="panel-body" style={{ padding: "16px 14px 10px" }}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart
              data={singleSampleData}
              margin={{ top: 20, right: 28, bottom: 8, left: -8 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.06)"}
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 10.5, fontFamily: "var(--font-mono)" }}
                axisLine={{ stroke: isDark ? "#1e293b" : "#e2e8f0" }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 1]}
                tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 10.5, fontFamily: "var(--font-mono)" }}
                axisLine={{ stroke: isDark ? "#1e293b" : "#e2e8f0" }}
                tickLine={false}
                tickFormatter={(v: number) => v.toFixed(1)}
                label={{
                  value: "Anomaly Score",
                  angle: -90,
                  position: "insideLeft",
                  fill: isDark ? "#94a3b8" : "#64748b",
                  fontSize: 11,
                  dx: 14,
                }}
              />
              <Tooltip content={<SingleSampleTooltip isDark={isDark} />} cursor={{ fill: isDark ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.04)" }} />
              <Legend
                verticalAlign="top"
                align="right"
                wrapperStyle={{ paddingBottom: 6, fontSize: "0.72rem", color: isDark ? "#94a3b8" : "#64748b" }}
              />
              {/* Threshold reference line */}
              <ReferenceLine
                y={SINGLE_SAMPLE_FLAG_THRESHOLD}
                stroke="var(--destructive)"
                strokeDasharray="5 3"
                strokeWidth={1.5}
                label={{
                  value: "0.55 threshold",
                  position: "insideTopRight",
                  fill: "var(--destructive)",
                  fontSize: 10.5,
                  fontWeight: 600,
                }}
              />
              {/* Bars: colour-coded by flagged status */}
              <Bar
                dataKey="score"
                name="Anomaly Score"
                radius={[3, 3, 0, 0]}
                isAnimationActive
                animationDuration={700}
              >
                {singleSampleData.map((d) => (
                  <Cell
                    key={d.seq}
                    fill={
                      d.flagged
                        ? "rgba(239,68,68,0.75)"
                        : isDark
                        ? "rgba(100,116,139,0.45)"
                        : "rgba(148,163,184,0.4)"
                    }
                    stroke={d.flagged ? "var(--destructive)" : isDark ? "#475569" : "#cbd5e1"}
                    strokeWidth={0.5}
                  />
                ))}
              </Bar>
              {/* Trend line connecting all sample scores */}
              <Line
                type="monotone"
                dataKey="score"
                name="Score trajectory"
                stroke={isDark ? "#38bdf8" : "#0284c7"}
                strokeWidth={2}
                dot={(props: { cx?: number; cy?: number; payload?: SingleSampleDatum }) => {
                  const f = props.payload?.flagged;
                  return (
                    <circle
                      key={`ss-dot-${props.payload?.seq}`}
                      cx={props.cx}
                      cy={props.cy}
                      r={f ? 5.5 : 3}
                      fill={f ? "var(--destructive)" : isDark ? "#38bdf8" : "#0284c7"}
                      stroke="#fff"
                      strokeWidth={1.5}
                    />
                  );
                }}
                activeDot={{ r: 7 }}
                isAnimationActive
                animationDuration={750}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── GRAPH 2: CUSUM DETECTION ─────────────────────────────────────── */}
      <div className="panel animate-fade-in">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <GitCommit size={16} color={isDark ? "#38bdf8" : "#0284c7"} />
              Cumulative (CUSUM) detection —{" "}
              {result.biomarker.toUpperCase()}
            </div>
            <div
              style={{
                fontSize: "0.72rem",
                color: "var(--muted-foreground)",
                marginTop: 2,
              }}
            >
              Drift detector · Baseline: first {result.baseline_window_used} samples ·
              Detection window: {result.detection_sample_count} samples ·
              Threshold h = {result.cusum_result.threshold}
            </div>
          </div>
          <span
            className={`badge ${result.cusum_flagged ? "badge-critical" : "badge-clean"}`}
            style={{ fontSize: "0.6875rem", flexShrink: 0 }}
          >
            {result.cusum_flagged ? "CUSUM Drift Flagged" : "CUSUM Stable"}
          </span>
        </div>

        <div className="panel-body" style={{ padding: "16px 14px 10px" }}>
          {/* Baseline-window annotation */}
          <div
            style={{
              fontSize: "0.72rem",
              color: "var(--muted-foreground)",
              marginBottom: 8,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: 2,
                background: isDark ? "rgba(148,163,184,0.18)" : "rgba(148,163,184,0.25)",
                border: isDark ? "1px dashed #475569" : "1px dashed #94a3b8",
              }}
            />
            Shaded region = baseline calibration window (Samples 1–{result.baseline_window_used}) · CUSUM starts at Sample {result.baseline_window_used + 1}
          </div>

          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={cusumData}
              margin={{ top: 20, right: 28, bottom: 8, left: -8 }}
            >
              {/* Baseline window shaded background */}
              {cusumData
                .filter((d) => d.isBaseline)
                .map((d) => (
                  <ReferenceLine
                    key={`bref-${d.seq}`}
                    x={d.label}
                    stroke={isDark ? "rgba(148,163,184,0.12)" : "rgba(148,163,184,0.2)"}
                    strokeWidth={28}
                  />
                ))}

              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.06)"}
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 10.5, fontFamily: "var(--font-mono)" }}
                axisLine={{ stroke: isDark ? "#1e293b" : "#e2e8f0" }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={cusumYDomain}
                tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 10.5, fontFamily: "var(--font-mono)" }}
                axisLine={{ stroke: isDark ? "#1e293b" : "#e2e8f0" }}
                tickLine={false}
                tickFormatter={(v: number) => v.toFixed(1)}
                label={{
                  value: "Cumulative Sum",
                  angle: -90,
                  position: "insideLeft",
                  fill: isDark ? "#94a3b8" : "#64748b",
                  fontSize: 11,
                  dx: 14,
                }}
              />
              <Tooltip content={<CusumTooltip isDark={isDark} />} />
              <Legend
                verticalAlign="top"
                align="right"
                wrapperStyle={{ paddingBottom: 6, fontSize: "0.72rem", color: isDark ? "#94a3b8" : "#64748b" }}
              />

              {/* Decision threshold h */}
              <ReferenceLine
                y={result.cusum_result.threshold}
                stroke="var(--warning)"
                strokeDasharray="5 3"
                strokeWidth={1.5}
                label={{
                  value: `h = ${result.cusum_result.threshold}`,
                  position: "insideTopRight",
                  fill: "var(--warning)",
                  fontSize: 10.5,
                  fontWeight: 600,
                }}
              />

              {/* C+ upper cumulative sum */}
              <Line
                type="monotone"
                dataKey="upper"
                name="C⁺ Upper Cumulative Sum"
                stroke="var(--destructive)"
                strokeWidth={2.5}
                dot={{ r: 3.5, fill: "var(--destructive)", stroke: "#fff", strokeWidth: 1.5 }}
                activeDot={{ r: 6 }}
                isAnimationActive
                animationDuration={750}
                connectNulls={false}
              />
              {/* C- lower cumulative sum */}
              <Line
                type="monotone"
                dataKey="lower"
                name="C⁻ Lower Cumulative Sum"
                stroke={isDark ? "#3b82f6" : "#2563eb"}
                strokeWidth={2.5}
                dot={{ r: 3.5, fill: isDark ? "#3b82f6" : "#2563eb", stroke: "#fff", strokeWidth: 1.5 }}
                activeDot={{ r: 6 }}
                isAnimationActive
                animationDuration={750}
                connectNulls={false}
              />

              {/* Flagged trigger marker */}
              {flaggedPoint && (
                <ReferenceDot
                  x={flaggedPoint.label}
                  y={
                    (flaggedPoint.upper ?? 0) > result.cusum_result.threshold
                      ? flaggedPoint.upper!
                      : flaggedPoint.lower!
                  }
                  r={9}
                  fill="var(--destructive)"
                  stroke="#ffffff"
                  strokeWidth={2}
                  label={{
                    value: "⚑ Drift Trigger",
                    position: "top",
                    fill: "var(--destructive)",
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Footer summary */}
        <div
          style={{
            padding: "12px 20px",
            background: "var(--muted)",
            borderTop: "1px solid var(--border)",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
            fontSize: "0.75rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
            <Activity
              size={15}
              color="var(--primary)"
              style={{ marginTop: 2, flexShrink: 0 }}
            />
            <div>
              <span style={{ color: "var(--muted-foreground)" }}>
                Single-sample status:{" "}
              </span>
              <strong
                style={{ color: flaggedCount > 0 ? "var(--destructive)" : "var(--success)" }}
              >
                {flaggedCount} of {result.sample_count} samples flagged
              </strong>
              <div
                style={{
                  color: "var(--muted-foreground)",
                  fontSize: "0.6875rem",
                }}
              >
                {flaggedCount > 0
                  ? "Point-in-time anomalous spike detected."
                  : "No isolated sample exceeded 0.55 threshold."}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
            <ShieldAlert
              size={15}
              color={result.cusum_flagged ? "var(--destructive)" : "var(--success)"}
              style={{ marginTop: 2, flexShrink: 0 }}
            />
            <div>
              <span style={{ color: "var(--muted-foreground)" }}>
                CUSUM drift status:{" "}
              </span>
              <strong
                style={{
                  color: result.cusum_flagged ? "var(--destructive)" : "var(--success)",
                }}
              >
                {result.cusum_flagged
                  ? `Flagged at Sample ${(result.cusum_result.flagged_at_index ?? 0) + baselineLen + 1}`
                  : "Stable — no cumulative drift"}
              </strong>
              <div
                style={{
                  color: "var(--muted-foreground)",
                  fontSize: "0.6875rem",
                }}
              >
                {result.cusum_flagged
                  ? "Sustained multi-sample drift exceeds threshold (micro-dosing pattern)."
                  : "Cumulative sum remains within statistical baseline."}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EvasionSim;
