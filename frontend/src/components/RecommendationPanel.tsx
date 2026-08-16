import type { Recommendation } from "../types/api";

const ACTION_TYPE_LABELS: Record<Recommendation["action_type"], string> = {
  no_action: "No action",
  increase_monitoring: "Increased monitoring",
  target_test: "Targeted test",
  biological_passport_review: "Biological passport review",
  open_case: "Open case",
};

function actionTypeBadgeClasses(actionType: Recommendation["action_type"]): string {
  switch (actionType) {
    case "no_action":
      return "bg-gray-100 text-gray-600";
    case "increase_monitoring":
      return "bg-blue-100 text-blue-700";
    case "target_test":
      return "bg-amber-100 text-amber-700";
    case "biological_passport_review":
      return "bg-orange-100 text-orange-700";
    case "open_case":
      return "bg-red-100 text-red-700";
  }
}

interface RecommendationPanelProps {
  recommendation: Recommendation;
}

function RecommendationPanel({ recommendation }: RecommendationPanelProps) {
  return (
    <div>
      <h2 className="text-lg font-medium">Recommended Action</h2>

      <div className="mt-2 rounded border border-gray-300 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-sm font-medium ${actionTypeBadgeClasses(
              recommendation.action_type
            )}`}
          >
            {ACTION_TYPE_LABELS[recommendation.action_type]}
          </span>
          <span className="text-sm text-gray-500">
            value score {recommendation.value_score.toFixed(4)} · cost {recommendation.cost}
          </span>
        </div>

        <p className="mt-2 text-sm">{recommendation.explanation_text}</p>

        <div className="mt-2 text-sm text-gray-500">
          anomaly score {recommendation.anomaly_score.toFixed(2)}, uncertainty score{" "}
          {recommendation.uncertainty_score.toFixed(2)}
        </div>
      </div>
    </div>
  );
}

export default RecommendationPanel;
