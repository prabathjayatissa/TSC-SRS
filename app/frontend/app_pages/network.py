"""Network and logistics view (SRS screen 2)."""
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

data = {
    "nodes": common.load_table(scenario, "nodes"),
    "transport_links": common.load_table(scenario, "transport_links"),
    "routes": common.load_table(scenario, "routes"),
    "route_legs": common.load_table(scenario, "route_legs"),
}
nodes = data.get("nodes")
links = data.get("transport_links")
routes = data.get("routes")
route_legs = data.get("route_legs")

st.title(":material/route: Network & logistics")
st.caption(f"Scenario {scenario} · coordinates are illustrative anchors, not surveyed assets")

with st.container(border=True):
    st.subheader("Node locations")
    if nodes is None or nodes.empty:
        st.caption("No node data available.")
    else:
        size_map = {"supplier_factory": 260, "supplier_dc": 200, "port": 200,
                    "airport": 200, "destination_hub": 150, "factory": 120}
        color_map = {"supplier_factory": "#0078D4", "supplier_dc": "#8764B8",
                     "port": "#00B7C3", "airport": "#FFB900",
                     "destination_hub": "#107C10", "factory": "#D83B01"}
        nodes = nodes.copy()
        nodes["marker_size"] = nodes["node_type"].map(size_map).fillna(120)
        nodes["marker_color"] = nodes["node_type"].map(color_map).fillna("#737373")
        st.map(nodes, latitude="latitude", longitude="longitude",
               color="marker_color", size="marker_size", width="stretch",
               alt="Map of supply chain nodes coloured by node type")
        st.caption("Colours: supplier factory, supplier DC, port, airport, "
                   "destination hub, factory.")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Node inventory")
        if nodes is not None and not nodes.empty:
            st.dataframe(
                nodes[["node_id", "node_type", "country", "supplier_id",
                       "daily_handling_units", "power_dependency", "water_dependency"]],
                hide_index=True, width="stretch", alt="Table of network nodes",
            )

with col2:
    with st.container(border=True):
        st.subheader("Effective link capacity")
        if links is not None and not links.empty:
            by_mode = links.groupby("mode", as_index=False)["daily_capacity_units"].sum()
            bar = (
                alt.Chart(by_mode).mark_bar()
                .encode(
                    x=alt.X("mode:N", title="transport mode"),
                    y=alt.Y("daily_capacity_units:Q", title="nominal daily capacity (units)"),
                    color=alt.Color("mode:N", legend=None),
                    tooltip=["mode", "daily_capacity_units"],
                )
                .properties(height=280)
            )
            st.altair_chart(bar, width="stretch")

with st.container(border=True):
    st.subheader("Transport links")
    if links is None or links.empty or nodes is None:
        st.caption("No transport-link data available.")
    else:
        node_lookup = nodes.set_index("node_id")[["node_type", "country"]]
        enriched = links.copy()
        enriched["from_type"] = enriched["from_node"].map(node_lookup["node_type"])
        enriched["to_type"] = enriched["to_node"].map(node_lookup["node_type"])
        enriched["from_country"] = enriched["from_node"].map(node_lookup["country"])
        enriched["to_country"] = enriched["to_node"].map(node_lookup["country"])
        st.dataframe(
            enriched[["link_id", "from_node", "from_type", "to_node", "to_type",
                      "mode", "transit_days", "daily_capacity_units",
                      "departure_interval_days", "cost_per_unit"]],
            hide_index=True, width="stretch", alt="Table of transport links",
        )

with st.container(border=True):
    st.subheader("Routes and leg sequences")
    if routes is None or routes.empty:
        st.caption("No route data available.")
    else:
        legs_by_route = (
            route_legs.sort_values(["route_id", "sequence"])
            .groupby("route_id")["link_id"]
            .apply(lambda s: " → ".join(s))
            .rename("legs")
        )
        combined = routes.set_index("route_id").join(legs_by_route).reset_index()
        st.dataframe(combined, hide_index=True, width="stretch",
                     alt="Table of routes and their ordered legs")
