"""TSC-SRS — Taiwan IT Supply Chain Resilience Simulator (dashboard entry point).

Run from the repository root::

    streamlit run app/frontend/app.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

st.set_page_config(
    page_title="TSC-SRS · Supply Chain Resilience Simulator",
    page_icon=":material/hub:",
    layout="wide",
)

pages = {
    "Analysis": [
        st.Page("app_pages/dashboard.py", title="Dashboard",
                icon=":material/dashboard:", default=True),
        st.Page("app_pages/results.py", title="Results & comparison",
                icon=":material/compare_arrows:"),
        st.Page("app_pages/network.py", title="Network & logistics",
                icon=":material/route:"),
    ],
    "Configuration": [
        st.Page("app_pages/master_data.py", title="Master data",
                icon=":material/table_view:"),
        st.Page("app_pages/scenario_designer.py", title="Scenario designer",
                icon=":material/science:"),
        st.Page("app_pages/data_explorer.py", title="Data explorer",
                icon=":material/database:"),
    ],
}

with st.sidebar:
    st.title(":material/hub: TSC-SRS")
    st.caption("Taiwan IT supply chain resilience simulator · synthetic data")
    scenarios = common.available_scenarios()
    if scenarios:
        default_index = scenarios.index("compound") if "compound" in scenarios else 0
        st.session_state.scenario = st.selectbox(
            "Active scenario", scenarios, index=default_index, key="scenario_select"
        )
    else:
        st.warning("No scenarios found. Run `python run_simulation.py` first.")
        st.session_state.scenario = None

navigation = st.navigation(pages, position="sidebar")
navigation.run()
