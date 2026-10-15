"""What-if / predictive perturbation experiments (SRS phase 3 extension).

The simulator is deterministic for a given seed, so uncertainty is modelled as
seed-to-seed variability of the stochastic demand stream rather than as a
hazard probability. Every projection produced here therefore carries explicit,
auditable assumptions:

    * the demand model, replenishment policy and network are unchanged from the
      base scenario;
    * exactly one perturbation is applied (custom asset impact(s) and/or a
      demand multiplier) and nothing else;
    * the perturbation is treated as certain inside its time window - these are
      conditional "if this happens, then ..." projections, not forecasts of
      hazard likelihood;
    * uncertainty bands are the min/median/max across the supplied seeds.

Nothing in this module mutates the base scenario tables: copies are made before
perturbation so results stay reproducible.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import engine
from . import metrics

DEFAULT_START = date(2027, 1, 1)


def build_whatif(base_scenario, days, seed, event=None, impacts=(),
                 demand_multiplier=1.0, demand_from_day=0, start_date=DEFAULT_START):
    """Return perturbed ``(tables, demand_map)`` without mutating the originals."""
    tables, demand_map = engine.prepare_tables(base_scenario, days, seed, start_date)

    if demand_multiplier and demand_multiplier != 1.0:
        demand_orders = [dict(row) for row in tables["demand_orders"]]
        for row in demand_orders:
            if row["day"] >= demand_from_day:
                row["quantity"] = int(round(row["quantity"] * demand_multiplier))
        tables["demand_orders"] = demand_orders
        demand_map = {
            (r["day"], r["factory_id"], r["output_sku"]): r["quantity"]
            for r in demand_orders
        }

    if impacts:
        iso = lambda d: (start_date + timedelta(days=d)).isoformat()
        event = dict(event or {})
        event_id = event.get("event_id", "W1")
        start_day = int(event.get("start_day", min(im["start_day"] for im in impacts)))
        duration = int(event.get("duration", 1))
        tables["hazard_events"] = list(tables["hazard_events"]) + [dict(
            event_id=event_id, scenario_id=f"{base_scenario}_whatif",
            hazard_type=event.get("hazard_type", "what_if"), hazard_subtype="",
            start_day=start_day, end_day=start_day + duration,
            start_date=iso(start_day), end_date_exclusive=iso(start_day + duration),
            latitude=float(event.get("latitude", 0.0)),
            longitude=float(event.get("longitude", 0.0)),
            intensity_metric=event.get("intensity_metric", "scenario_defined"),
            intensity=event.get("intensity", 0), unit=event.get("unit", ""),
            parent_event_id="", event_group_id=event_id, observed_day=start_day,
            uncertainty="what_if_perturbation_not_probability",
        )]
        injected = [dict(
            impact_id=f"WI{i + 1:03}", event_id=event_id, asset_id=im["asset_id"],
            start_day=int(im["start_day"]),
            end_day_exclusive=int(im["start_day"]) + int(im["duration"]),
            capacity_multiplier=float(im["capacity_multiplier"]),
            reason=im.get("reason", "what_if"),
        ) for i, im in enumerate(impacts)]
        tables["asset_impacts"] = list(tables["asset_impacts"]) + injected

    return tables, demand_map


def run_whatif(base_scenario="baseline", days=365, seed=42, **kwargs):
    """Run one perturbation and return ``(summary, outputs)``."""
    tables, demand_map = build_whatif(base_scenario, days, seed, **kwargs)
    ctx, ledger, backlog, outputs = engine.simulate(tables, demand_map, days, seed)
    units_ordered = sum(o["quantity"] for o in outputs["purchase_orders"])
    summary = metrics.summarize(
        f"{base_scenario}_whatif", seed, days, ctx, ledger, backlog, outputs, units_ordered
    )
    summary["backlog_peak"] = _backlog_peak(outputs)
    summary["recovery_day"] = _recovery_day(outputs)
    return summary, outputs


def _backlog_peak(outputs):
    peak = 0
    running = {}
    for row in outputs["production_actuals"]:
        running[row["day"]] = running.get(row["day"], 0) + row["backlog"]
    for value in running.values():
        peak = max(peak, value)
    return peak


def _recovery_day(outputs):
    days_with_backlog = sorted(
        row["day"] for row in outputs["production_actuals"] if row["backlog"] > 0
    )
    return days_with_backlog[-1] if days_with_backlog else 0


def monte_carlo(base_scenario="baseline", days=365, seeds=(42, 43, 44, 45, 46), **kwargs):
    """Return a list of ``(summary, outputs)`` across seeds for uncertainty bands."""
    return [run_whatif(base_scenario, days=days, seed=seed, **kwargs) for seed in seeds]
