export type Recommendation = {
  market_id: string;
  match_id: string;
  outcome: string;
  status: "recommended" | "rejected";
  estimated_probability: number;
  market_implied_probability: number;
  edge: number;
  expected_value: number;
  fractional_kelly: number;
  confidence_score: number;
  risk_score: number;
  supporting_evidence: string[];
  key_statistics: Record<string, number>;
  simulation_summary: Record<string, number | string>;
  rejection_reasons: string[];
};

export type SchedulerJob = {
  name: string;
  interval_seconds: number;
  runs: number;
  failures: number;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_error: string | null;
};

export type SchedulerState = {
  running: boolean;
  jobs: SchedulerJob[];
};

export type PaperTradePreview = {
  id: string;
  match_id: string;
  market_id: string;
  outcome: string;
  edge: number;
  target_stake: number;
  estimated_probability: number | null;
  market_implied_probability: number | null;
  action: string;
  generated_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";
const INTERNAL_API_BASE = process.env.INTERNAL_API_BASE ?? API_BASE;

export async function getRecommendations(): Promise<Recommendation[]> {
  const res = await fetch(`${API_BASE}/recommendations`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("failed to load recommendations");
  }
  return res.json();
}

export async function getSchedulerState(): Promise<SchedulerState> {
  const res = await fetch(`${API_BASE}/scheduler`, { cache: "no-store" });
  if (!res.ok) {
    return { running: false, jobs: [] };
  }
  return res.json();
}

export async function getPaperTrades(): Promise<PaperTradePreview[]> {
  const res = await fetch(`${INTERNAL_API_BASE}/paper-trades`, { cache: "no-store" });
  if (!res.ok) {
    return [];
  }
  return res.json();
}
