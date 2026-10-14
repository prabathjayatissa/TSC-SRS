"""Master data and inventory view (SRS screen 3)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

scenario = st.session_state.get("scenario")
if not scenario:
    st.info("No scenario selected.")
    st.stop()

data = common.load_scenario(scenario)

st.title(":material/table_view: Master data & inventory")
st.caption(f"Validated configuration inputs for scenario {scenario}")

available = [name for name in common.INPUT_TABLES if name in data]
table_name = st.selectbox("Entity", available, key="master_entity")
frame = data.get(table_name)

with st.container(border=True):
    if frame is None or frame.empty:
        st.caption(f"{table_name} is empty for this scenario.")
    else:
        st.caption(f"{len(frame):,} rows · {len(frame.columns)} columns")
        st.dataframe(frame, hide_index=True, width="stretch",
                     alt=f"Table of {table_name}")
        st.download_button(
            f"Download {table_name}.csv", frame.to_csv(index=False).encode("utf-8"),
            file_name=f"{scenario}_{table_name}.csv", mime="text/csv",
            icon=":material/download:", width="stretch",
        )

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("Bill of materials")
        bom = data.get("bill_of_materials")
        if bom is None or bom.empty:
            st.caption("No BOM defined.")
        else:
            st.dataframe(bom, hide_index=True, width="stretch",
                         alt="Bill of materials")

with col2:
    with st.container(border=True):
        st.subheader("Replenishment policies")
        policies = data.get("inventory_policies")
        if policies is None or policies.empty:
            st.caption("No inventory policies defined.")
        else:
            st.dataframe(policies, hide_index=True, width="stretch",
                         alt="Inventory replenishment policies")

with st.container(border=True):
    st.subheader("Initial inventory")
    inventory = data.get("initial_inventory")
    if inventory is None or inventory.empty:
        st.caption("No initial inventory defined.")
    else:
        pivot = inventory.pivot_table(index="factory_id", columns="sku_id",
                                      values="quantity", aggfunc="sum")
        st.dataframe(pivot, width="stretch", alt="Initial inventory by factory and SKU")
