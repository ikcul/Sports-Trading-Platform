import { Database, LineChart, ShieldCheck } from "lucide-react";
import { Metric } from "@/components/Metric";
import { RecommendationTable } from "@/components/RecommendationTable";
import { SchedulerStatus } from "@/components/SchedulerStatus";
import { TradeLedger } from "@/components/TradeLedger";
import { getPaperTrades, getRecommendations, getSchedulerState } from "@/lib/api";

export const dynamic = "force-dynamic";

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default async function Page() {
  const [recommendations, scheduler, trades] = await Promise.all([getRecommendations(), getSchedulerState(), getPaperTrades()]);
  const top = recommendations[0];
  const totalPositions = trades.length;
  const averageEdge = totalPositions > 0 ? trades.reduce((sum, trade) => sum + trade.edge, 0) / totalPositions : 0;
  const groupedMatches = new Set(trades.filter((trade) => trades.some((other) => other.match_id === trade.match_id && other.id !== trade.id)).map((trade) => trade.match_id)).size;

  return (
    <main className="min-h-screen">
      <header className="border-b border-border bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <h1 className="text-xl font-semibold">Quantitative Sports Trading</h1>
            <p className="mt-1 text-sm text-slate-600">Live paper-trading heartbeat, portfolio risk controls, and explainable model recommendations</p>
          </div>
          <SchedulerStatus state={scheduler} />
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6">
        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Live positions" value={String(totalPositions)} tone={totalPositions > 0 ? "signal" : "default"} />
          <Metric label="Max match exposure" value="5.0%" />
          <Metric label="Average edge" value={pct(averageEdge)} tone={averageEdge > 0 ? "signal" : "default"} />
          <Metric label="Grouped matches" value={String(groupedMatches)} />
        </section>
        <TradeLedger trades={trades} />
        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Sample estimated probability" value={pct(top.estimated_probability)} tone="signal" />
          <Metric label="Sample market implied" value={pct(top.market_implied_probability)} />
          <Metric label="Sample edge" value={pct(top.edge)} tone="signal" />
          <Metric label="Sample confidence" value={pct(top.confidence_score)} />
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
