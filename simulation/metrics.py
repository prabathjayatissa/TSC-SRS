"""KPI and summary calculation (SRS sections 6.2 and 10)."""
from __future__ import annotations


def summarize(scenario, seed, days, ctx, ledger, backlog, outputs, units_ordered):
    production = outputs["production_actuals"]
    shipments = outputs["shipments"]
    legs = outputs["shipment_legs"]

    total_demand = sum(r["new_demand"] for r in production)
    produced = sum(r["produced"] for r in production)
    total_capacity = sum(r["capacity"] for r in production)
    completed = [s for s in shipments if s["received_day"] != ""]
    total_lead = sum(s["received_day"] - s["dispatch_day"] for s in completed)
    transport_cost = sum(
        leg["quantity"] * ctx.linkmap[leg["link_id"]]["cost_per_unit"] for leg in legs
    )
    final_inventory_value = sum(
        qty * ctx.unit_value.get(sku, 0) for (_, sku), qty in ledger.balance.items()
    )
    stockout_days = len({r["day"] for r in production if r["backlog"] > 0})
    ending_backlog = sum(backlog.values())

    return dict(
        scenario=scenario,
        seed=seed,
        days=days,
        total_demand=total_demand,
        produced=produced,
        demand_fulfilment_rate=round(produced / total_demand, 4) if total_demand else 0.0,
        production_utilization=round(produced / total_capacity, 4) if total_capacity else 0.0,
        ending_backlog=ending_backlog,
        backlog_rate=round(ending_backlog / total_demand, 6) if total_demand else 0.0,
        stockout_days=stockout_days,
        final_inventory_value=round(final_inventory_value, 2),
        completed_shipments=len(completed),
        incomplete_shipments=len(shipments) - len(completed),
        units_ordered=units_ordered,
        mean_completed_lead_days=round(total_lead / max(1, len(completed)), 2),
        transport_cost_incurred=round(transport_cost, 2),
        validation="passed",
        right_censoring=(
            "unfinished orders and shipments retained; completed lead times alone "
            "are biased"
        ),
    )
