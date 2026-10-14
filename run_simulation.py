#!/usr/bin/env python3
"""Command-line interface for the Taiwan IT Supply Chain Resilience Simulator.

Examples
--------
Generate every scenario (baseline + disruptions) under ``scenarios/``::

    python run_simulation.py --days 730 --seed 42 --scenarios all

Generate a single scenario::

    python run_simulation.py --scenarios compound

List the available scenarios without running anything::

    python run_simulation.py --list
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from simulation import engine
from simulation.master_data import SCENARIOS


def parse_scenarios(values):
    if values == ["all"]:
        return list(SCENARIOS)
    unknown = [v for v in values if v not in SCENARIOS]
    if unknown:
        raise SystemExit(f"unknown scenario(s): {', '.join(unknown)}; available: {', '.join(SCENARIOS)}")
    # baseline is always generated first for comparison purposes.
    return list(dict.fromkeys(["baseline", *values]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default="scenarios", help="scenario output root")
    parser.add_argument("--days", type=int, default=730, help="simulation length in days")
    parser.add_argument("--seed", type=int, default=42, help="scenario random seed")
    parser.add_argument("--scenarios", nargs="+", default=["all"],
                        help="scenario ids, or 'all'")
    parser.add_argument("--start-date", default="2027-01-01", help="ISO start date")
    parser.add_argument("--no-validate", action="store_true",
                        help="skip pre-simulation validation (not recommended)")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(SCENARIOS))
        return 0

    if args.days < 1:
        raise SystemExit("--days must be positive")

    root = Path(args.root)
    start_date = date.fromisoformat(args.start_date)
    selected = parse_scenarios(args.scenarios)

    summaries, manifests = [], {}
    for scenario in selected:
        summary, run_id = engine.run_and_write(
            root, scenario, days=args.days, seed=args.seed,
            start_date=start_date, validate=not args.no_validate,
        )
        summaries.append(summary)
        manifests[scenario] = run_id
        print(f"[ok] {scenario:<12} run={run_id} "
              f"cost={summary['transport_cost_incurred']:,.0f} "
              f"lead={summary['mean_completed_lead_days']}d")

    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "comparison.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )
    (root / "scenario_index.json").write_text(
        json.dumps({"scenarios": selected, "runs": manifests,
                    "seed": args.seed, "days": args.days,
                    "start_date": str(start_date)}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
