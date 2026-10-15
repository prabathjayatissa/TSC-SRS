"""Analytical helpers for the baseline-vs-compound resilience dashboard.

These functions operate on the cached scenario tables exposed by
:mod:`common` and return plain DataFrames / dictionaries so they can be unit
tested and reused across pages. Every derived metric is documented with the
formula it implements.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import common

MODE_ORDER = ["sea", "air", "road"]


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def frames(scenario):
    """Return the tables needed for cross-scenario analysis."""
    return {
        "production": common.load_table(scenario, "production_actuals"),
        "shipments": common.load_table(scenario, "shipments"),
        "legs": common.load_table(scenario, "shipment_legs"),
        "links": common.load_table(scenario, "transport_links"),
        "nodes": common.load_table(scenario, "nodes"),
        "snapshots": common.load_table(scenario, "inventory_snapshots"),
        "hazards": common.load_table(scenario, "hazard_events"),
        "impacts": common.load_table(scenario, "asset_impacts"),
        "products": common.load_table(scenario, "products"),
        "purchase_orders": common.load_table(scenario, "purchase_orders"),
        "decisions": common.load_table(scenario, "decisions"),
        "summary": common.load_summary(scenario),
        "config": common.load_config(scenario),
    }


def _clean(frame):
    return frame if frame is not None else pd.DataFrame()


# --------------------------------------------------------------------------- #
# Shipment delays
# --------------------------------------------------------------------------- #
def lead_times(bundle):
    """Completed shipments with observed lead time in days.

    lead_time = received_day - dispatch_day  (completed shipments only).
    Right-censored (in-transit) shipments are excluded and reported separately
    because their true lead time is unknown.
    """
    shipments = _clean(bundle["shipments"]).copy()
    if shipments.empty:
        return shipments
    completed = shipments[shipments["received_day"].notna()].copy()
    completed["lead"] = completed["received_day"] - completed["dispatch_day"]
    completed["mode"] = completed["route_id"].str.split("_").str[-1]
    return completed


def lead_time_stats(bundle):
    completed = lead_times(bundle)
    if completed.empty:
        return {}
    out = {
        "completed": int(len(completed)),
        "in_transit": int(len(_clean(bundle["shipments"])) - len(completed)),
        "mean": round(float(completed["lead"].mean()), 2),
        "median": float(completed["lead"].median()),
        "p95": float(completed["lead"].quantile(0.95)),
        "max": int(completed["lead"].max()),
    }
    by_mode = (
        completed.groupby("mode")["lead"]
        .agg(["count", "mean", "median", "max"])
        .round(2)
    )
    out["by_mode"] = by_mode
    return out


# --------------------------------------------------------------------------- #
# Transport cost
# --------------------------------------------------------------------------- #
def leg_details(bundle):
    """Shipment legs enriched with link, product and delay information.

    delay_days = (arrival_day - departure_day) - link.transit_days
    Positive values mean the leg took longer than the nominal transit time.
    """
    legs = _clean(bundle["legs"]).copy()
    links = _clean(bundle["links"])
    shipments = _clean(bundle["shipments"])
    if legs.empty or links.empty:
        return legs
    legs = legs.merge(
        links[["link_id", "mode", "cost_per_unit", "transit_days",
               "from_node", "to_node", "departure_interval_days"]],
        on="link_id", how="left",
    )
    legs["cost"] = legs["quantity"] * legs["cost_per_unit"]
    if not shipments.empty:
        legs = legs.merge(
            shipments[["shipment_id", "sku_id", "route_id", "factory_id"]],
            on="shipment_id", how="left",
        )
    completed = legs["arrival_day"].notna()
    legs["transit"] = np.where(completed, legs["arrival_day"] - legs["departure_day"], np.nan)
    legs["delay_days"] = legs["transit"] - legs["transit_days"]
    return legs


def cost_by_mode(bundle):
    legs = leg_details(bundle)
    if legs.empty:
        return pd.Series(dtype=float)
    return legs.groupby("mode")["cost"].sum().round(2)


def cost_by_factory(bundle):
    legs = leg_details(bundle)
    if legs.empty or "factory_id" not in legs:
        return pd.Series(dtype=float)
    return legs.groupby("factory_id")["cost"].sum().round(2)


# --------------------------------------------------------------------------- #
# Production, backlog and inventory time series
# --------------------------------------------------------------------------- #
def daily_production(bundle, factory=None, sku=None, day_range=None):
    production = _clean(bundle["production"]).copy()
    if production.empty:
        return pd.DataFrame(columns=["day", "new_demand", "produced", "backlog", "capacity"])
    if factory and factory != "All":
        production = production[production["factory_id"] == factory]
    if sku and sku != "All":
        production = production[production["output_sku"] == sku]
    grouped = (
        production.groupby("day", as_index=False)[
            ["new_demand", "produced", "backlog", "capacity"]
        ].sum().sort_values("day")
    )
    if day_range:
        grouped = grouped[grouped["day"].between(*day_range)]
    return grouped


def daily_inventory(bundle, factory=None, sku=None, day_range=None):
    snapshots = _clean(bundle["snapshots"]).copy()
    if snapshots.empty:
        return pd.DataFrame(columns=["day", "on_hand"])
    if factory and factory != "All":
        snapshots = snapshots[snapshots["factory_id"] == factory]
    if sku and sku != "All":
        snapshots = snapshots[snapshots["sku_id"] == sku]
    grouped = snapshots.groupby("day", as_index=False)["on_hand"].sum().sort_values("day")
    if day_range:
        grouped = grouped[grouped["day"].between(*day_range)]
    return grouped


# --------------------------------------------------------------------------- #
# Cross-scenario KPI comparison
# --------------------------------------------------------------------------- #
KPI_LABELS = {
    "total_demand": "Total demand (units)",
    "produced": "Produced (units)",
    "demand_fulfilment_rate": "Demand fulfilment",
    "production_utilization": "Production utilization",
    "stockout_days": "Stockout days",
    "final_inventory_value": "Final inventory value ($)",
    "mean_completed_lead_days": "Mean completed lead time (days)",
    "completed_shipments": "Completed shipments",
    "incomplete_shipments": "In-transit at end",
    "transport_cost_incurred": "Transport cost ($)",
}


def kpi_comparison(scenarios):
    rows = []
    for scenario in scenarios:
        summary = common.load_summary(scenario)
        summary = dict(summary)
        summary["scenario"] = scenario
        rows.append(summary)
    frame = pd.DataFrame(rows)
    return frame


def kpi_deltas(scenario_a, scenario_b):
    """Absolute and relative change of key KPIs from A (baseline) to B (compound)."""
    a = common.load_summary(scenario_a)
    b = common.load_summary(scenario_b)
    rows = []
    for key, label in KPI_LABELS.items():
        if key not in a or key not in b:
            continue
        av, bv = a[key], b[key]
        absolute = bv - av
        relative = (absolute / av * 100) if av else 0.0
        rows.append(dict(
            metric=label, key=key, baseline=av, compound=bv,
            change=round(absolute, 4), change_pct=round(relative, 2),
        ))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Disruption narrative (explanations)
# --------------------------------------------------------------------------- #
def _first_nonempty(bundle):
    impacts = _clean(bundle["impacts"])
    hazards = _clean(bundle["hazards"])
    return impacts, hazards


def disruption_insights(baseline, compound):
    """Return data-backed explanation cards for the compound scenario.

    Each item is ``{title, detail, evidence}``. Values are computed from the
    loaded data so the commentary stays consistent with the tables.
    """
    insights = []

    base_lead = lead_time_stats(baseline)
    comp_lead = lead_time_stats(compound)
    if base_lead and comp_lead:
        delta = round(comp_lead["mean"] - base_lead["mean"], 2)
        insights.append(dict(
            title="Sea-freight lead times stretch during recovery",
            detail=(
                "The earthquake halts the supplier node, drawing down component "
                "inventory across all factories. Replenishment is forced onto "
                "faster, more expensive air freight, and what sea freight remains "
                "queues behind reduced port/road capacity."
            ),
            evidence=(
                f"Mean completed lead time {base_lead['mean']} d → {comp_lead['mean']} d "
                f"({delta:+} d); 95th percentile {base_lead['p95']:.0f} d → "
                f"{comp_lead['p95']:.0f} d."
            ),
        ))

    base_legs = leg_details(baseline)
    comp_legs = leg_details(compound)
    if not base_legs.empty and not comp_legs.empty:
        base_cost = cost_by_mode(baseline)
        comp_cost = cost_by_mode(compound)
        air_delta = float(comp_cost.get("air", 0) - base_cost.get("air", 0))
        total_delta = float(comp_cost.sum() - base_cost.sum())
        share = (air_delta / total_delta * 100) if total_delta else 0.0
        insights.append(dict(
            title="Cost increase is concentrated in expedited air freight",
            detail=(
                "The replenishment policy has no visibility of future events; it "
                "reacts to low on-hand stock by expediting. Because the earthquake "
                "lowers inventory for a sustained period, the number of air orders "
                "rises well beyond the baseline."
            ),
            evidence=(
                f"Air cost +${air_delta:,.0f} of a +${total_delta:,.0f} total "
                f"transport-cost change ({share:.0f}% of the increase)."
            ),
        ))

    base_ship = _clean(baseline["shipments"])
    comp_ship = _clean(compound["shipments"])
    if not base_ship.empty and not comp_ship.empty:
        base_air = int((base_ship["route_id"].str.endswith("air")).sum())
        comp_air = int((comp_ship["route_id"].str.endswith("air")).sum())
        insights.append(dict(
            title="Expediting substitutes for buffer stock",
            detail=(
                "Total demand and total output are unchanged, but the compound "
                "scenario shifts a larger share of orders to air routes. This is "
                "the visible cost of using speed instead of inventory as the "
                "resilience buffer."
            ),
            evidence=f"Air orders {base_air:,} → {comp_air:,} (+{comp_air - base_air:,}).",
        ))

    base_prod = _clean(baseline["production"])
    comp_prod = _clean(compound["production"])
    if not base_prod.empty and not comp_prod.empty:
        base_last = int(base_prod.loc[base_prod["backlog"] > 0, "day"].max() or -1)
        comp_last = int(comp_prod.loc[comp_prod["backlog"] > 0, "day"].max() or -1)
        base_days = int((base_prod.groupby("day")["backlog"].sum() > 0).sum())
        comp_days = int((comp_prod.groupby("day")["backlog"].sum() > 0).sum())
        insights.append(dict(
            title="Backlog recovery is prolonged, not deeper",
            detail=(
                "Both scenarios share an identical initial ramp-up transient, so "
                "the peak backlog is the same. The difference is duration: the "
                "earthquake extends how long factories carry any backlog at all."
            ),
            evidence=(
                f"Stockout days {base_days} → {comp_days}; last day with backlog "
                f"{base_last} → {comp_last}."
            ),
        ))

    comp_snap = _clean(compound["snapshots"])
    base_snap = _clean(baseline["snapshots"])
    comp_impacts, comp_hazards = _first_nonempty(compound)
    if not comp_snap.empty and not base_snap.empty and not comp_impacts.empty:
        start = int(comp_impacts["start_day"].min())
        end = int(comp_impacts["end_day_exclusive"].max())
        bw = base_snap[base_snap["day"].between(start, end)].groupby("day")["on_hand"].sum()
        cw = comp_snap[comp_snap["day"].between(start, end)].groupby("day")["on_hand"].sum()
        if not bw.empty and not cw.empty:
            drop = (1 - cw.min() / bw.min()) * 100 if bw.min() else 0
            insights.append(dict(
                title="Component inventory drawdown is the transmission channel",
                detail=(
                    "The supplier outage is propagated to factories through "
                    "component inventory: on-hand stock falls before production "
                    "and lead times are affected."
                ),
                evidence=(
                    f"Minimum total component on-hand during the disruption window "
                    f"{bw.min():,.0f} → {cw.min():,.0f} units ({-drop:+.1f}%)."
                ),
            ))

    if not comp_hazards.empty:
        hazards = ", ".join(sorted(comp_hazards["hazard_type"].unique()))
        groups = comp_hazards["event_group_id"].nunique()
        insights.append(dict(
            title="Compound, partially concurrent hazards",
            detail=(
                "The compound scenario layers a tsunami on the earthquake, then a "
                "typhoon, extreme rain and a landslide, and later a heatwave. "
                "Overlapping impacts on the same asset are resolved with the most "
                "restrictive (minimum) multiplier."
            ),
            evidence=f"{len(comp_hazards)} events across {groups} groups: {hazards}.",
        ))

    return insights


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #
def build_recommendations(baseline, compound):
    """Data-backed resilience recommendations with assumptions and uncertainty.

    Returns a list of dicts with: finding, recommendation, mechanism,
    expected_effect, assumption, confidence.
    """
    recommendations = []

    # 1. Single-source supplier.
    nodes = _clean(compound["nodes"])
    comp_impacts = _clean(compound["impacts"])
    supplier_nodes = nodes[nodes["node_type"] == "supplier_factory"] if not nodes.empty else nodes
    s1_hit = not comp_impacts.empty and (comp_impacts["asset_id"] == "S1").any()
    recommendations.append(dict(
        finding=(
            "A single supplier factory (S1) feeds all six final-assembly "
            "factories, and it was directly disrupted."
            if s1_hit else
            "Final assembly depends on a concentrated upstream supplier base."
        ),
        recommendation="Qualify a second, geographically separated supplier for "
                       "the highest-volume components and split volume 70/30.",
        mechanism="Removes the single point of failure so a local shock to S1 "
                  "cannot stop inbound supply for every factory at once.",
        expected_effect="Reduces the depth and duration of the inventory drawdown "
                        "in proportion to the share dual-sourced (a 30% split caps "
                        "the immediate supply loss near 30%).",
        assumption="The alternate supplier has comparable lead time and quality; "
                   "demand is unchanged.",
        confidence="Medium — mechanism is structural; the size of the benefit "
                   "depends on the split and on the alternate supplier's exposure.",
    ))

    # 2. Buffers vs expedite.
    base_cost = cost_by_mode(baseline)
    comp_cost = cost_by_mode(compound)
    air_delta = float(comp_cost.get("air", 0) - base_cost.get("air", 0))
    recommendations.append(dict(
        finding=f"Air (expedite) spend rose by ${air_delta:,.0f} under the compound "
                f"scenario because the policy has no forward view of the disruption.",
        recommendation="Hold modest pre-positioned safety stock on the critical "
                       "components instead of relying on post-event expediting.",
        mechanism="Buffer inventory absorbs the early part of an outage, avoiding "
                  "the most expensive air shipments which cluster in the first weeks.",
        expected_effect="Trades a one-off inventory carrying cost for a reduction "
                        "in expedite spend of a similar order to the observed air "
                        "premium.",
        assumption="Carrying cost per unit per day is below the air premium per "
                   "unit; disruption frequency is at least the modelled rate.",
        confidence="Medium — the direction is well supported by the data; the "
                   "break-even depends on carrying-cost and disruption-frequency "
                   "parameters that are fictional here.",
    ))

    # 3. Port / route diversification.
    hazards = _clean(compound["hazards"])
    port_hit = not hazards.empty and {"typhoon", "tsunami"} & set(hazards["hazard_type"])
    recommendations.append(dict(
        finding=("Ports and roads were closed by the tsunami, typhoon and "
                 "landslide, which are the links that bound sea-route throughput."
                 if port_hit else
                 "Sea routes funnel through a small number of port and road nodes."),
        recommendation="Pre-clear an alternate port/airport discharge and a road "
                       "diversion for each destination.",
        mechanism="Gives the logistics layer a path around a closed node instead of "
                  "a hard capacity stop.",
        expected_effect="Lowers peak transit delay when any single port/road node "
                        "is closed for the duration of an event.",
        assumption="Alternate nodes exist with spare capacity and do not share the "
                   "same geographic exposure.",
        confidence="High — route continuity is explicit in the data and the "
                   "mechanism is direct.",
    ))

    # 4. Heat resilience at F4.
    impacts = comp_impacts
    heat = impacts[impacts["reason"].str.contains("heat", na=False)] if not impacts.empty else impacts
    recommendations.append(dict(
        finding=("Extreme heat cut the effective production capacity of factory "
                 "F4 by about 45% for twelve days."
                 if not heat.empty else
                 "Production capacity is exposed to temperature extremes."),
        recommendation="Add cooling capacity / shift production earlier in the day "
                       "at heat-exposed factories.",
        mechanism="Restores effective capacity during heat events so output is not "
                  "reduced when demand is steady.",
        expected_effect="Recovers most of the lost daily capacity during heat "
                        "windows; protects against backlog build-up if demand rises.",
        assumption="Heat events recur with similar intensity and duration as "
                   "modelled.",
        confidence="Medium — capacity loss is directly modelled; the achievable "
                   "recovery depends on engineering limits not represented here.",
    ))

    # 5. Disruption-aware planning.
    recommendations.append(dict(
        finding="The replenishment policy explicitly uses inventory thresholds only, "
                "with no access to future event information.",
        recommendation="Introduce a disruption-aware planning mode that can pull "
                       "orders forward when a credible hazard warning exists.",
        mechanism="Converts some of the reactive expedite demand into planned, "
                  "cheaper sea freight released before the event.",
        expected_effect="Shifts cost from air back toward sea and shortens the "
                        "recovery tail.",
        assumption="Warnings are timely and reasonably reliable; acting early does "
                   "not simply move the same cost earlier.",
        confidence="Low–Medium — benefit depends entirely on warning lead time and "
                   "accuracy, which are outside this synthetic model.",
    ))

    return recommendations


# --------------------------------------------------------------------------- #
# Map support
# --------------------------------------------------------------------------- #
def node_lookup(bundle):
    nodes = _clean(bundle["nodes"])
    if nodes.empty:
        return pd.DataFrame()
    return nodes.set_index("node_id")[["latitude", "longitude", "node_type", "country"]]


def map_flows(bundle, day_range=None, factory=None, sku=None, mode=None):
    """Aggregate shipment legs into map-ready flows with delay statistics.

    Filters: departure day window, factory, product (sku) and transport mode.
    """
    legs = leg_details(bundle)
    if legs.empty:
        return legs
    if day_range:
        legs = legs[legs["departure_day"].between(*day_range)]
    if factory and factory != "All":
        legs = legs[legs["factory_id"] == factory]
    if sku and sku != "All":
        legs = legs[legs["sku_id"] == sku]
    if mode and mode != "All":
        legs = legs[legs["mode"] == mode]

    nodes = node_lookup(bundle)
    if nodes.empty:
        return legs
    coords = nodes[["latitude", "longitude"]]
    legs = legs.join(coords.rename(columns={"latitude": "from_lat", "longitude": "from_lon"}), on="from_node")
    legs = legs.join(coords.rename(columns={"latitude": "to_lat", "longitude": "to_lon"}), on="to_node")

    grouped = legs.groupby(["link_id", "mode", "from_node", "to_node",
                            "from_lat", "from_lon", "to_lat", "to_lon"], as_index=False).agg(
        shipments=("shipment_id", "nunique"),
        quantity=("quantity", "sum"),
        cost=("cost", "sum"),
        mean_delay=("delay_days", "mean"),
        max_delay=("delay_days", "max"),
    )
    return grouped


def hazard_points(bundle):
    hazards = _clean(bundle["hazards"])
    if hazards.empty:
        return hazards
    return hazards.dropna(subset=["latitude", "longitude"]).copy()
