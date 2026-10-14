"""KPI dashboard (SRS screen 1)."""
import sys
from pathlib import Path

import altair as alt
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

scenario = st.session_state.get("scenario")
if not scenario:
    st.info("No scenario selected.")
    st.stop()

data = common.load_scenario(scenario)
summary = data.get("summary", {})
config = data.get("config", {})

st.title(f":material/dashboard: {scenario.capitalize()} scenario")
st.caption(
    f"seed {config.get('seed', '?')} · {config.get('simulation_days', '?')} days from "
    f"{config.get('start_date', '?')} · parameters {config.get('parameter_status', 'fictional')}"
)

with st.container(horizontal=True):
    st.metric("Demand fulfilment",
              f"{summary.get('demand_fulfilment_rate', 0) * 100:.1f}%", border=True)
    st.metric("Production utilization",
              f"{summary.get('production_utilization', 0) * 100:.1f}%", border=True)
    st.metric("Ending backlog", f"{summary.get('ending_backlog', 0):,}", border=True)
    st.metric("Stockout days", f"{summary.get('stockout_days', 0):,}", border=True)
    st.metric("Inventory value", f"${summary.get('final_inventory_value', 0):,.0f}", border=True)
    st.metric("Transport cost", f"${summary.get('transport_cost_incurred', 0):,.0f}", border=True)

st.divider()

production = data.get("production_actuals")
factories = ["All"]
if production is not None and not production.empty:
    factories += sorted(production["factory_id"].unique())
factory = st.segmented_control(
    "Factory", factories, default="All", key="dash_factory"
) or "All"

daily = common.production_daily(data, factory)

with st.container(border=True):
    st.subheader("Demand, production and backlog")
    value_vars = [c for c in ("new_demand", "produced", "backlog") if c in daily.columns]
    melted = daily.melt(id_vars="day", value_vars=value_vars,
                        var_name="metric", value_name="units")
    chart = (
        alt.Chart(melted).mark_line()
        .encode(
            x=alt.X("day:Q", title="simulation day"),
            y=alt.Y("units:Q", title="units"),
            color=alt.Color("metric:N", title="metric"),
            tooltip=["day", "metric", "units"],
        )
        .properties(height=320)
        .interactive()
    )
    st.altair_chart(chart, width="stretch")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Component inventory on hand")
        inventory = common.inventory_daily(data, factory)
        if inventory.empty:
            st.caption("No inventory snapshots available.")
        else:
            area = (
                alt.Chart(inventory).mark_area(opacity=0.55)
                .encode(
                    x=alt.X("day:Q", title="simulation day"),
                    y=alt.Y("on_hand:Q", title="units on hand"),
                    tooltip=["day", "on_hand"],
                )
                .properties(height=300)
                .interactive()
            )
            st.altair_chart(area, width="stretch")

with col2:
    with st.container(border=True):
        st.subheader("Production constraint source")
        if production is None or production.empty:
            st.caption("No production records available.")
        else:
            scoped = production if factory == "All" else production[production["factory_id"] == factory]
            counts = scoped.groupby("material_limited").size().reset_index(name="days")
            counts["label"] = counts["material_limited"].map(
                {0: "capacity-supply", 1: "material-limited"}
            )
            bar = (
                alt.Chart(counts).mark_bar()
                .encode(
                    x=alt.X("label:N", title="limiting factor"),
                    y=alt.Y("days:Q", title="output-SKU days"),
                    color=alt.Color("label:N", legend=None),
                    tooltip=["label", "days"],
                )
                .properties(height=300)
            )
            st.altair_chart(bar, width="stretch")

impacts = data.get("asset_impacts")
events = data.get("hazard_events")
if impacts is not None and not impacts.empty:
    with st.container(border=True):
        st.subheader("Disruption timeline")
        merged = impacts.merge(events[["event_id", "hazard_type"]], on="event_id", how="left")
        timeline = (
            alt.Chart(merged).mark_bar(size=16)
            .encode(
                x=alt.X("start_day:Q", title="simulation day"),
                x2="end_day_exclusive:Q",
                y=alt.Y("asset_id:N", title="asset", sort="-x"),
                color=alt.Color("hazard_type:N", title="hazard"),
                tooltip=["asset_id", "hazard_type", "reason", "capacity_multiplier",
                         "start_day", "end_day_exclusive"],
            )
            .properties(height=max(160, 46 * merged["asset_id"].nunique()))
            .interactive()
        )
        st.altair_chart(timeline, width="stretch")
else:
    st.info("This scenario has no disruption events (baseline conditions).")
