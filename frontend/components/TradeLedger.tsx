import { Layers3 } from "lucide-react";
import type { PaperTradePreview } from "@/lib/api";

function pct(value: number | null | undefined) {
  if (value === null || value === undefined) return "n/a";
  return `${(value * 100).toFixed(2)}%`;
}

function localTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function TradeLedger({ trades }: { trades: PaperTradePreview[] }) {
  const groupedCounts = trades.reduce<Record<string, number>>((acc, trade) => {
    acc[trade.match_id] = (acc[trade.match_id] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h2 className="text-base font-semibold">Live Paper Trade Ledger</h2>
          <p className="mt-1 text-sm text-slate-600">Paper-trading registry fed by real-time preview positions.</p>
        </div>
        <Layers3 className="h-5 w-5 text-accent" />
      </div>
      {trades.length === 0 ? (
        <div className="grid min-h-48 place-items-center px-6 py-10 text-center">
          <div>
            <p className="text-sm font-medium">Awaiting real-time model evaluation loops...</p>
            <p className="mt-2 max-w-md text-sm text-slate-600">Syncing with Kalshi order lines. Paper-trade previews will appear here once the live evaluator records a viable edge.</p>
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-xs uppercase tracking-normal text-slate-600">
              <tr>
                <th className="px-5 py-3">Match / Selection</th>
                <th className="px-5 py-3">Model</th>
                <th className="px-5 py-3">Market</th>
                <th className="px-5 py-3">Edge</th>
                <th className="px-5 py-3">Scaled Kelly</th>
                <th className="px-5 py-3">Action</th>
                <th className="px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => {
                const clustered = groupedCounts[trade.match_id] > 1;
                return (
                  <tr key={trade.id} className={`border-t border-border ${clustered ? "border-l-4 border-l-accent bg-emerald-50/30" : ""}`}>
                    <td className="px-5 py-4">
                      <div className="font-medium">{trade.match_id}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                        <span>{trade.outcome}</span>
                        {clustered ? <span className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-700">same-match risk group</span> : null}
                      </div>
                    </td>
                    <td className="px-5 py-4">{pct(trade.estimated_probability)}</td>
                    <td className="px-5 py-4">{pct(trade.market_implied_probability)}</td>
                    <td className="px-5 py-4 font-medium text-signal">{pct(trade.edge)}</td>
                    <td className="px-5 py-4">{pct(trade.target_stake)}</td>
                    <td className="px-5 py-4">
                      <span className="whitespace-nowrap rounded-md bg-muted px-2 py-1 text-xs font-medium">{trade.action}</span>
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-slate-600">{localTime(trade.generated_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
