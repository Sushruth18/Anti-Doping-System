import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NumberTicker } from "@/components/ui/number-ticker";
import type { Recommendation } from "../types/api";

const ACTION_TYPE_LABELS: Record<Recommendation["action_type"], string> = {
  no_action: "No action",
  increase_monitoring: "Increased monitoring",
  target_test: "Targeted test",
  biological_passport_review: "Biological passport review",
  open_case: "Open case",
};

// Badge ships default/secondary/destructive/outline/ghost/link only — there is
// no warning/success variant — so the two mid-severity tiers below carry token
// classes directly. Same escalation order as before, mapped onto the palette:
// muted -> primary -> warning -> warning(solid) -> destructive.
function actionTypeBadgeClasses(actionType: Recommendation["action_type"]): string {
  switch (actionType) {
    case "no_action":
      return "bg-muted text-muted-foreground";
    case "increase_monitoring":
      return "bg-primary/10 text-primary";
    case "target_test":
      return "bg-warning/10 text-warning";
    case "biological_passport_review":
      return "bg-warning text-warning-foreground";
    case "open_case":
      return "bg-destructive/10 text-destructive";
  }
}

interface RecommendationPanelProps {
  recommendation: Recommendation;
}

function RecommendationPanel({ recommendation }: RecommendationPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recommended Action</CardTitle>
      </CardHeader>

      <CardContent className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={actionTypeBadgeClasses(recommendation.action_type)}>
            {ACTION_TYPE_LABELS[recommendation.action_type]}
          </Badge>
          <span className="text-sm text-muted-foreground">
            value score{" "}
            <NumberTicker
              value={recommendation.value_score}
              decimalPlaces={4}
              className="font-mono tabular-nums text-muted-foreground"
            />{" "}
            · cost{" "}
            <NumberTicker
              value={recommendation.cost}
              decimalPlaces={0}
              className="font-mono tabular-nums text-muted-foreground"
            />
          </span>
        </div>

        <p className="text-sm">{recommendation.explanation_text}</p>

        <div className="text-sm text-muted-foreground">
          anomaly score{" "}
          <NumberTicker
            value={recommendation.anomaly_score}
            decimalPlaces={2}
            className="font-mono tabular-nums text-muted-foreground"
          />
          , uncertainty score{" "}
          <NumberTicker
            value={recommendation.uncertainty_score}
            decimalPlaces={2}
            className="font-mono tabular-nums text-muted-foreground"
          />
        </div>
      </CardContent>
    </Card>
  );
}

export default RecommendationPanel;
