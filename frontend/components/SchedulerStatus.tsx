import { Activity, Clock3 } from "lucide-react";
import type { SchedulerState } from "@/lib/api";

export function SchedulerStatus({ state }: { state: SchedulerState }) {
  const intervalText = state.jobs.length
    ? state.jobs.map((job) => `${label(job.name)} ${job.interval_seconds}s`).join(" / ")
    : "scheduler intervals pending";

  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-3">
      <div
        className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
          state.running ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"
        }`}
      >
        <Activity className="h-4 w-4" />
        {state.running ? "Running" : "Gated"}
      </div>
      <div className="inline-flex min-w-0 items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-slate-600">
        <Clock3 className="h-4 w-4 text-accent" />
        <span className="truncate">{intervalText}</span>
      </div>
    </div>
  );
}

function label(value: string) {
  return value.replace("_", " ");
}
