"""Resilience forecast (what-if projections) and recommendations.

Predictions are conditional perturbation experiments with explicit assumptions
and Monte-Carlo uncertainty across the stochastic demand stream.
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A  # noqa: E402
import common  # noqa: E402
from simulation import whatif  # noqa: E402


@st.cache_data(show_spinner=False)
def project(base, days, seeds, asset, start, duration, mult, demand_mult, apply):
    """Run a perturbation (or reference) across seeds. Returns (summaries, backlog)."""
    impacts = (
        [dict(asset_id=asset, start_day=int(start), duration=int(duration),
              capacity_multiplier=float(mult), reason="user_what_if")]
        if apply else []
    )
    summaries, backlog_rows = [], []
    for seed in seeds:
        summary, outputs = whatif.run_whatif(
            base, days=int(days), seed=int(seed), impacts=impacts,
            demand_multiplier=float(demand_mult),
        )
        summary["seed"] = seed
        summaries.append(summary)
        daily = {}
        for row in outputs["production_actuals"]:
            daily[row["day"]] = daily.get(row["day"], 0) + row["backlog"]
        backlog_rows.extend(dict(seed=seed, day=day, backlog=value)
                            for day, value in daily.items())
    return pd.DataFrame(summaries), pd.DataFrame(backlog_rows)


st.title(":material/online_prediction: Resilience forecast & recommendations")
st.caption("Conditional what-if projections with stated assumptions and seed-based "
           "uncertainty, followed by data-backed resilience recommendations.")

nodes = common.load_table("compound", "nodes")
links = common.load_table("compound", "transport_links")
asset_options = []
if nodes is not None:
    asset_options += sorted(nodes["node_id"].unique())
if links is not None:
    asset_options += sorted(links["link_id"].unique())

with st.form("forecast_form"):
    st.markdown("**Projection parameters**")
    row1 = st.columns(4)
    base_scenario = row1[0].selectbox("Base scenario", ["baseline", "compound"])
    asset = row1[1].selectbox("Disrupted asset", asset_options,
                              index=asset_options.index("S1") if "S1" in asset_options else 0)
    start_day = row1[2].number_input("Impact start day", 0, 3000, 90)
    duration = row1[3].number_input("Impact duration (days)", 1, 365, 8)
    row2 = st.columns(4)
    mult = row2[0].slider("Capacity multiplier during impact", 0.0, 1.0, 0.0, 0.05)
    demand_mult = row2[1].slider("Demand multiplier", 0.5, 2.0, 1.0, 0.05)
    horizon = row2[2].number_input("Projection horizon (days)", 60, 730, 365, 30)
    n_seeds = row2[3].number_input("Monte-Carlo samples", 2, 8, 3)
    submitted = st.form_submit_button("Run projection", type="primary",
                                      icon=":material/play_arrow:")

seeds = tuple(42 + i for i in range(int(n_seeds)))

if submitted:
    st.session_state["forecast"] = dict(
        base_scenario=base_scenario, asset=asset, start_day=int(start_day),
        duration=int(duration), mult=float(mult), demand_mult=float(demand_mult),
        horizon=int(horizon), seeds=seeds,
    )

params = st.session_state.get("forecast")
if not params:
    st.info("Set the parameters and select **Run projection**. Defaults model an "
            "8-day total outage of the supplier factory S1 starting on day 90.")
    params = dict(base_scenario="baseline", asset="S1", start_day=90, duration=8,
                  mult=0.0, demand_mult=1.0, horizon=365, seeds=(42, 43, 44))

with st.expander("Assumptions behind this projection", expanded=True):
    st.markdown(
        f"""
- **Scenario:** the `{params['base_scenario']}` network, demand model and
  replenishment policy are unchanged.
- **Perturbation:** asset `{params['asset']}` has capacity multiplied by
  `{params['mult']:.2f}` for `{params['duration']}` days starting on day
  `{params['start_day']}`. This is treated as **certain inside its window** —
  it projects *"if this happens"*, not the probability that it happens.
- **Demand:** {params['demand_mult']:.2f}× the modelled demand from day 0
  onward.
- **Horizon:** {params['horizon']} days.
- **Uncertainty:** the spread across {len(params['seeds'])} seeds
  ({', '.join(map(str, params['seeds']))}) of the stochastic demand stream.
  It is **model uncertainty only** — it does not represent hazard probability,
  parameter calibration error, or structural change.
"""
    )

with st.status(f"Projecting {params['asset']} impact across {len(params['seeds'])} seeds …",
               expanded=False) as status:
    perturbed, backlog = project(
        params["base_scenario"], params["horizon"], params["seeds"], params["asset"],
        params["start_day"], params["duration"], params["mult"], params["demand_mult"], True,
    )
    reference, ref_backlog = project(
        params["base_scenario"], params["horizon"], params["seeds"], params["asset"],
        params["start_day"], params["duration"], params["mult"], params["demand_mult"], False,
    )
    status.update(label="Projection complete", state="complete")

# --- headline predictions -------------------------------------------------- #
def band(frame, column):
    return (float(frame[column].min()), float(frame[column].median()), float(frame[column].max()))

cost = band(perturbed, "transport_cost_incurred")
ref_cost = band(reference, "transport_cost_incurred")
peak = band(perturbed, "backlog_peak")
rec = band(perturbed, "recovery_day")
lead = band(perturbed, "mean_completed_lead_days")

with st.container(horizontal=True):
    st.metric("Projected transport cost", f"${cost[1]:,.0f}",
              delta=f"${cost[1] - ref_cost[1]:+,.0f} vs reference", border=True,
              help=f"Range ${cost[0]:,.0f} – ${cost[2]:,.0f} across seeds.")
    st.metric("Projected backlog peak", f"{peak[1]:,.0f}",
              delta=f"{peak[1] - band(reference, 'backlog_peak')[1]:+,.0f}", border=True,
              help=f"Range {peak[0]:,.0f} – {peak[2]:,.0f}.")
    st.metric("Backlog clears by day", f"{rec[1]:,.0f}",
              delta=f"{rec[1] - band(reference, 'recovery_day')[1]:+,.0f} d", border=True,
              help=f"Range {rec[0]:,.0f} – {rec[2]:,.0f}.")
    st.metric("Mean lead time", f"{lead[1]:,.2f} d",
              delta=f"{lead[1] - band(reference, 'mean_completed_lead_days')[1]:+.2f} d",
              border=True, help=f"Range {lead[0]:,.2f} – {lead[2]:,.2f}.")

st.caption(
    f"Prediction: an outage of **{params['asset']}** for {params['duration']} days at "
    f"{params['mult']:.2f}× capacity is expected to add about "
    f"**${cost[1] - ref_cost[1]:,.0f}** in transport cost (median) and push backlog "
    f"recovery out by about **{rec[1] - band(reference, 'recovery_day')[1]:,.0f} days**. "
    f"Uncertainty across seeds spans ${cost[0]:,.0f}–${cost[2]:,.0f} for cost."
)

# --- backlog trajectory ---------------------------------------------------- #
agg = backlog.groupby("day")["backlog"].agg(["min", "median", "max"]).reset_index()
ref_agg = ref_backlog.groupby("day")["backlog"].median().reset_index().rename(
    columns={"backlog": "reference"})

with st.container(border=True):
    st.subheader("Projected backlog trajectory (with uncertainty band)")
    band_chart = (
        alt.Chart(agg).mark_area(opacity=0.22, color="#0078D4")
        .encode(
            x=alt.X("day:Q", title="simulation day"),
            y=alt.Y("min:Q", title="units of backlog"),
            y2="max:Q",
        )
    )
    median_line = (
        alt.Chart(agg).mark_line(color="#0078D4")
        .encode(x="day:Q", y=alt.Y("median:Q", title="units of backlog"),
                tooltip=["day", "median", "min", "max"])
    )
    ref_line = (
        alt.Chart(ref_agg).mark_line(color="#999999", strokeDash=[5, 4])
        .encode(x="day:Q", y="reference:Q", tooltip=["day", "reference"])
    )
    st.altair_chart((band_chart + median_line + ref_line).properties(height=340).interactive(),
                    width="stretch")
    st.caption("Solid = median across seeds, shaded = min–max band, dashed grey = "
               "reference (no perturbation).")

with st.expander("Projection results by seed"):
    cols = ["seed", "transport_cost_incurred", "mean_completed_lead_days",
            "backlog_peak", "recovery_day", "stockout_days", "produced"]
    st.dataframe(perturbed[cols], hide_index=True, width="stretch",
                 alt="Projection results per seed")
    st.download_button(
        "Download projection (CSV)",
        perturbed[cols].to_csv(index=False).encode("utf-8"),
        file_name="forecast_projection.csv", mime="text/csv",
        icon=":material/download:", width="stretch",
    )

st.divider()

# --- recommendations ------------------------------------------------------- #
st.subheader(":material/lightbulb: Recommendations to improve resilience")
st.caption("Each recommendation is tied to evidence in the data, states the "
           "mechanism it relies on, the assumption it makes, and a confidence level.")

for item in A.build_recommendations(A.frames("baseline"), A.frames("compound")):
    with st.container(border=True):
        st.markdown(f"**{item['recommendation']}**")
        st.markdown(f"*Finding.* {item['finding']}")
        st.markdown(f"*Mechanism.* {item['mechanism']}")
        st.markdown(f"*Expected effect.* {item['expected_effect']}")
        st.caption(f"Assumption · {item['assumption']}  |  Confidence · {item['confidence']}")
