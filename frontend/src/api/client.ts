import type { AthleteListItem } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function getAthletes(): Promise<AthleteListItem[]> {
  const response = await fetch(`${API_BASE_URL}/athletes`);
  if (!response.ok) {
    throw new Error(`GET /athletes failed: ${response.status}`);
  }
  return response.json() as Promise<AthleteListItem[]>;
}
