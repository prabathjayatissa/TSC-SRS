"""Daily simulation orchestrator (SRS sections 6, FR-10).

Daily processing order (baseline, documented and tested):
    1. activate events and compute effective asset/link capacity
    2. advance in-transit shipments and receive arrivals
    3. run production (consume components, fulfil backlog)
    4. every ``review_interval_days``: plan replenishment and raise orders
    5. dispatch ready orders into shipments
    6. record the day's inventory snapshot
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from . import demand as demand_mod
from . import disruptions as disruptions_mod
from . import inventory as inventory_mod
from . import logistics as logistics_mod
from . import master_data as master_data_mod
from . import metrics as metrics_mod
from . import production as production_mod
from . import procurement as procurement_mod
from . import storage
from .master_data import SCENARIOS

INPUT_TABLES = (
    "scenarios", "suppliers", "nodes", "products", "bill_of_materials",
    "factory_products", "initial_inventory", "inventory_policies",
    "transport_links", "routes", "route_legs", "demand_orders",
    "hazard_events", "asset_impacts",
)
OUTPUT_TABLES = (
    "purchase_orders", "shipments", "shipment_legs", "inventory_transactions",
    "inventory_snapshots", "production_actuals", "decisions",
)


class SimulationContext:
    """Derived lookups shared across the daily simulation steps."""

    def __init__(self, tables):
        self.tables = tables
        self.linkmap = {l["link_id"]: l for l in tables["transport_links"]}
        self.route_map = defaultdict(list)
        for leg in sorted(tables["route_legs"], key=lambda r: (r["route_id"], r["sequence"])):
            self.route_map[leg["route_id"]].append(leg["link_id"])
        self.bom_by_parent = defaultdict(list)
        for bom in tables["bill_of_materials"]:
            self.bom_by_parent[bom["parent_sku"]].append(bom)
        self.factories = list(master_data_mod.FACTORY_IDS)
        self.components = list(master_data_mod.COMPONENT_IDS)
        self.policies = {
            (p["factory_id"], p["sku_id"]): p for p in tables["inventory_policies"]
        }
        self.unit_value = {p["sku_id"]: p["unit_value"] for p in tables["products"]}


def prepare_tables(scenario, days, seed, start_date):
    tables = master_data_mod.build_master_data(scenario, days, seed, start_date)
    events, impacts = disruptions_mod.build_hazards(scenario, start_date)
    tables["hazard_events"] = events
    tables["asset_impacts"] = impacts
    demand_rows, demand_map = demand_mod.build_demand(
        days, seed, master_data_mod.FACTORY_IDS, start_date
    )
    tables["demand_orders"] = demand_rows
    return tables, demand_map


def simulate(tables, demand_map, days, seed):
    ctx = SimulationContext(tables)
    effects = disruptions_mod.EffectModel(tables["asset_impacts"])

    ledger = inventory_mod.InventoryLedger(tables["initial_inventory"])
    orders, shipments, legs = [], [], []
    production_records, snapshots, decisions = [], [], []
    backlog = {(f, f"P{p}"): 0 for f in ctx.factories for p in range(1, 4)}

    for day in range(days):
        capacities = logistics_mod.compute_capacities(ctx, effects, day)
        logistics_mod.advance_shipments(ctx, effects, day, shipments, legs, capacities, ledger)
        production_mod.run_production(ctx, effects, day, demand_map, backlog, ledger, production_records)
        if day % ctx.policies[ctx.factories[0], ctx.components[0]]["review_interval_days"] == 0:
            procurement_mod.plan_replenishment(ctx, day, ledger, orders, shipments, decisions)
        logistics_mod.dispatch_orders(ctx, effects, day, orders, shipments)
        inventory_mod.record_snapshot(day, ledger, snapshots)

    outputs = dict(
        purchase_orders=orders,
        shipments=[{k: v for k, v in s.items() if not k.startswith("_")} for s in shipments],
        shipment_legs=legs,
        inventory_transactions=ledger.transactions,
        inventory_snapshots=snapshots,
        production_actuals=production_records,
        decisions=decisions,
    )
    return ctx, ledger, backlog, outputs


def _assert_integrity(tables, ctx, ledger, backlog, outputs):
    assert inventory_mod.reconcile(tables["initial_inventory"], ledger), "inventory not reconciled"
    receipts = sum(
        t["quantity_delta"] for t in ledger.transactions if t["transaction_type"] == "receipt"
    )
    received_shipments = sum(
        s["quantity"] for s in outputs["shipments"] if s["received_day"] != ""
    )
    assert receipts == received_shipments, "receipts do not match received shipments"
    assert all(
        leg["arrival_day"] == "" or leg["arrival_day"] >= leg["departure_day"]
        for leg in outputs["shipment_legs"]
    ), "a shipment leg arrives before it departs"
    production = outputs["production_actuals"]
    assert (
        sum(r["new_demand"] for r in production) - sum(r["produced"] for r in production)
        == sum(backlog.values())
    ), "backlog does not reconcile with demand and production"


def run_scenario(scenario, days=730, seed=42, start_date=None, validate=True):
    """Simulate one scenario in memory.

    Returns ``(summary, input_tables, output_tables)``.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; expected one of {SCENARIOS}")
    if days < 1:
        raise ValueError("days must be positive")
    start_date = start_date or date(2027, 1, 1)

    tables, demand_map = prepare_tables(scenario, days, seed, start_date)

    if validate:
        from validation import validate_dataset
        report = validate_dataset(tables, expected_tables=INPUT_TABLES)
        if not report.ok:
            raise ValueError("validation failed:\n" + report.format())

    ctx, ledger, backlog, outputs = simulate(tables, demand_map, days, seed)
    _assert_integrity(tables, ctx, ledger, backlog, outputs)

    units_ordered = sum(o["quantity"] for o in outputs["purchase_orders"])
    summary = metrics_mod.summarize(
        scenario, seed, days, ctx, ledger, backlog, outputs, units_ordered
    )

    input_tables = {name: tables[name] for name in INPUT_TABLES}
    output_tables = {name: outputs[name] for name in OUTPUT_TABLES}
    return summary, input_tables, output_tables


def run_and_write(root, scenario, days=730, seed=42, start_date=None, validate=True):
    """Simulate a scenario and persist it under ``root`` as a scenario folder."""
    start_date = start_date or date(2027, 1, 1)
    summary, input_tables, output_tables = run_scenario(
        scenario, days=days, seed=seed, start_date=start_date, validate=validate
    )
    run_id = storage.write_scenario(
        root, scenario, input_tables, output_tables, summary, seed, days, start_date
    )
    return summary, run_id
