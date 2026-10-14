"""Scenario folder persistence and run manifests (SRS section 9).

Layout per scenario::

    scenarios/<scenario_id>/
    ├── config.json
    ├── master_data/*.csv     # configuration inputs
    ├── outputs/*.csv         # simulation results
    ├── reports/
    │   ├── summary.json
    │   └── data_dictionary.json
    └── runs/<run_id>/manifest.json

Scenario outputs are isolated on disk; each execution also records a run
manifest so that results are traceable to their inputs, seed and version.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SOFTWARE_VERSION = "1.0.0"

# Tables that must still emit a valid header when they contain no rows.
EMPTY_HEADERS = {
    "hazard_events": "event_id,scenario_id,hazard_type,hazard_subtype,start_day,"
                     "end_day,start_date,end_date_exclusive,latitude,longitude,"
                     "intensity_metric,intensity,unit,parent_event_id,"
                     "event_group_id,observed_day,uncertainty",
    "asset_impacts": "impact_id,event_id,asset_id,start_day,end_day_exclusive,"
                     "capacity_multiplier,reason",
}


def write_csv(folder, name, rows):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.csv"
    if rows:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    elif name in EMPTY_HEADERS:
        path.write_text(EMPTY_HEADERS[name] + "\n", encoding="utf-8")


def write_scenario(root, scenario, input_tables, output_tables, summary,
                   seed, days, start_date):
    root = Path(root)
    scenario_dir = root / scenario
    master_dir = scenario_dir / "master_data"
    output_dir = scenario_dir / "outputs"
    reports_dir = scenario_dir / "reports"

    for name, rows in input_tables.items():
        write_csv(master_dir, name, rows)
    for name, rows in output_tables.items():
        write_csv(output_dir, name, rows)

    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    dictionary = {}
    for name, rows in {**input_tables, **output_tables}.items():
        dictionary[name] = {
            "kind": "input" if name in input_tables else "output",
            "rows": len(rows),
            "columns": list(rows[0]) if rows else [],
        }
    (reports_dir / "data_dictionary.json").write_text(
        json.dumps(dictionary, indent=2), encoding="utf-8"
    )

    created = datetime.now(timezone.utc)
    config = dict(
        scenario_id=scenario,
        seed=seed,
        simulation_days=days,
        start_date=str(start_date),
        parameter_status="fictional_not_calibrated",
        created_utc=created.isoformat(timespec="seconds"),
    )
    (scenario_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    run_id = f"run_{created.strftime('%Y%m%dT%H%M%SZ')}_{seed}"
    manifest = dict(
        scenario_id=scenario,
        run_id=run_id,
        seed=seed,
        start_date=str(start_date),
        simulation_days=days,
        software_version=SOFTWARE_VERSION,
        input_data_version="synthetic_v1",
        execution_status="completed",
        generated_utc=created.isoformat(timespec="seconds"),
        row_counts={name: len(rows) for name, rows in {**input_tables, **output_tables}.items()},
        summary=summary,
    )
    run_dir = scenario_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return run_id
