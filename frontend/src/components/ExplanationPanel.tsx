import type { AnomalyDetail } from "../types/api";

// TODO: unvalidated placeholder tier thresholds pending real calibration
// data, same status as backend ANOMALY_SCORE_SCALE. Chosen so an athlete
// matching their own baseline (expected raw distance ~2.1-2.2 under the
// current SCALE=3.0 placeholder, i.e. score ~0.5) reads as "Low" rather
// than "Moderate" by default.
const SEVERITY_THRESHOLDS = { moderate: 0.6, elevated: 0.85 };

function severityLabel(anomalyScore: number): string {
  if (anomalyScore >= SEVERITY_THRESHOLDS.elevated) return "Elevated priority";
  if (anomalyScore >= SEVERITY_THRESHOLDS.moderate) return "Moderate priority";
  return "Low priority";
}

interface ExplanationPanelProps {
  anomalies: AnomalyDetail[];
}

function ExplanationPanel({ anomalies }: ExplanationPanelProps) {
  if (anomalies.length === 0) {
    return (
      <div>
        <h2 className="text-lg font-medium">Anomaly History</h2>
        <p className="text-gray-500">No anomaly history yet for this athlete.</p>
      </div>
    );
  }

  const [mostRecent, ...older] = anomalies;

  return (
    <div>
      <h2 className="text-lg font-medium">Anomaly History</h2>

      <div className="mt-2 rounded border border-gray-300 p-3">
        <div className="text-sm text-gray-500">{mostRecent.created_at}</div>
        <div className="font-medium">
          {severityLabel(mostRecent.anomaly_score)}{" "}
          <span className="text-sm text-gray-500">
            (score {mostRecent.anomaly_score.toFixed(2)}, raw distance{" "}
            {mostRecent.mahalanobis_distance.toFixed(2)})
          </span>
        </div>

        {mostRecent.contributing_biomarkers.length > 0 && (
          <ul className="mt-2 text-sm">
            {mostRecent.contributing_biomarkers.map((b) => (
              <li key={b.biomarker}>
                {b.biomarker}: {b.deviation_direction} baseline (observed{" "}
                {b.observed_value}, posterior mean {b.posterior_mean.toFixed(2)}, z²{" "}
                {b.z_score_squared.toFixed(2)})
              </li>
            ))}
          </ul>
        )}
      </div>

      {older.length > 0 && (
        <div className="mt-3">
          <p className="text-sm text-gray-500">
            Contributing biomarker detail is only available for the most recent
            anomaly — it isn't shown for older entries below, not because none were
            found.
          </p>
          <ul className="mt-1 text-sm">
            {older.map((anomaly) => (
              <li key={anomaly.id}>
                {anomaly.created_at} — {severityLabel(anomaly.anomaly_score)} (score{" "}
                {anomaly.anomaly_score.toFixed(2)})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default ExplanationPanel;
