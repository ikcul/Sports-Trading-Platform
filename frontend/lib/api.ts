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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

export async function getRecommendations(): Promise<Recommendation[]> {
  const res = await fetch(`${API_BASE}/recommendations`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("failed to load recommendations");
  }
  return res.json();
}
