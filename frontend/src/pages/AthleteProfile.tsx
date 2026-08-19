import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { BlurFade } from "@/components/ui/blur-fade";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

// Shared by every inline "still loading this section" indicator on this page.
// Not swapped for Skeleton here — that's a bigger information-architecture
// change than this step's "wrap in Card, convert to Tabs" scope covers, so
// this keeps the exact prior spinner mechanism and only retokens its colors.
function SectionSpinner({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-8">
      <div className="h-6 w-6 animate-spin rounded-full border-4 border-muted border-t-primary" />
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}

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
      className="inline-flex w-fit items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
    >
      ← Back to Dashboard
    </Link>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-background px-4 py-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          {backLink}
          <Card>
            <CardContent className="flex items-center justify-center gap-3 py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-muted border-t-primary" />
              <span className="text-sm text-muted-foreground">Loading athlete data…</span>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (error || !trajectory) {
    return (
      <div className="min-h-screen bg-background px-4 py-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          {backLink}
          <Card>
            <CardContent>
              <Alert variant="destructive">
                <AlertTitle>Unable to load athlete data</AlertTitle>
              </Alert>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const series: BiomarkerTrajectory[] = trajectory.series;
  const selected = series.find((s) => s.biomarker === selectedBiomarker) ?? series[0];

  return (
    <div className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto flex max-w-4xl flex-col gap-4">
        {backLink}

        <h1 className="text-2xl font-bold text-foreground">Athlete {trajectory.athlete_id}</h1>

        <BlurFade>
          <Card>
            <CardContent>
              <Tabs
                value={selected?.biomarker ?? ""}
                onValueChange={(value) => setSelectedBiomarker(value as string)}
              >
                <TabsList>
                  {series.map((s) => (
                    <TabsTrigger key={s.biomarker} value={s.biomarker}>
                      {s.biomarker}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>

              {selected && (
                <div className="mt-4 overflow-x-auto">
                  <TrajectoryChart points={selected.points} />
                </div>
              )}
            </CardContent>
          </Card>
        </BlurFade>

        <Card>
          <CardContent>
            {anomaliesLoading && <SectionSpinner label="Loading anomaly history…" />}
            {!anomaliesLoading && anomaliesError && (
              <Alert variant="destructive">
                <AlertTitle>Unable to load athlete data</AlertTitle>
              </Alert>
            )}
            {!anomaliesLoading && !anomaliesError && anomalies && (
              <ExplanationPanel anomalies={anomalies} />
            )}
          </CardContent>
        </Card>

        <BlurFade>
          <EvasionSim athleteId={Number(id)} />
        </BlurFade>

        {recommendationLoading && (
          <Card>
            <CardContent>
              <SectionSpinner label="Loading recommendation…" />
            </CardContent>
          </Card>
        )}
        {!recommendationLoading && recommendationError && (
          <Card>
            <CardContent>
              <Alert variant="destructive">
                <AlertTitle>Unable to load athlete data</AlertTitle>
              </Alert>
            </CardContent>
          </Card>
        )}
        {!recommendationLoading && !recommendationError && recommendation && (
          <BlurFade>
            <RecommendationPanel recommendation={recommendation} />
          </BlurFade>
        )}

        <BlurFade>
          <DecisionPanel athleteId={Number(id)} />
        </BlurFade>

        <BlurFade>
          <AuditTimeline athleteId={Number(id)} />
        </BlurFade>
      </div>
    </div>
  );
}

export default AthleteProfile;
