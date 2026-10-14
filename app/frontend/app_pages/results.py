"""Results and scenario comparison (SRS screen 5)."""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

st.title(":material/compare_arrows: Results & comparison")

frame = common.comparison_frame()
if frame.empty:
    st.warning("No comparison data found. Run `python run_simulation.py --scenarios all` first.")
    st.stop()

with st.container(border=True):
    st.subheader("Scenario KPI comparison")
    st.dataframe(frame, hide_index=True, width="stretch",
                 alt="Table comparing KPIs across scenarios")

numeric = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
default_metric = "transport_cost_incurred" if "transport_cost_incurred" in numeric else numeric[0]
metric = st.selectbox("Compare KPI across scenarios", numeric,
                      index=numeric.index(default_metric))

with st.container(border=True):
    st.subheader(f"{metric} by scenario")
    bar = (
        alt.Chart(frame).mark_bar()
        .encode(
            x=alt.X("scenario:N", sort="-y", title="scenario"),
            y=alt.Y(f"{metric}:Q", title=metric),
            color=alt.Color("scenario:N", legend=None),
            tooltip=["scenario", metric],
        )
        .properties(height=320)
    )
    st.altair_chart(bar, width="stretch")

st.subheader("Time-series overlay")
overlay_metric = st.segmented_control(
    "Production metric", ["produced", "new_demand", "backlog"],
    default="produced", key="overlay_metric",
) or "produced"

frames = []
for scenario in frame["scenario"]:
    production = common.load_table(scenario, "production_actuals")
    if production is None or production.empty:
        continue
    grouped = production.groupby("day", as_index=False)[overlay_metric].sum()
    grouped["scenario"] = scenario
    frames.append(grouped)

if frames:
    overlay = pd.concat(frames, ignore_index=True)
    with st.container(border=True):
        chart = (
            alt.Chart(overlay).mark_line()
            .encode(
                x=alt.X("day:Q", title="simulation day"),
                y=alt.Y(f"{overlay_metric}:Q", title=overlay_metric),
                color=alt.Color("scenario:N", title="scenario"),
                tooltip=["day", "scenario", overlay_metric],
            )
            .properties(height=340)
            .interactive()
        )
        st.altair_chart(chart, width="stretch")

st.subheader("Exports")
col1, col2 = st.columns(2)
with col1:
    st.download_button(
        "Download comparison (CSV)", frame.to_csv(index=False).encode("utf-8"),
        file_name="scenario_comparison.csv", mime="text/csv",
        icon=":material/download:", width="stretch",
    )
with col2:
    st.download_button(
        "Download comparison (JSON)",
        common.load_comparison().to_json(orient="records", indent=2).encode("utf-8"),
        file_name="scenario_comparison.json", mime="application/json",
        icon=":material/download:", width="stretch",
    )

with st.container(border=True):
    st.subheader("Export a scenario output table")
    col1, col2 = st.columns(2)
    export_scenario = col1.selectbox("Scenario", list(frame["scenario"]), key="export_scenario")
    tables = common.OUTPUT_TABLES
    export_table = col2.selectbox("Table", tables, key="export_table")
    table = common.load_table(export_scenario, export_table)
    if table is None or table.empty:
        st.caption("Selected table is empty.")
    else:
        st.caption(f"{len(table):,} rows")
        st.download_button(
            f"Download {export_scenario}_{export_table}.csv",
            table.to_csv(index=False).encode("utf-8"),
            file_name=f"{export_scenario}_{export_table}.csv", mime="text/csv",
            icon=":material/download:", width="stretch",
        )
