import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getAthleteAnomalies, getAthleteTrajectory } from "../api/client";
import ExplanationPanel from "../components/ExplanationPanel";
import TrajectoryChart from "../components/TrajectoryChart";
import type { AnomalyDetail, BiomarkerTrajectory, TrajectoryResponse } from "../types/api";

function AthleteProfile() {
  const { id } = useParams<{ id: string }>();
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [selectedBiomarker, setSelectedBiomarker] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [anomalies, setAnomalies] = useState<AnomalyDetail[] | null>(null);
  const [anomaliesLoading, setAnomaliesLoading] = useState(true);
  const [anomaliesError, setAnomaliesError] = useState(false);

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

  if (loading) return <div>Loading...</div>;
  if (error || !trajectory) return <div>Failed to load</div>;

  const series: BiomarkerTrajectory[] = trajectory.series;
  const selected = series.find((s) => s.biomarker === selectedBiomarker) ?? series[0];

  return (
    <div>
      <h1>Athlete {trajectory.athlete_id} — Trajectory</h1>

      <div>
        {series.map((s) => (
          <button
            key={s.biomarker}
            onClick={() => setSelectedBiomarker(s.biomarker)}
            disabled={s.biomarker === selected?.biomarker}
          >
            {s.biomarker}
          </button>
        ))}
      </div>

      {selected && <TrajectoryChart points={selected.points} />}

      <div className="mt-6">
        {anomaliesLoading && <div>Loading...</div>}
        {!anomaliesLoading && anomaliesError && <div>Failed to load</div>}
        {!anomaliesLoading && !anomaliesError && anomalies && (
          <ExplanationPanel anomalies={anomalies} />
        )}
      </div>
    </div>
  );
}

export default AthleteProfile;
