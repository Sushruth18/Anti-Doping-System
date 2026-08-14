import { useEffect, useState } from "react";
import { getAthletes } from "../api/client";
import type { AthleteListItem } from "../types/api";

function Dashboard() {
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
    <div>
      <ul>
        {athletes.map((athlete) => (
          <li key={athlete.id}>
            {athlete.name} — {athlete.sport} — priority {athlete.priority_score}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Dashboard;
