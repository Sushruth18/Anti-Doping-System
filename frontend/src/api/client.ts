import type {
  AnomalyDetail,
  AthleteListItem,
  AuditTimelineResponse,
  Case,
  DecisionInput,
  DecisionResponse,
  EvasionPattern,
  EvasionSimulationResponse,
  NewCaseInput,
  Recommendation,
  TrajectoryResponse,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function getAthletes(): Promise<AthleteListItem[]> {
  const response = await fetch(`${API_BASE_URL}/athletes`);
  if (!response.ok) {
    throw new Error(`GET /athletes failed: ${response.status}`);
  }
  return response.json() as Promise<AthleteListItem[]>;
}

export async function getAthleteTrajectory(id: number): Promise<TrajectoryResponse> {
  const response = await fetch(`${API_BASE_URL}/athletes/${id}/trajectory`);
  if (!response.ok) {
    throw new Error(`GET /athletes/${id}/trajectory failed: ${response.status}`);
  }
  return response.json() as Promise<TrajectoryResponse>;
}

export async function getAthleteAnomalies(id: number): Promise<AnomalyDetail[]> {
  const response = await fetch(`${API_BASE_URL}/athletes/${id}/anomalies`);
  if (!response.ok) {
    throw new Error(`GET /athletes/${id}/anomalies failed: ${response.status}`);
  }
  return response.json() as Promise<AnomalyDetail[]>;
}

export async function getAthleteRecommendation(id: number): Promise<Recommendation> {
  const response = await fetch(`${API_BASE_URL}/athletes/${id}/recommendation`);
  if (!response.ok) {
    throw new Error(`GET /athletes/${id}/recommendation failed: ${response.status}`);
  }
  return response.json() as Promise<Recommendation>;
}

export async function getSimulationEvasion(
  athleteId: number,
  pattern?: EvasionPattern
): Promise<EvasionSimulationResponse> {
  const params = new URLSearchParams({ athlete_id: String(athleteId) });
  if (pattern) params.set("pattern", pattern);
  const response = await fetch(`${API_BASE_URL}/simulation/evasion?${params}`);
  if (!response.ok) {
    throw new Error(`GET /simulation/evasion failed: ${response.status}`);
  }
  return response.json() as Promise<EvasionSimulationResponse>;
}

export async function createCase(input: NewCaseInput): Promise<Case> {
  const response = await fetch(`${API_BASE_URL}/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`POST /cases failed: ${response.status}`);
  }
  return response.json() as Promise<Case>;
}

export async function postDecision(
  caseId: number,
  input: DecisionInput
): Promise<DecisionResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`POST /cases/${caseId}/decision failed: ${response.status}`);
  }
  return response.json() as Promise<DecisionResponse>;
}

export async function getAuditTimeline(athleteId: number): Promise<AuditTimelineResponse> {
  const response = await fetch(`${API_BASE_URL}/audit/${athleteId}`);
  if (!response.ok) {
    throw new Error(`GET /audit/${athleteId} failed: ${response.status}`);
  }
  return response.json() as Promise<AuditTimelineResponse>;
}
