"""Scenario designer: parameters, disruptions and on-demand runs (SRS screen 4)."""
import sys
from datetime import date
from pathlib import Path

import altair as alt
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

scenario = st.session_state.get("scenario")
if not scenario:
    st.info("No scenario selected.")
    st.stop()

data = {
    "config": common.load_config(scenario),
    "summary": common.load_summary(scenario),
    "asset_impacts": common.load_table(scenario, "asset_impacts"),
    "hazard_events": common.load_table(scenario, "hazard_events"),
}
config = data.get("config", {})
summary = data.get("summary", {})
impacts = data.get("asset_impacts")
events = data.get("hazard_events")

st.title(":material/science: Scenario designer")
st.caption(f"Configure and (re)run scenario {scenario}")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Run parameters")
        st.json(config, expanded=True)

with col2:
    with st.container(border=True):
        st.subheader("Re-run simulation")
        st.caption("Executes the simulation engine in-process and writes new outputs "
                   "to the scenario folder. Validation runs before the engine.")
        days = st.number_input("Simulation days", min_value=1, max_value=3650,
                               value=int(config.get("simulation_days", 730)), step=30)
        seed = st.number_input("Random seed", min_value=0, max_value=10_000,
                               value=int(config.get("seed", 42)), step=1)
        run_clicked = st.button("Run simulation", type="primary",
                                icon=":material/play_arrow:")

        if run_clicked:
            from simulation import engine
            with st.status(f"Simulating {scenario} for {days} days ...", expanded=True) as status:
                st.write("Validating configuration ...")
                try:
                    result, run_id = engine.run_and_write(
                        common.SCENARIOS_DIR, scenario, days=int(days), seed=int(seed),
                        start_date=date.fromisoformat(str(config.get("start_date", "2027-01-01"))),
                        validate=True,
                    )
                except Exception as exc:  # surfaced to the user, never hidden
                    status.update(label="Simulation failed", state="error")
                    st.exception(exc)
                else:
                    st.write(f"Run {run_id} completed.")
                    st.write(f"Transport cost {result['transport_cost_incurred']:,.0f} · "
                             f"mean lead {result['mean_completed_lead_days']} days")
                    status.update(label="Simulation complete", state="complete")
                    st.cache_data.clear()
                    st.rerun()

st.divider()

with st.container(border=True):
    st.subheader("Hazard events")
    if events is None or events.empty:
        st.caption("No hazard events in this scenario.")
    else:
        st.dataframe(
            events[["event_id", "hazard_type", "start_day", "end_day",
                    "start_date", "intensity_metric", "intensity", "unit",
                    "parent_event_id", "event_group_id"]],
            hide_index=True, width="stretch", alt="Table of hazard events",
        )

with st.container(border=True):
    st.subheader("Asset impacts")
    if impacts is None or impacts.empty:
        st.caption("No asset impacts in this scenario.")
    else:
        st.dataframe(impacts, hide_index=True, width="stretch",
                     alt="Table of asset impacts")

if impacts is not None and not impacts.empty:
    with st.container(border=True):
        st.subheader("Effective capacity over time")
        days_total = int(config.get("simulation_days", 730))
        start, end = common.impact_window(impacts, pad=5, days=days_total)
        assets = sorted(impacts["asset_id"].unique())
        window = max(1, end - start)
        step = max(1, window // 120)
        timeline = common.capacity_timeline(impacts, assets, days_total)
        timeline = timeline[(timeline["day"] >= start) & (timeline["day"] <= end)]
        timeline = timeline[timeline["day"] % step == 0]
        heatmap = (
            alt.Chart(timeline).mark_rect()
            .encode(
                x=alt.X("day:Q", title="simulation day"),
                y=alt.Y("asset:N", title="asset"),
                color=alt.Color("multiplier:Q", title="capacity multiplier",
                                scale=alt.Scale(scheme="redyellowgreen", domain=[0, 1])),
                tooltip=["asset", "day", "multiplier"],
            )
            .properties(height=max(140, 34 * len(assets)))
        )
        st.altair_chart(heatmap, width="stretch")
