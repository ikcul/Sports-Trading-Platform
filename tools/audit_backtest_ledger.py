from __future__ import annotations

import argparse
import json
from pathlib import Path


def fmt_pct(value: float) -> str:
    return f"{value * 100:6.2f}%"


def money(value: float) -> str:
    return f"{value:8.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit executed backtest ledger entries.")
    parser.add_argument("path", type=Path, help="Backtest JSON path")
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    report = payload.get("report", payload)
    records = report.get("records", [])
    executed = [
        record
        for record in records
        if record.get("recommendation", {}).get("status") == "recommended"
        and float(record.get("recommendation", {}).get("kelly_fraction", 0.0)) > 0
    ]
    headers = ["Match ID", "As Of", "Outcome", "Model", "Market", "Edge", "Frac Kelly", "PnL"]
    rows = []
    for record in executed:
        rec = record["recommendation"]
        rows.append(
            [
                record["match_id"],
                record["as_of"],
                rec["outcome"],
                fmt_pct(float(rec["estimated_probability"])),
                fmt_pct(float(rec["market_implied_probability"])),
                fmt_pct(float(rec["edge"])),
                fmt_pct(float(rec["fractional_kelly"])),
                money(float(record["profit_loss"])),
            ]
        )
    widths = [max(len(str(row[i])) for row in [headers, *rows]) if rows else len(headers[i]) for i in range(len(headers))]
    print("| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    print("| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |")
    for row in rows:
        print("| " + " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) + " |")
    print(f"\nExecuted positions: {len(executed)}")


if __name__ == "__main__":
    main()
