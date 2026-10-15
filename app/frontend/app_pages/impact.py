"""Baseline vs compound impact analysis (SRS comparison + explanations)."""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A  # noqa: E402

BASELINE, COMPOUND = "baseline", "compound"

st.title(":material/insights: Impact analysis — baseline vs compound")
st.caption(
    "Compares the undisturbed baseline with the compound scenario (earthquake + "
    "tsunami, typhoon + landslide, and a heatwave) and explains the mechanisms."
)

base = A.frames(BASELINE)
comp = A.frames(COMPOUND)

max_day = int(comp["config"].get("simulation_days", 730)) - 1

# --- filters --------------------------------------------------------------- #
with st.container(border=True):
    st.markdown("**Filters**")
    row = st.columns([2, 1, 1, 1, 1])
    day_range = row[0].slider("Simulation day range", 0, max_day, (0, max_day))
    factories = ["All"] + sorted(comp["production"]["factory_id"].unique())
    factory = row[1].selectbox("Factory", factories)
    outputs = ["All"] + sorted(comp["production"]["output_sku"].unique())
    output_sku = row[2].selectbox("Output product", outputs)
    components = ["All"] + sorted(comp["snapshots"]["sku_id"].unique())
    component = row[3].selectbox("Component", components)
    modes = ["All"] + A.MODE_ORDER
    mode = row[4].selectbox("Transport mode", modes)

# --- KPI deltas ------------------------------------------------------------ #
deltas = A.kpi_deltas(BASELINE, COMPOUND).set_index("key")

def card(key, label, fmt, pct=False):
    if key not in deltas.index:
        return
    row = deltas.loc[key]
    base_v, comp_v = row["baseline"], row["compound"]
    if pct:
        st.metric(label, f"{comp_v * 100:.1f}%", delta=f"{(comp_v - base_v) * 100:+.1f} pts", border=True)
    elif fmt == "$":
        st.metric(label, f"${comp_v:,.0f}", delta=f"${comp_v - base_v:+,.0f}", border=True)
    elif fmt == "d":
        st.metric(label, f"{comp_v:,.2f} d", delta=f"{comp_v - base_v:+.2f} d", border=True)
    else:
        st.metric(label, f"{comp_v:,.0f}", delta=f"{comp_v - base_v:+,.0f}", border=True)

with st.container(horizontal=True):
    card("stockout_days", "Stockout days", "n")
    card("mean_completed_lead_days", "Mean lead time", "d")
    card("transport_cost_incurred", "Transport cost", "$")
    card("production_utilization", "Production utilization", "pct", pct=True)

base_cost = A.cost_by_mode(base)
comp_cost = A.cost_by_mode(comp)
air_delta = float(comp_cost.get("air", 0) - base_cost.get("air", 0))
st.caption(
    f"Headline: identical demand and total output, but {int(deltas.loc['stockout_days','change'])} "
    f"more stockout days, +${float(deltas.loc['transport_cost_incurred','change']):,.0f} transport "
    f"cost, and +${air_delta:,.0f} of that in expedited air freight."
)

st.divider()

# --- inventory ------------------------------------------------------------- #
def inventory_frame(day_range, factory, component):
    frames = []
    for name, bundle in ((BASELINE, base), (COMPOUND, comp)):
        d = A.daily_inventory(bundle, factory, component, day_range)
        d["scenario"] = name
        frames.append(d)
    return pd.concat(frames, ignore_index=True)

with st.container(border=True):
    st.subheader("Inventory levels")
    inv = inventory_frame(day_range, factory, component)
    chart = (
        alt.Chart(inv).mark_line()
        .encode(
            x=alt.X("day:Q", title="simulation day"),
            y=alt.Y("on_hand:Q", title="units on hand"),
            color=alt.Color("scenario:N", title="scenario"),
            tooltip=["day", "scenario", "on_hand"],
        )
        .properties(height=320).interactive()
    )
    st.altair_chart(chart, width="stretch")
    st.caption("Total component on-hand; the compound curve dips lower around the "
               "earthquake window (days 90–105) and stays below baseline during recovery.")

# --- shipment delays ------------------------------------------------------- #
def lead_frame():
    frames = []
    for name, bundle in ((BASELINE, base), (COMPOUND, comp)):
        lt = A.lead_times(bundle)
        if lt.empty:
            continue
        lt = lt[lt["dispatch_day"].between(*day_range)]
        if factory != "All":
            lt = lt[lt["factory_id"] == factory]
        if mode != "All":
            lt = lt[lt["mode"] == mode]
        lt = lt.copy()
        lt["scenario"] = name
        frames.append(lt)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Shipment lead-time distribution")
        lead = lead_frame()
        if lead.empty:
            st.caption("No completed shipments for the current filters.")
        else:
            box = (
                alt.Chart(lead).mark_boxplot(extent="min-max")
                .encode(
                    x=alt.X("scenario:N", title="scenario"),
                    y=alt.Y("lead:Q", title="lead time (days)"),
                    color=alt.Color("scenario:N", legend=None),
                )
                .properties(height=300)
            )
            st.altair_chart(box, width="stretch")
            stats = lead.groupby("scenario")["lead"].agg(["count", "mean", "median", "max"]).round(2)
            st.dataframe(stats, width="stretch", alt="Lead-time statistics by scenario")

with col2:
    with st.container(border=True):
        st.subheader("Delay vs nominal transit (by mode)")
        legs = []
        for name, bundle in ((BASELINE, base), (COMPOUND, comp)):
            d = A.leg_details(bundle)
            if d.empty:
                continue
            d = d[d["departure_day"].between(*day_range)]
            if factory != "All":
                d = d[d["factory_id"] == factory]
            if mode != "All":
                d = d[d["mode"] == mode]
            d["scenario"] = name
            legs.append(d)
        legs = pd.concat(legs, ignore_index=True) if legs else pd.DataFrame()
        if legs.empty:
            st.caption("No shipment legs for the current filters.")
        else:
            agg = (legs.dropna(subset=["delay_days"])
                   .groupby(["scenario", "mode"], as_index=False)["delay_days"].mean())
            bar = (
                alt.Chart(agg).mark_bar()
                .encode(
                    x=alt.X("mode:N", title="transport mode"),
                    y=alt.Y("delay_days:Q", title="mean delay (days over nominal)"),
                    color=alt.Color("scenario:N", title="scenario"),
                    xOffset="scenario:N",
                    tooltip=["scenario", "mode", "delay_days"],
                )
                .properties(height=300)
            )
            st.altair_chart(bar, width="stretch")
            st.caption("Delay = (arrival − departure) − nominal transit. Sea freight "
                       "absorbs most of the disruption; air is largely unaffected.")

# --- production & backlog -------------------------------------------------- #
def production_frame():
    frames = []
    for name, bundle in ((BASELINE, base), (COMPOUND, comp)):
        d = A.daily_production(bundle, factory, output_sku, day_range)
        d["scenario"] = name
        frames.append(d)
    return pd.concat(frames, ignore_index=True)

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Production output")
        prod = production_frame()
        melted = prod.melt(id_vars=["day", "scenario"],
                           value_vars=["produced", "new_demand"],
                           var_name="kind", value_name="units")
        chart = (
            alt.Chart(melted).mark_line()
            .encode(
                x=alt.X("day:Q", title="simulation day"),
                y=alt.Y("units:Q", title="units"),
                color=alt.Color("scenario:N", title="scenario"),
                strokeDash=alt.StrokeDash("kind:N", title="series"),
                tooltip=["day", "scenario", "kind", "units"],
            )
            .properties(height=300).interactive()
        )
        st.altair_chart(chart, width="stretch")

with col2:
    with st.container(border=True):
        st.subheader("Backlog")
        prod = production_frame()
        chart = (
            alt.Chart(prod).mark_area(opacity=0.5)
            .encode(
                x=alt.X("day:Q", title="simulation day"),
                y=alt.Y("backlog:Q", title="units of backlog"),
                color=alt.Color("scenario:N", title="scenario"),
                tooltip=["day", "scenario", "backlog"],
            )
            .properties(height=300).interactive()
        )
        st.altair_chart(chart, width="stretch")
        st.caption("The initial transient is identical; the compound scenario's "
                   "backlog tail extends from day 134 to day 241.")

# --- transport cost -------------------------------------------------------- #
with st.container(border=True):
    st.subheader("Cumulative transport cost")
    rows = []
    for name, bundle in ((BASELINE, base), (COMPOUND, comp)):
        d = A.leg_details(bundle)
        if d.empty:
            continue
        d = d[d["departure_day"].between(*day_range)]
        if factory != "All":
            d = d[d["factory_id"] == factory]
        if mode != "All":
            d = d[d["mode"] == mode]
        grouped = d.groupby("departure_day", as_index=False)["cost"].sum().sort_values("departure_day")
        grouped["cumulative_cost"] = grouped["cost"].cumsum()
        grouped["scenario"] = name
        rows.append(grouped)
    cum = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if cum.empty:
        st.caption("No cost data for the current filters.")
    else:
        chart = (
            alt.Chart(cum).mark_line()
            .encode(
                x=alt.X("departure_day:Q", title="simulation day"),
                y=alt.Y("cumulative_cost:Q", title="cumulative cost ($)"),
                color=alt.Color("scenario:N", title="scenario"),
                tooltip=["departure_day", "scenario", "cumulative_cost"],
            )
            .properties(height=320).interactive()
        )
        st.altair_chart(chart, width="stretch")
        pivot = cum.groupby("scenario")["cumulative_cost"].max().round(0)
        st.caption("Final cumulative cost — " +
                   "; ".join(f"{k}: ${v:,.0f}" for k, v in pivot.items()) +
                   ". The gap opens during days 85–205 (earthquake recovery).")

# --- explanations ---------------------------------------------------------- #
st.subheader("Why the compound scenario behaves this way")
for insight in A.disruption_insights(base, comp):
    with st.container(border=True):
        st.markdown(f"**{insight['title']}**")
        st.markdown(insight["detail"])
        st.caption(f"Evidence · {insight['evidence']}")

with st.expander("Extracted KPI deltas (table)"):
    st.dataframe(deltas.reset_index(drop=True), hide_index=True, width="stretch",
                 alt="KPI deltas baseline versus compound")
