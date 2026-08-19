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
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
    <div className="rounded border border-border bg-card px-3 py-2 text-sm text-foreground shadow">
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
    <div className="rounded border border-border bg-card px-3 py-2 text-sm text-foreground shadow">
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
      <Card>
        <CardHeader>
          <CardTitle>Evasion Simulation</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center gap-3 py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-muted border-t-primary" />
            <span className="text-sm text-muted-foreground">Loading evasion simulation…</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !result) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Evasion Simulation</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTitle>Unable to load evasion simulation</AlertTitle>
          </Alert>
        </CardContent>
      </Card>
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
    <Card>
      <CardHeader>
        <CardTitle>Evasion Simulation</CardTitle>
        <CardDescription>
          Athlete {result.athlete_id} · biomarker <span className="font-medium">{result.biomarker}</span>{" "}
          · pattern <span className="font-medium">{result.pattern}</span> · {result.sample_count} samples
        </CardDescription>
      </CardHeader>

      <CardContent>
        <div>
          <h3 className="text-sm font-medium text-foreground">
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
                stroke="#B91C1C"
                strokeDasharray="4 4"
                label={{ value: "0.55 threshold", position: "insideTopRight", fill: "#B91C1C", fontSize: 12 }}
              />
              <Bar dataKey="score" name="anomaly_score" isAnimationActive={false}>
                {singleSampleData.map((d) => (
                  <Cell key={d.index} fill={d.flagged ? "#B91C1C" : "#64748B"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <Separator className="my-4" />

        <div>
          <h3 className="text-sm font-medium text-foreground">
            Cumulative (CUSUM) detection — {result.biomarker}
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={cusumData} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis domain={cusumYDomain} tickFormatter={(value: number) => value.toFixed(0)} />
              <Tooltip content={<CusumTooltip />} />
              <Legend />
              <ReferenceLine
                y={result.cusum_result.threshold}
                stroke="#0F172A"
                strokeDasharray="4 4"
                label={{
                  value: `threshold (h=${result.cusum_result.threshold})`,
                  position: "insideTopRight",
                  fill: "#0F172A",
                  fontSize: 12,
                }}
              />
              <Line
                dataKey="upper"
                stroke="#B91C1C"
                strokeWidth={2}
                dot
                isAnimationActive={false}
                name="C+ (upper)"
              />
              <Line
                dataKey="lower"
                stroke="#1D4ED8"
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
                  fill="#B91C1C"
                  stroke="#0F172A"
                  strokeWidth={2}
                  label={{ value: "flagged", position: "top", fill: "#B91C1C", fontSize: 12 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <Separator className="my-4" />

        <div className="text-sm">
          <p className="text-muted-foreground">
            Baseline established from first{" "}
            <span className="font-mono tabular-nums">{result.baseline_window_used}</span> samples;
            cumulative detection run across remaining{" "}
            <span className="font-mono tabular-nums">{result.detection_sample_count}</span> samples.
          </p>
          <p className="mt-1">
            Single-sample detection:{" "}
            <span className="font-mono tabular-nums">{flaggedCount}</span> of{" "}
            <span className="font-mono tabular-nums">{result.sample_count}</span> samples flagged.
          </p>
          <p className="mt-1">
            Cumulative (CUSUM) detection:{" "}
            {result.cusum_flagged ? (
              <>
                flagged at sample{" "}
                <span className="font-mono tabular-nums">
                  {(result.cusum_result.flagged_at_index ?? 0) + 1}
                </span>
              </>
            ) : (
              "not flagged with current thresholds"
            )}
            .
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export default EvasionSim;
