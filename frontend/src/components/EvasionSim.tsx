import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getSimulationEvasion } from "../api/client";
import type { EvasionSimulationResponse } from "../types/api";

// Same "moderate" cutoff frontend/src/components/ExplanationPanel.tsx
// already applies to the normalized anomaly_score — reused here so the
// two panels agree on what "flagged" means, not a separately invented
// number.
const SINGLE_SAMPLE_FLAG_THRESHOLD = 0.55;

interface EvasionSimProps {
  athleteId: number;
}

interface SingleSampleDatum {
  index: number;
  label: string;
  score: number;
  flagged: boolean;
}

interface CusumDatum {
  index: number;
  label: string;
  upper: number;
  lower: number;
}

function SingleSampleTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: SingleSampleDatum }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded border border-gray-300 bg-white px-3 py-2 text-sm shadow">
      <div className="font-medium">{point.label}</div>
      <div className={point.flagged ? "text-red-600" : "text-gray-600"}>
        anomaly_score: {point.score.toFixed(3)}
      </div>
      {point.flagged && <div className="text-red-600">above 0.55 threshold</div>}
    </div>
  );
}

function CusumTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: CusumDatum }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded border border-gray-300 bg-white px-3 py-2 text-sm shadow">
      <div className="font-medium">{point.label}</div>
      <div className="text-red-600">C+ (upper): {point.upper.toFixed(3)}</div>
      <div className="text-blue-600">C- (lower): {point.lower.toFixed(3)}</div>
    </div>
  );
}

function EvasionSim({ athleteId }: EvasionSimProps) {
  const [result, setResult] = useState<EvasionSimulationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    setResult(null);
    getSimulationEvasion(athleteId)
      .then((data) => setResult(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [athleteId]);

  if (loading) {
    return (
      <div>
        <h2 className="text-lg font-medium">Evasion Simulation</h2>
        <div className="mt-2 flex items-center justify-center gap-3 rounded border border-gray-300 py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-gray-200 border-t-gray-600" />
          <span className="text-sm text-gray-500">Loading evasion simulation…</span>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div>
        <h2 className="text-lg font-medium">Evasion Simulation</h2>
        <div className="mt-2 rounded border border-gray-300 p-8 text-center">
          <p className="text-sm font-medium text-red-600">Unable to load evasion simulation</p>
        </div>
      </div>
    );
  }

  const singleSampleData: SingleSampleDatum[] = result.single_sample_scores.map(
    (score, index) => ({
      index,
      label: `Sample ${index + 1}`,
      score,
      flagged: score >= SINGLE_SAMPLE_FLAG_THRESHOLD,
    })
  );

  const cusumData: CusumDatum[] = result.cusum_result.cusum_upper.map((upper, index) => ({
    index,
    label: `Sample ${index + 1}`,
    upper,
    lower: result.cusum_result.cusum_lower[index],
  }));

  // Auto-scaling the y-axis to just the data range can leave the
  // threshold reference line off-chart entirely when detection_sample_count
  // is small (cusum sums haven't had room to climb) — the exact case this
  // chart exists to make legible. Force the domain to always cover the
  // threshold, with 15% headroom above it, while still expanding to fit
  // any data that legitimately exceeds it.
  const cusumValues = cusumData.flatMap((d) => [d.upper, d.lower]);
  const cusumYDomain: [number, number] = [
    Math.min(0, ...cusumValues),
    Math.max(result.cusum_result.threshold * 1.15, ...cusumValues),
  ];

  const flaggedIndex = result.cusum_result.flagged_at_index;
  const flaggedPoint =
    flaggedIndex !== null && cusumData[flaggedIndex]
      ? {
          index: flaggedIndex,
          label: cusumData[flaggedIndex].label,
          // Whichever side (upper/lower) actually crossed the threshold at
          // this index is the one worth marking; cusum.py's compute_cusum
          // doesn't report which side triggered, only the shared index.
          value:
            cusumData[flaggedIndex].upper > result.cusum_result.threshold
              ? cusumData[flaggedIndex].upper
              : cusumData[flaggedIndex].lower,
        }
      : null;

  const flaggedCount = singleSampleData.filter((d) => d.flagged).length;

  return (
    <div>
      <h2 className="text-lg font-medium">Evasion Simulation</h2>
      <p className="mt-1 text-sm text-gray-500">
        Athlete {result.athlete_id} · biomarker <span className="font-medium">{result.biomarker}</span>{" "}
        · pattern <span className="font-medium">{result.pattern}</span> · {result.sample_count} samples
      </p>

      <div className="mt-3 rounded border border-gray-300 p-3">
        <h3 className="text-sm font-medium text-gray-700">
          Single-sample detection (per-sample anomaly score)
        </h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={singleSampleData} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis domain={[0, 1]} />
            <Tooltip content={<SingleSampleTooltip />} />
            <Legend />
            <ReferenceLine
              y={SINGLE_SAMPLE_FLAG_THRESHOLD}
              stroke="#dc2626"
              strokeDasharray="4 4"
              label={{ value: "0.55 threshold", position: "insideTopRight", fill: "#dc2626", fontSize: 12 }}
            />
            <Bar dataKey="score" name="anomaly_score" isAnimationActive={false}>
              {singleSampleData.map((d) => (
                <Cell key={d.index} fill={d.flagged ? "#dc2626" : "#9ca3af"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 rounded border border-gray-300 p-3">
        <h3 className="text-sm font-medium text-gray-700">
          Cumulative (CUSUM) detection — {result.biomarker}
        </h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={cusumData} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis domain={cusumYDomain} />
            <Tooltip content={<CusumTooltip />} />
            <Legend />
            <ReferenceLine
              y={result.cusum_result.threshold}
              stroke="#111827"
              strokeDasharray="4 4"
              label={{
                value: `threshold (h=${result.cusum_result.threshold})`,
                position: "insideTopRight",
                fill: "#111827",
                fontSize: 12,
              }}
            />
            <Line
              dataKey="upper"
              stroke="#dc2626"
              strokeWidth={2}
              dot
              isAnimationActive={false}
              name="C+ (upper)"
            />
            <Line
              dataKey="lower"
              stroke="#2563eb"
              strokeWidth={2}
              dot
              isAnimationActive={false}
              name="C- (lower)"
            />
            {flaggedPoint && (
              <ReferenceDot
                x={flaggedPoint.label}
                y={flaggedPoint.value}
                r={7}
                fill="#dc2626"
                stroke="#111827"
                strokeWidth={2}
                label={{ value: "flagged", position: "top", fill: "#dc2626", fontSize: 12 }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 rounded border border-gray-300 p-3 text-sm">
        <p className="text-gray-500">
          Baseline established from first {result.baseline_window_used} samples; cumulative
          detection run across remaining {result.detection_sample_count} samples.
        </p>
        <p className="mt-1">
          Single-sample detection: {flaggedCount} of {result.sample_count} samples flagged.
        </p>
        <p className="mt-1">
          Cumulative (CUSUM) detection:{" "}
          {result.cusum_flagged
            ? `flagged at sample ${(result.cusum_result.flagged_at_index ?? 0) + 1}`
            : "not flagged with current thresholds"}
          .
        </p>
      </div>
    </div>
  );
}

export default EvasionSim;
