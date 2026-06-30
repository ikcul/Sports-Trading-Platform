type MetricProps = {
  label: string;
  value: string;
  tone?: "default" | "signal" | "risk";
};

export function Metric({ label, value, tone = "default" }: MetricProps) {
  const toneClass = tone === "signal" ? "text-signal" : tone === "risk" ? "text-risk" : "text-foreground";
  return (
    <div className="panel p-4">
      <div className="text-xs font-medium uppercase tracking-normal text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}
