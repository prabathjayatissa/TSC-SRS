"""Shared data access and KPI helpers for the TSC-SRS dashboard.

The dashboard reads the SRS scenario-folder layout produced by the simulation
engine: ``scenarios/<scenario_id>/{master_data,outputs,reports}``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCENARIOS_DIR = ROOT / "scenarios"

INPUT_TABLES = [
    "scenarios", "suppliers", "nodes", "products", "bill_of_materials",
    "factory_products", "initial_inventory", "inventory_policies",
    "transport_links", "routes", "route_legs", "demand_orders",
    "hazard_events", "asset_impacts",
]
OUTPUT_TABLES = [
    "purchase_orders", "shipments", "shipment_legs", "inventory_transactions",
    "inventory_snapshots", "production_actuals", "decisions",
]
ALL_TABLES = INPUT_TABLES + OUTPUT_TABLES


@st.cache_data(show_spinner=False)
def available_scenarios():
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(
        p.name for p in SCENARIOS_DIR.iterdir()
        if p.is_dir() and (p / "config.json").exists()
    )


@st.cache_data(show_spinner=False)
def load_table(scenario, name):
    for sub in ("master_data", "outputs"):
        path = SCENARIOS_DIR / scenario / sub / f"{name}.csv"
        if path.exists():
            try:
                return pd.read_csv(path)
            except pd.errors.EmptyDataError:
                return pd.DataFrame()
    return None


@st.cache_data(show_spinner=False)
def load_config(scenario):
    path = SCENARIOS_DIR / scenario / "config.json"
    return json.loads(path.read_text()) if path.exists() else {}


@st.cache_data(show_spinner=False)
def load_summary(scenario):
    path = SCENARIOS_DIR / scenario / "reports" / "summary.json"
    return json.loads(path.read_text()) if path.exists() else {}


@st.cache_data(show_spinner=False)
def load_scenario(scenario):
    data = {}
    for name in ALL_TABLES:
        frame = load_table(scenario, name)
        if frame is not None:
            data[name] = frame
    data["config"] = load_config(scenario)
    data["summary"] = load_summary(scenario)
    return data


@st.cache_data(show_spinner=False)
def load_comparison():
    path = SCENARIOS_DIR / "reports" / "comparison.json"
    if not path.exists():
        return pd.DataFrame()
    return pd.DataFrame(json.loads(path.read_text()))


@st.cache_data(show_spinner=False)
def comparison_frame():
    frame = load_comparison()
    if frame.empty:
        return frame
    frame = frame.copy()
    if "demand_fulfilment_rate" in frame:
        frame["demand_fulfilment_rate"] = (frame["demand_fulfilment_rate"] * 100).round(2)
    if "production_utilization" in frame:
        frame["production_utilization"] = (frame["production_utilization"] * 100).round(2)
    return frame


def scenario_tables(scenario):
    """Return the raw table dict for a scenario (with a cached loader)."""
    return load_scenario(scenario)


def production_daily(data, factory=None):
    frame = data.get("production_actuals")
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["day", "new_demand", "produced", "backlog"])
    if factory and factory != "All":
        frame = frame[frame["factory_id"] == factory]
    return (
        frame.groupby("day", as_index=False)[["new_demand", "produced", "backlog", "capacity"]]
        .sum()
        .sort_values("day")
    )


def inventory_daily(data, factory=None, sku=None):
    frame = data.get("inventory_snapshots")
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["day", "on_hand"])
    if factory and factory != "All":
        frame = frame[frame["factory_id"] == factory]
    if sku and sku != "All":
        frame = frame[frame["sku_id"] == sku]
    return (
        frame.groupby("day", as_index=False)["on_hand"].sum().sort_values("day")
    )


def _multiplier(impacts_by_asset, asset, day):
    best = 1.0
    for row in impacts_by_asset.get(asset, ()):
        if row["start_day"] <= day < row["end_day_exclusive"]:
            if row["capacity_multiplier"] < best:
                best = row["capacity_multiplier"]
    return best


def capacity_timeline(impacts, assets, days):
    """Return a long dataframe of ``(asset, day, multiplier)`` for impacted assets.

    ``impacts`` may be a list of dicts or a :class:`pandas.DataFrame`.
    """
    if impacts is None:
        records = []
    elif hasattr(impacts, "to_dict"):
        records = impacts.to_dict("records")
    else:
        records = list(impacts)
    impacts_by_asset = {}
    for row in records:
        impacts_by_asset.setdefault(row["asset_id"], []).append(row)
    rows = []
    for asset in assets:
        for day in range(days):
            rows.append(dict(asset=asset, day=day,
                             multiplier=_multiplier(impacts_by_asset, asset, day)))
    return pd.DataFrame(rows)


def impact_window(impacts, pad=5, days=730):
    """Return the ``(start, end)`` day window that bounds the impact activities."""
    if impacts is None or len(impacts) == 0:
        return 0, min(days, 60)
    if hasattr(impacts, "columns"):
        starts = impacts["start_day"]
        ends = impacts["end_day_exclusive"]
    else:
        starts = [r["start_day"] for r in impacts]
        ends = [r["end_day_exclusive"] for r in impacts]
    start = max(0, int(min(starts)) - pad)
    end = min(days, int(max(ends)) + pad)
    return start, end


def line_chart(frame, x, y, color=None, alt_text="time series", width=700, height=320):
    if frame.empty:
        return None
    if isinstance(y, str):
        y = [y]
    chart = alt.Chart(frame).mark_line().encode(
        x=alt.X(f"{x}:Q", title=x),
        y=alt.Y(f"{y[0]}:Q", title="value"),
        tooltip=[x] + list(y),
    )
    if color:
        chart = alt.Chart(frame).mark_line().encode(
            x=alt.X(f"{x}:Q", title=x),
            y=alt.Y("value:Q", title="value"),
            color=alt.Color(f"{color}:N", title=color),
            tooltip=[x, color, "value"],
        )
    return chart.properties(width=width, height=height).interactive()


def metric_delta(current, reference):
    if not reference:
        return None
    return round((current - reference) / reference * 100, 1)
