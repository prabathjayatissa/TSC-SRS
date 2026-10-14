"""Raw data explorer across all scenarios and tables."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402

st.title(":material/database: Data explorer")

scenarios = common.available_scenarios()
if not scenarios:
    st.warning("No scenarios found. Run `python run_simulation.py` first.")
    st.stop()

col1, col2 = st.columns(2)
explore_scenario = col1.selectbox(
    "Scenario", scenarios,
    index=scenarios.index(st.session_state.get("scenario", scenarios[0]))
    if st.session_state.get("scenario") in scenarios else 0,
    key="explore_scenario",
)
table_name = col2.selectbox(
    "Table", common.ALL_TABLES, key="explore_table",
)

frame = common.load_table(explore_scenario, table_name)
kind = "input (master_data)" if table_name in common.INPUT_TABLES else "output (outputs)"

with st.container(border=True):
    st.caption(f"{table_name} · {kind} · {explore_scenario}")
    if frame is None:
        st.info("Table not present for this scenario.")
    elif frame.empty:
        st.info("Table is empty.")
    else:
        st.caption(f"{len(frame):,} rows · {len(frame.columns)} columns")
        st.dataframe(frame, hide_index=True, width="stretch",
                     alt=f"Table {table_name} for scenario {explore_scenario}")
        st.download_button(
            f"Download {table_name}.csv", frame.to_csv(index=False).encode("utf-8"),
            file_name=f"{explore_scenario}_{table_name}.csv", mime="text/csv",
            icon=":material/download:", width="stretch",
        )

with st.expander("Data dictionary", icon=":material/menu_book:"):
    dictionary_path = common.SCENARIOS_DIR / explore_scenario / "reports" / "data_dictionary.json"
    if dictionary_path.exists():
        st.json(__import__("json").loads(dictionary_path.read_text()), expanded=False)
    else:
        st.caption("No data dictionary for this scenario.")
