import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrajectoryPoint } from "../types/api";
import { useTheme } from "../lib/theme";

interface TrajectoryChartProps {
  points: TrajectoryPoint[];
}

interface ChartDatum extends TrajectoryPoint {
  ci_range: number;
}

function TrajectoryTooltip({
  active,
  payload,
  isDark,
}: {
  active?: boolean;
  payload?: { payload: ChartDatum }[];
  isDark: boolean;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;

  return (
    <div
      style={{
        background: isDark ? "#0f172a" : "#ffffff",
        border: isDark ? "1px solid #1e293b" : "1px solid #cbd5e1",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: "0.75rem",
        boxShadow: isDark ? "0 8px 24px rgba(0,0,0,0.5)" : "0 4px 16px rgba(0,0,0,0.1)",
        fontFamily: "var(--font-sans)",
        color: isDark ? "#f8fafc" : "#0f172a",
      }}
    >
      <div style={{ fontWeight: 600, color: isDark ? "#f8fafc" : "#0f172a", marginBottom: 6 }}>
        Sample Date: {point.date}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 3 }}>
        <span style={{ color: "var(--muted-foreground)" }}>Observed:</span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--destructive)" }}>
          {point.observed.toFixed(2)}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 3 }}>
        <span style={{ color: "var(--muted-foreground)" }}>Expected Mean:</span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: isDark ? "#60a5fa" : "#2563eb" }}>
          {point.expected.toFixed(2)}
        </span>
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          marginTop: 4,
          paddingTop: 4,
          borderTop: isDark ? "1px solid #1e293b" : "1px solid #e2e8f0",
        }}
      >
        <span style={{ color: "var(--muted-foreground)" }}>95% Bayesian CI:</span>
        <span style={{ fontFamily: "var(--font-mono)", color: isDark ? "#cbd5e1" : "#475569" }}>
          [{point.ci_lower.toFixed(2)}, {point.ci_upper.toFixed(2)}]
        </span>
      </div>
    </div>
  );
}

export function TrajectoryChart({ points }: TrajectoryChartProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const data: ChartDatum[] = points.map((point) => ({
    ...point,
    ci_range: point.ci_upper - point.ci_lower,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 12, right: 20, bottom: 4, left: -10 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke={isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 11, fontFamily: "var(--font-mono)" }}
          axisLine={{ stroke: isDark ? "#1e293b" : "#e2e8f0" }}
          tickLine={false}
        />
        <YAxis
          domain={["auto", "auto"]}
          tick={{ fill: isDark ? "#94a3b8" : "#64748b", fontSize: 11, fontFamily: "var(--font-mono)" }}
          axisLine={{ stroke: isDark ? "#1e293b" : "#e2e8f0" }}
          tickLine={false}
          width={45}
        />
        <Tooltip content={<TrajectoryTooltip isDark={isDark} />} />
        <Legend
          iconType="circle"
          iconSize={8}
          verticalAlign="top"
          align="right"
          wrapperStyle={{
            fontSize: "0.75rem",
            color: isDark ? "#94a3b8" : "#64748b",
            paddingBottom: "10px",
            fontFamily: "var(--font-sans)",
          }}
        />

        {/* Invisible spacer area to establish the lower CI floor */}
        <Area
          dataKey="ci_lower"
          stackId="ci-band"
          stroke="none"
          fill="transparent"
          isAnimationActive={false}
          legendType="none"
          name="ci_lower"
          tooltipType="none"
        />
        {/* Visible 95% Confidence Interval band */}
        <Area
          dataKey="ci_range"
          stackId="ci-band"
          stroke="none"
          fill={isDark ? "#3b82f6" : "#2563eb"}
          fillOpacity={isDark ? 0.16 : 0.12}
          isAnimationActive={true}
          animationDuration={700}
          name="95% Bayesian CI Band"
          tooltipType="none"
        />

        <Line
          dataKey="expected"
          stroke={isDark ? "#60a5fa" : "#2563eb"}
          strokeWidth={2}
          dot={false}
          isAnimationActive={true}
          animationDuration={700}
          name="Bayesian Posterior Expected"
          strokeDasharray="4 3"
        />

        <Line
          dataKey="observed"
          stroke="var(--destructive)"
          strokeWidth={2}
          dot={{ r: 4.5, fill: "var(--destructive)", strokeWidth: 1.5, stroke: "#ffffff" }}
          activeDot={{ r: 7, fill: "var(--destructive)" }}
          isAnimationActive={true}
          animationDuration={750}
          name="Observed Sample"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default TrajectoryChart;
