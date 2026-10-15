# Taiwan IT Supply Chain Resilience Simulator (TSC-SRS)

A scenario-driven supply-chain simulation and decision-support prototype for a
synthetic Taiwan IT supply chain. It is implemented against the SRS
(Software Requirements Specification) as a modular Python simulation engine, a
validation layer, a reproducible scenario store, and an interactive Streamlit
dashboard.

> All coordinates are illustrative anchors, not surveyed assets. All parameters
> are fictional and are not calibrated to any real operation.

## Architecture

```
SAP/
├── simulation/                 # simulation engine package (stdlib only)
│   ├── engine.py               # daily orchestrator (SRS §6)
│   ├── master_data.py          # network / product / BOM configuration
│   ├── demand.py               # deterministic + stochastic demand
│   ├── disruptions.py          # hazard events + asset impacts + effect model
│   ├── inventory.py            # inventory balances and transaction ledger
│   ├── production.py           # BOM explosion and production
│   ├── procurement.py          # replenishment policy and order planning
│   ├── logistics.py            # capacities, shipment advancement, dispatch
│   ├── metrics.py              # KPI / summary calculation (SRS §10)
│   ├── whatif.py               # perturbation + Monte-Carlo what-if projections
│   └── storage.py              # scenario folders + run manifests (SRS §9)
├── validation/                 # data-integrity layer (SRS §5)
│   ├── schema.py               # required columns and value ranges
│   ├── foreign_keys.py         # FK + composite logical keys
│   ├── business_rules.py       # BOM cycles, route continuity, multipliers
│   └── report.py               # ValidationReport
├── app/frontend/               # Streamlit dashboard (SRS §7 screens)
│   ├── app.py                  # entry point (st.navigation)
│   ├── common.py               # shared data access + chart helpers
│   ├── analysis.py             # comparison, insight, forecast & map analysis
│   └── app_pages/              # Impact analysis · Resilience forecast · Dashboard ·
│                               # Results · World map · Master data ·
│                               # Scenario designer · Data explorer
├── scenarios/                  # scenario configuration, outputs and reports
│   └── <scenario_id>/
│       ├── config.json
│       ├── master_data/*.csv
│       ├── outputs/*.csv
│       ├── reports/{summary.json,data_dictionary.json}
│       └── runs/<run_id>/manifest.json
├── tests/                      # unittest suite
├── run_simulation.py           # CLI: generate / run scenarios
└── requirements.txt
```

## Quick start

```bash
# 1. (optional) create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. install dashboard dependencies
pip install -r requirements.txt

# 3. generate every scenario (baseline + five disruption scenarios)
python run_simulation.py --scenarios all --days 730 --seed 42

# 4. launch the dashboard (from the repository root)
streamlit run app/frontend/app.py
```

## Running simulations

```bash
# all scenarios with custom horizon and seed
python run_simulation.py --scenarios all --days 365 --seed 7

# a single scenario (baseline is always generated for comparison)
python run_simulation.py --scenarios compound

# list scenario ids
python run_simulation.py --list
```

Scenarios: `baseline`, `earthquake`, `typhoon`, `landslide`, `heat`, `compound`.

Each run writes isolated outputs to the scenario folder and records a run
manifest (`runs/<run_id>/manifest.json`) capturing the scenario id, run id,
seed, start date, duration, software version, input-data version and status.

## Validation

Every scenario is validated **before** the engine runs (foreign keys, composite
logical keys, BOM self-reference and cycles, route-leg continuity, non-negative
quantities, and expected capacity-multiplier ranges). Invalid data raises a
`ValueError` with a table/key/message report instead of producing misleading
results. The inventory ledger is additionally reconciled after the run.

```python
from simulation import engine
summary, inputs, outputs = engine.run_scenario("compound", days=730, seed=42)
```

## Dashboard screens

| Screen | Purpose |
|--------|---------|
| Impact analysis | Baseline vs compound KPIs, inventory/delay/production/backlog/cost charts, data-backed explanations of each disruption mechanism |
| Resilience forecast | Parameterised what-if projections (asset, window, capacity/demand multipliers) with stated assumptions, seed-based uncertainty bands and download |
| Dashboard | KPIs, demand/production/backlog, inventory, constraint source, disruption timeline |
| Results & comparison | Cross-scenario KPI comparison, time-series overlay, CSV/JSON exports |
| World map | deck.gl map of suppliers, factories, hubs, ports and routes with filters for scenario, time, factory, product, mode, country and node type; disruption overlay |
| Master data | Products, BOM, inventory policies, initial inventory |
| Scenario designer | Parameters, hazard events/impacts, capacity heatmap, in-process re-run |
| Data explorer | Browse and download every input and output table |

### Predictions and uncertainty

The **Resilience forecast** screen runs the deterministic engine under an explicit
perturbation (capacity multiplier on a chosen asset for a chosen window, optional
demand multiplier) and repeats it across several seeds of the stochastic demand
stream. Reported bands are **model uncertainty across seeds only** — they do not
represent hazard probability, calibrated parameter error, or structural change.
Every projection is labelled *"if this happens"*, not *"the probability that this
happens"*.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers engine reconciliation and reproducibility, and validation of
recorded keys, foreign keys, BOM cycles and value ranges.

## Mapping to the SRS roadmap

- **Phase 1 — data model and validation:** `simulation/master_data.py`,
  `validation/`, scenario folder management, synthetic dataset.
- **Phase 2 — simulation engine:** `simulation/` (inventory, production,
  procurement, logistics, metrics).
- **Phase 3 — disruption modelling:** `simulation/disruptions.py`, impact
  policy (minimum multiplier) and baseline-vs-disrupted experiments.
- **Phase 4 — web application:** `app/frontend/` dashboard.
- **Phase 5 — verification:** `tests/` plus run manifests for reproducibility.

## Notes and current limitations

- Storage is CSV-based with an explicit validation layer, as permitted for the
  first prototype; the logical schema maps directly onto the relational model.
- Outputs live in `outputs/` (latest run) with per-run manifests archived under
  `runs/`; a future iteration can write each run to its own output directory.
- Anomaly/yield, work-in-progress and multi-stage production are intentionally
  out of scope for the initial release.
