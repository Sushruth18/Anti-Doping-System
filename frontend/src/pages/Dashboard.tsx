import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getAthletes } from "../api/client";
import type { AthleteListItem } from "../types/api";

function scoreBadgeClasses(priorityScore: number): string {
  const pct = priorityScore * 100;
  if (pct >= 90) return "bg-red-100 text-red-700";
  if (pct >= 70) return "bg-amber-100 text-amber-700";
  return "bg-green-100 text-green-700";
}

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

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Failed to load</div>;

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">Athlete Dashboard</h1>

        <ul className="flex flex-col gap-3">
          {athletes.map((athlete) => (
            <li
              key={athlete.id}
              onClick={() => navigate(`/athlete/${athlete.id}`)}
              className="cursor-pointer rounded-lg bg-white p-4 shadow-sm transition hover:shadow-md"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-lg font-semibold text-gray-900">{athlete.name}</span>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                    {athlete.sport}
                  </span>
                </div>

                {athlete.scored ? (
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-1 text-sm font-medium ${scoreBadgeClasses(
                      athlete.priority_score
                    )}`}
                  >
                    {(athlete.priority_score * 100).toFixed(0)}%
                  </span>
                ) : (
                  <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-1 text-sm font-medium text-gray-500">
                    Not yet scored
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default Dashboard;
