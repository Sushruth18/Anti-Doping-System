import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAthleteAnomalies, getAthleteRecommendation, getAthleteTrajectory } from "../api/client";
import AuditTimeline from "../components/AuditTimeline";
import DecisionPanel from "../components/DecisionPanel";
import EvasionSim from "../components/EvasionSim";
import ExplanationPanel from "../components/ExplanationPanel";
import RecommendationPanel from "../components/RecommendationPanel";
import TrajectoryChart from "../components/TrajectoryChart";
import type {
  AnomalyDetail,
  BiomarkerTrajectory,
  Recommendation,
  TrajectoryResponse,
} from "../types/api";

function AthleteProfile() {
  const { id } = useParams<{ id: string }>();
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [selectedBiomarker, setSelectedBiomarker] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [anomalies, setAnomalies] = useState<AnomalyDetail[] | null>(null);
  const [anomaliesLoading, setAnomaliesLoading] = useState(true);
  const [anomaliesError, setAnomaliesError] = useState(false);

  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recommendationLoading, setRecommendationLoading] = useState(true);
  const [recommendationError, setRecommendationError] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(false);
    getAthleteTrajectory(Number(id))
      .then((data) => {
        setTrajectory(data);
        setSelectedBiomarker(data.series[0]?.biomarker ?? null);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setAnomaliesLoading(true);
    setAnomaliesError(false);
    getAthleteAnomalies(Number(id))
      .then((data) => setAnomalies(data))
      .catch(() => setAnomaliesError(true))
      .finally(() => setAnomaliesLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setRecommendationLoading(true);
    setRecommendationError(false);
    getAthleteRecommendation(Number(id))
      .then((data) => setRecommendation(data))
      .catch(() => setRecommendationError(true))
      .finally(() => setRecommendationLoading(false));
  }, [id]);

  const backLink = (
    <Link
      to="/"
      className="inline-flex w-fit items-center gap-1 text-sm font-medium text-gray-600 hover:text-gray-900"
    >
      ← Back to Dashboard
    </Link>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 px-4 py-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          {backLink}
          <div className="flex items-center justify-center gap-3 rounded-lg bg-white p-12 shadow-sm">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-gray-200 border-t-gray-600" />
            <span className="text-sm text-gray-500">Loading athlete data…</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !trajectory) {
    return (
      <div className="min-h-screen bg-gray-50 px-4 py-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          {backLink}
          <div className="rounded-lg bg-white p-8 text-center shadow-sm">
            <p className="text-sm font-medium text-red-600">Unable to load athlete data</p>
          </div>
        </div>
      </div>
    );
  }

  const series: BiomarkerTrajectory[] = trajectory.series;
  const selected = series.find((s) => s.biomarker === selectedBiomarker) ?? series[0];

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto flex max-w-4xl flex-col gap-4">
        {backLink}

        <h1 className="text-2xl font-bold text-gray-900">Athlete {trajectory.athlete_id}</h1>

        <div className="rounded-lg bg-white p-4 shadow-sm">
          <div className="flex flex-wrap gap-2">
            {series.map((s) => (
              <button
                key={s.biomarker}
                onClick={() => setSelectedBiomarker(s.biomarker)}
                disabled={s.biomarker === selected?.biomarker}
                className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-600 transition hover:bg-gray-200 disabled:bg-gray-900 disabled:text-white disabled:hover:bg-gray-900"
              >
                {s.biomarker}
              </button>
            ))}
          </div>

          {selected && (
            <div className="mt-4 overflow-x-auto">
              <TrajectoryChart points={selected.points} />
            </div>
          )}
        </div>

        <div className="rounded-lg bg-white p-4 shadow-sm">
          {anomaliesLoading && (
            <div className="flex items-center justify-center gap-3 py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-gray-200 border-t-gray-600" />
              <span className="text-sm text-gray-500">Loading anomaly history…</span>
            </div>
          )}
          {!anomaliesLoading && anomaliesError && (
            <p className="py-4 text-center text-sm font-medium text-red-600">
              Unable to load athlete data
            </p>
          )}
          {!anomaliesLoading && !anomaliesError && anomalies && (
            <ExplanationPanel anomalies={anomalies} />
          )}
        </div>

        <div className="rounded-lg bg-white p-4 shadow-sm">
          <EvasionSim athleteId={Number(id)} />
        </div>

        <div className="rounded-lg bg-white p-4 shadow-sm">
          {recommendationLoading && (
            <div className="flex items-center justify-center gap-3 py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-gray-200 border-t-gray-600" />
              <span className="text-sm text-gray-500">Loading recommendation…</span>
            </div>
          )}
          {!recommendationLoading && recommendationError && (
            <p className="py-4 text-center text-sm font-medium text-red-600">
              Unable to load athlete data
            </p>
          )}
          {!recommendationLoading && !recommendationError && recommendation && (
            <RecommendationPanel recommendation={recommendation} />
          )}
        </div>

        <div className="rounded-lg bg-white p-4 shadow-sm">
          <DecisionPanel athleteId={Number(id)} />
        </div>

        <div className="rounded-lg bg-white p-4 shadow-sm">
          <AuditTimeline athleteId={Number(id)} />
        </div>
      </div>
    </div>
  );
}

export default AthleteProfile;
