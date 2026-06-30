import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { Recommendation } from "@/lib/api";

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export function RecommendationTable({ rows }: { rows: Recommendation[] }) {
  return (
    <div className="panel overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-base font-semibold">Expected Value Rankings</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase tracking-normal text-slate-600">
            <tr>
              <th className="px-5 py-3">Market</th>
              <th className="px-5 py-3">Outcome</th>
              <th className="px-5 py-3">Est.</th>
              <th className="px-5 py-3">Market</th>
              <th className="px-5 py-3">Edge</th>
              <th className="px-5 py-3">Kelly</th>
              <th className="px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.market_id} className="border-t border-border">
                <td className="whitespace-nowrap px-5 py-4 font-medium">{row.market_id}</td>
                <td className="px-5 py-4">{row.outcome}</td>
                <td className="px-5 py-4">{pct(row.estimated_probability)}</td>
                <td className="px-5 py-4">{pct(row.market_implied_probability)}</td>
                <td className="px-5 py-4 text-signal">{pct(row.edge)}</td>
                <td className="px-5 py-4">{pct(row.fractional_kelly)}</td>
                <td className="px-5 py-4">
                  <span className="inline-flex items-center gap-2">
                    {row.status === "recommended" ? <CheckCircle2 className="h-4 w-4 text-signal" /> : <AlertTriangle className="h-4 w-4 text-risk" />}
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
