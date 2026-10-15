"""Interactive world map: suppliers, factories, hubs, routes and disruptions.

Filters: scenario, time, factory, product, transport mode, location (country)
and node type. Uses deck.gl via st.pydeck_chart for polylines and points.
"""
import sys
from pathlib import Path

import pydeck as pdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A  # noqa: E402
import common  # noqa: E402

MODE_COLORS = {"sea": [0, 120, 212], "air": [216, 59, 1], "road": [135, 100, 184]}
NODE_COLORS = {
    "supplier_factory": [0, 120, 212], "supplier_dc": [135, 100, 184],
    "port": [0, 183, 195], "airport": [255, 185, 0],
    "destination_hub": [16, 124, 16], "factory": [216, 59, 1],
}
HAZARD_COLORS = {
    "earthquake": [216, 59, 1], "tsunami": [0, 90, 158], "typhoon": [135, 100, 184],
    "landslide": [120, 90, 40], "extreme_rain": [0, 153, 204], "heat": [200, 50, 50],
}

st.title(":material/public: World map — network, flows and disruptions")

scenarios = common.available_scenarios()
if not scenarios:
    st.warning("No scenarios found. Run `python run_simulation.py --scenarios all` first.")
    st.stop()

default_scenario = st.session_state.get("scenario", "compound")
with st.container(border=True):
    st.markdown("**Filters**")
    row1 = st.columns(4)
    scenario = row1[0].selectbox(
        "Scenario", scenarios,
        index=scenarios.index(default_scenario) if default_scenario in scenarios else 0,
    )
    bundle = A.frames(scenario)
    max_day = int(bundle["config"].get("simulation_days", 730)) - 1
    day_range = row1[1].slider("Simulation day range", 0, max_day, (0, max_day))
    factories = ["All"] + sorted(bundle["production"]["factory_id"].unique())
    factory = row1[2].selectbox("Factory", factories)
    components = ["All"] + sorted(bundle["snapshots"]["sku_id"].unique())
    sku = row1[3].selectbox("Product (component)", components)

    nodes_all = bundle["nodes"]
    row2 = st.columns(4)
    mode = row2[0].selectbox("Transport mode", ["All"] + A.MODE_ORDER)
    countries = sorted(nodes_all["country"].unique())
    selected_countries = row2[1].multiselect("Location (country)", countries, default=countries)
    node_types = sorted(nodes_all["node_type"].unique())
    selected_types = row2[2].multiselect("Node type", node_types, default=node_types)
    layer_choice = row2[3].selectbox("Flow colour", ["Transport mode", "Mean delay"])

nodes = nodes_all[
    nodes_all["country"].isin(selected_countries)
    & nodes_all["node_type"].isin(selected_types)
].copy()

flows = A.map_flows(bundle, day_range, factory, sku, mode)
if not flows.empty:
    flows = flows[
        flows["from_node"].isin(set(nodes["node_id"]))
        & flows["to_node"].isin(set(nodes["node_id"]))
    ].copy()

# --- build layers ---------------------------------------------------------- #
layers = []

if not flows.empty:
    max_q = max(1.0, float(flows["quantity"].max()))
    if layer_choice == "Transport mode":
        flows["color"] = flows["mode"].map(lambda m: MODE_COLORS.get(m, [128, 128, 128]))
    else:
        flows["color"] = flows["mean_delay"].apply(
            lambda d: [200, 40, 40] if d > 0 else [16, 124, 16]
        )
    flows["width"] = 1 + 7 * (flows["quantity"] / max_q) ** 0.5
    flows["path"] = flows.apply(
        lambda r: [[r["from_lon"], r["from_lat"]], [r["to_lon"], r["to_lat"]]], axis=1
    )
    if layer_choice == "Mean delay":
        flows["width"] = 1 + 7 * (flows["mean_delay"].abs().fillna(0) /
                                  max(1.0, float(flows["mean_delay"].abs().max() or 1.0)))
    layers.append(pdk.Layer(
        "PathLayer", data=flows, get_path="path", get_color="color",
        get_width="width", width_min_pixels=1, pickable=True, auto_highlight=True,
    ))

if not nodes.empty:
    nodes = nodes.copy()
    nodes["color"] = nodes["node_type"].map(lambda t: NODE_COLORS.get(t, [128, 128, 128]))
    nodes["radius"] = nodes["node_type"].map(
        {"supplier_factory": 90000, "supplier_dc": 70000, "port": 70000,
         "airport": 70000, "destination_hub": 55000, "factory": 45000}
    ).fillna(45000)
    layers.append(pdk.Layer(
        "ScatterplotLayer", data=nodes, get_position=["longitude", "latitude"],
        get_fill_color="color", get_radius="radius", pickable=True,
        auto_highlight=True, opacity=0.85, stroked=True, get_line_color=[255, 255, 255],
    ))

hazards = A.hazard_points(bundle)
if not hazards.empty:
    hazards = hazards[hazards["start_day"].between(*day_range)].copy()
if not hazards.empty:
    hazards["color"] = hazards["hazard_type"].map(lambda t: HAZARD_COLORS.get(t, [200, 0, 0]))
    hazards["radius"] = 130000
    layers.append(pdk.Layer(
        "ScatterplotLayer", data=hazards, get_position=["longitude", "latitude"],
        get_fill_color="color", get_radius="radius", pickable=True,
        opacity=0.35, stroked=True, get_line_color="color", line_width_min_pixels=2,
    ))

center_lat = float(nodes["latitude"].mean()) if not nodes.empty else 10.0
center_lon = float(nodes["longitude"].mean()) if not nodes.empty else 120.0
view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=1.3, pitch=0)

tooltip = {
    "html": "<b>{node_id}{link_id}{asset_id}</b><br/>"
            "mode: {mode}<br/>type: {node_type}<br/>country: {country}<br/>"
            "shipments: {shipments}<br/>quantity: {quantity}<br/>"
            "mean delay: {mean_delay}<br/>cost: {cost}<br/>"
            "hazard: {hazard_type}",
    "style": {"backgroundColor": "#1A1A1A", "color": "white"},
}

deck = pdk.Deck(
    layers=layers, initial_view_state=view, tooltip=tooltip,
    map_style="light", map_provider="carto",
)
st.pydeck_chart(deck, width="stretch",
                alt="World map of suppliers, factories, hubs, transport routes and disruptions")

st.caption(
    "Line thickness ∝ shipped quantity. Colour: transport mode, or red/green for "
    "positive/negative mean delay. Large translucent circles are disruption events."
)

# --- supporting tables ----------------------------------------------------- #
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Active flows")
        if flows.empty:
            st.caption("No flows match the current filters.")
        else:
            table = flows[["link_id", "mode", "from_node", "to_node", "shipments",
                           "quantity", "mean_delay", "max_delay", "cost"]].copy()
            table = table.round({"quantity": 0, "mean_delay": 2, "max_delay": 2, "cost": 0})
            st.dataframe(table.sort_values("quantity", ascending=False),
                         hide_index=True, width="stretch", alt="Active transport flows")

with col2:
    with st.container(border=True):
        st.subheader("Disruption events")
        all_hazards = A.hazard_points(bundle)
        if all_hazards.empty:
            st.caption("This scenario has no disruption events.")
        else:
            cols = ["event_id", "hazard_type", "start_day", "end_day", "intensity",
                    "unit", "latitude", "longitude"]
            st.dataframe(all_hazards[cols], hide_index=True, width="stretch",
                         alt="Disruption events")

with st.container(border=True):
    st.subheader("Nodes")
    if nodes.empty:
        st.caption("No nodes match the location/type filters.")
    else:
        st.dataframe(
            nodes[["node_id", "node_type", "country", "latitude", "longitude",
                   "daily_handling_units", "power_dependency", "water_dependency"]],
            hide_index=True, width="stretch", alt="Network nodes",
        )
