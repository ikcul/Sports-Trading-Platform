import { Activity, Database, LineChart, ShieldCheck } from "lucide-react";
import { Metric } from "@/components/Metric";
import { RecommendationTable } from "@/components/RecommendationTable";
import { getRecommendations } from "@/lib/api";

export const dynamic = "force-dynamic";

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default async function Page() {
  const recommendations = await getRecommendations();
  const top = recommendations[0];

  return (
    <main className="min-h-screen">
      <header className="border-b border-border bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-xl font-semibold">Quantitative Sports Trading</h1>
            <p className="mt-1 text-sm text-slate-600">Evidence graph, deterministic models, market comparison, explainable recommendations</p>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
            <Activity className="h-4 w-4 text-accent" />
            Live research loop
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6">
        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Estimated probability" value={pct(top.estimated_probability)} tone="signal" />
          <Metric label="Market implied" value={pct(top.market_implied_probability)} />
          <Metric label="Edge" value={pct(top.edge)} tone="signal" />
          <Metric label="Confidence" value={pct(top.confidence_score)} />
        </section>
        <section className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
          <RecommendationTable rows={recommendations} />
          <div className="panel p-5">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-accent" />
              <h2 className="text-base font-semibold">Recommendation Gate</h2>
            </div>
            <dl className="mt-5 grid gap-3 text-sm">
              <div className="flex justify-between"><dt>Expected value</dt><dd className="font-medium">{top.expected_value.toFixed(3)}</dd></div>
              <div className="flex justify-between"><dt>Risk score</dt><dd className="font-medium">{top.risk_score.toFixed(3)}</dd></div>
              <div className="flex justify-between"><dt>Model agreement</dt><dd className="font-medium">{pct(top.key_statistics.model_agreement)}</dd></div>
              <div className="flex justify-between"><dt>Calibration error</dt><dd className="font-medium">{pct(top.key_statistics.calibration_error)}</dd></div>
            </dl>
          </div>
        </section>
        <section className="grid gap-6 lg:grid-cols-3">
          <div className="panel p-5">
            <div className="flex items-center gap-2"><Database className="h-5 w-5 text-accent" /><h2 className="text-base font-semibold">Evidence Timeline</h2></div>
            <ul className="mt-4 space-y-3 text-sm">
              {top.supporting_evidence.map((fact) => <li key={fact} className="border-l-2 border-accent pl-3 text-slate-700">{fact}</li>)}
            </ul>
          </div>
          <div className="panel p-5">
            <div className="flex items-center gap-2"><LineChart className="h-5 w-5 text-accent" /><h2 className="text-base font-semibold">Simulation Summary</h2></div>
            <dl className="mt-4 grid gap-3 text-sm">
              <div className="flex justify-between"><dt>Runs</dt><dd className="font-medium">{top.simulation_summary.simulations}</dd></div>
              <div className="flex justify-between"><dt>Home win</dt><dd className="font-medium">{pct(Number(top.simulation_summary.home_win))}</dd></div>
              <div className="flex justify-between"><dt>Draw</dt><dd className="font-medium">{pct(Number(top.simulation_summary.draw))}</dd></div>
              <div className="flex justify-between"><dt>Away win</dt><dd className="font-medium">{pct(Number(top.simulation_summary.away_win))}</dd></div>
            </dl>
          </div>
          <div className="panel p-5">
            <h2 className="text-base font-semibold">Research Controls</h2>
            <div className="mt-4 grid gap-3 text-sm text-slate-700">
              <div className="rounded-md bg-muted p-3">LLMs can extract facts and contradictions.</div>
              <div className="rounded-md bg-muted p-3">Only deterministic models estimate probability.</div>
              <div className="rounded-md bg-muted p-3">The engine rejects weak, illiquid, or contradictory edges.</div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
