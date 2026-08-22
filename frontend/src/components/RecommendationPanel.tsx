import type { Recommendation } from "../types/api";
import { CheckCircle, Eye, FlaskConical, BookOpen, FolderOpen } from "lucide-react";

const ACTION_TYPE_LABELS: Record<Recommendation["action_type"], string> = {
  no_action: "No Action",
  increase_monitoring: "Increased Monitoring",
  target_test: "Targeted Test",
  biological_passport_review: "Passport Review",
  open_case: "Open Case",
};

const ACTION_ICONS: Record<Recommendation["action_type"], React.ReactNode> = {
  no_action:                   <CheckCircle size={14} />,
  increase_monitoring:         <Eye size={14} />,
  target_test:                 <FlaskConical size={14} />,
  biological_passport_review:  <BookOpen size={14} />,
  open_case:                   <FolderOpen size={14} />,
};

function actionBadgeClass(actionType: Recommendation["action_type"]): string {
  switch (actionType) {
    case "no_action":                  return "badge-clean";
    case "increase_monitoring":        return "badge-info";
    case "target_test":                return "badge-moderate";
    case "biological_passport_review": return "badge-elevated";
    case "open_case":                  return "badge-critical";
  }
}

function ScoreRow({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.min(100, Math.round(value * 100));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: "0.6875rem", fontFamily: "var(--font-mono)", color, fontWeight: 600 }}>
          {value.toFixed(3)}
        </span>
      </div>
      <div className="score-bar-track" style={{ height: 3 }}>
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

interface RecommendationPanelProps {
  recommendation: Recommendation;
}

function RecommendationPanel({ recommendation }: RecommendationPanelProps) {
  const badgeCls = actionBadgeClass(recommendation.action_type);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Action badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span className={`badge ${badgeCls}`} style={{ fontSize: "0.75rem", padding: "4px 10px", gap: 5 }}>
          {ACTION_ICONS[recommendation.action_type]}
          {ACTION_TYPE_LABELS[recommendation.action_type]}
        </span>
        <span
          style={{
            fontSize: "0.6875rem",
            color: "var(--muted-foreground)",
            fontFamily: "var(--font-mono)",
          }}
        >
          cost {recommendation.cost}
        </span>
      </div>

      {/* Explanation */}
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--foreground)",
          lineHeight: 1.6,
          margin: 0,
          padding: "10px 12px",
          background: "var(--muted)",
          borderRadius: 6,
          border: "1px solid var(--border)",
        }}
      >
        {recommendation.explanation_text}
      </p>

      {/* Score breakdown */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          padding: "12px",
          background: "var(--muted)",
          borderRadius: 6,
          border: "1px solid var(--border)",
        }}
      >
        <div style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--muted-foreground)" }}>
          Score Breakdown
        </div>
        <ScoreRow
          label="Anomaly Score"
          value={recommendation.anomaly_score}
          color={recommendation.anomaly_score >= 0.70 ? "#ef4444" : recommendation.anomaly_score >= 0.55 ? "#f59e0b" : "#22c55e"}
        />
        <ScoreRow label="Value Score" value={recommendation.value_score} color="#3b82f6" />
        <ScoreRow label="Uncertainty Score" value={recommendation.uncertainty_score} color="#f97316" />
      </div>
    </div>
  );
}

export default RecommendationPanel;
