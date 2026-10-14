"""Taiwan IT Supply Chain Resilience Simulator (TSC-SRS) — simulation engine package.

Modules follow SRS section 9:
    master_data  — build master/configuration tables
    demand       — deterministic + stochastic demand generation
    disruptions  — hazard events and asset impacts
    inventory    — inventory balances and transaction ledger
    production   — BOM explosion and production
    procurement  — replenishment policy and purchase-order planning
    logistics    — transport capacities, shipment advancement and dispatch
    metrics      — KPI and summary calculation
    storage      — scenario folder / run-manifest persistence
    engine       — daily simulation orchestrator
"""
from .engine import run_and_write, run_scenario, SCENARIOS

__all__ = ["run_and_write", "run_scenario", "SCENARIOS"]
