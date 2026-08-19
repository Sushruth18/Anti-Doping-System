import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrajectoryPoint } from "../types/api";

interface TrajectoryChartProps {
  points: TrajectoryPoint[];
}

interface ChartDatum extends TrajectoryPoint {
  // Recharts has no native "band between two values" mark — the standard
  // way to shade a confidence band is to stack an invisible Area up to
  // ci_lower, then stack a second, visible Area of just the remaining
  // range (ci_upper - ci_lower) on top of it.
  ci_range: number;
}

function TrajectoryTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ChartDatum }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;

  return (
    <div className="rounded border border-border bg-card px-3 py-2 text-sm text-foreground shadow">
      <div className="font-medium">{point.date}</div>
      <div className="text-red-600">Observed: {point.observed}</div>
      <div className="text-indigo-600">Expected: {point.expected}</div>
      <div className="text-gray-500">
        95% CI: [{point.ci_lower}, {point.ci_upper}]
      </div>
    </div>
  );
}

function TrajectoryChart({ points }: TrajectoryChartProps) {
  const data: ChartDatum[] = points.map((point) => ({
    ...point,
    ci_range: point.ci_upper - point.ci_lower,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={["auto", "auto"]} />
        <Tooltip content={<TrajectoryTooltip />} />
        <Legend />

        {/* Invisible spacer area — establishes the stack's floor at
            ci_lower without drawing anything. */}
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
        {/* Visible band — stacks on top of ci_lower up to ci_upper. */}
        <Area
          dataKey="ci_range"
          stackId="ci-band"
          stroke="none"
          fill="#1D4ED8"
          fillOpacity={0.2}
          isAnimationActive={false}
          name="95% CI band"
          tooltipType="none"
        />

        <Line
          dataKey="expected"
          stroke="#1D4ED8"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
          name="Expected (baseline)"
        />

        <Scatter dataKey="observed" fill="#B91C1C" name="Observed" />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default TrajectoryChart;
