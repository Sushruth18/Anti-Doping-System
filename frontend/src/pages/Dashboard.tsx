import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BlurFade } from "@/components/ui/blur-fade";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getAthletes } from "../api/client";
import type { AthleteListItem } from "../types/api";

function scoreBadgeClasses(priorityScore: number): string {
  const pct = priorityScore * 100;
  if (pct >= 90) return "bg-destructive/10 text-destructive";
  if (pct >= 70) return "bg-warning/10 text-warning";
  return "bg-success/10 text-success";
}

const SKELETON_ROW_COUNT = 8;

function Dashboard() {
  const navigate = useNavigate();
  const [athletes, setAthletes] = useState<AthleteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    getAthletes()
      .then(setAthletes)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  const goToAthlete = (id: number) => navigate(`/athlete/${id}`);

  if (loading) {
    return (
      <div className="min-h-screen bg-background px-4 py-8">
        <div className="mx-auto max-w-5xl">
          <h1 className="mb-6 text-2xl font-bold text-foreground">Athlete Dashboard</h1>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Sport</TableHead>
                  <TableHead className="text-right">Age</TableHead>
                  <TableHead>Last Sample</TableHead>
                  <TableHead className="text-right">Priority</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: SKELETON_ROW_COUNT }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-20" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Skeleton className="ml-auto h-4 w-8" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Skeleton className="ml-auto h-5 w-20 rounded-full" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background px-4 py-8">
        <div className="mx-auto max-w-5xl">
          <h1 className="mb-6 text-2xl font-bold text-foreground">Athlete Dashboard</h1>
          <Alert variant="destructive">
            <AlertTitle>Failed to load</AlertTitle>
          </Alert>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-5xl">
        <h1 className="mb-6 text-2xl font-bold text-foreground">Athlete Dashboard</h1>

        <BlurFade>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Sport</TableHead>
                  <TableHead className="text-right">Age</TableHead>
                  <TableHead>Last Sample</TableHead>
                  <TableHead className="text-right">Priority</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {athletes.map((athlete) => (
                  <TableRow
                    key={athlete.id}
                    tabIndex={0}
                    role="button"
                    aria-label={`View profile for ${athlete.name}`}
                    onClick={() => goToAthlete(athlete.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        goToAthlete(athlete.id);
                      }
                    }}
                    className="cursor-pointer focus-visible:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                  >
                    <TableCell className="font-medium text-foreground">{athlete.name}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{athlete.sport}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {athlete.age}
                    </TableCell>
                    <TableCell className="font-mono tabular-nums text-muted-foreground">
                      {athlete.last_sample_date ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {athlete.scored ? (
                        <Badge className={scoreBadgeClasses(athlete.priority_score)}>
                          <span className="font-mono tabular-nums">
                            {(athlete.priority_score * 100).toFixed(0)}%
                          </span>
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Not yet scored</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </BlurFade>
      </div>
    </div>
  );
}

export default Dashboard;
