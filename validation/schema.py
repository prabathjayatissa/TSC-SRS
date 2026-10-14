"""Structural schema validation: required columns and value ranges."""
from __future__ import annotations

REQUIRED_COLUMNS = {
    "scenarios": ["scenario_id", "seed", "days", "start_date"],
    "suppliers": ["supplier_id", "name", "country"],
    "nodes": ["node_id", "node_type", "country", "latitude", "longitude",
              "daily_handling_units"],
    "products": ["sku_id", "product_level", "uom", "unit_value"],
    "bill_of_materials": ["parent_sku", "component_sku", "quantity_per"],
    "factory_products": ["factory_id", "output_sku", "capacity_per_day", "priority"],
    "initial_inventory": ["factory_id", "sku_id", "quantity"],
    "inventory_policies": ["factory_id", "sku_id", "target_units",
                           "review_interval_days", "expedite_trigger_units"],
    "transport_links": ["link_id", "from_node", "to_node", "mode", "transit_days",
                        "daily_capacity_units", "departure_interval_days"],
    "routes": ["route_id", "factory_id", "route_type", "activation_days"],
    "route_legs": ["route_id", "sequence", "link_id"],
    "demand_orders": ["day", "factory_id", "output_sku", "quantity"],
    "purchase_orders": ["order_id", "supplier_id", "factory_id", "sku_id", "quantity",
                        "route_id"],
    "shipments": ["shipment_id", "order_id", "factory_id", "sku_id", "quantity",
                  "route_id"],
    "shipment_legs": ["shipment_id", "sequence", "link_id"],
    "inventory_transactions": ["transaction_id", "day", "factory_id", "sku_id",
                               "quantity_delta", "transaction_type"],
    "inventory_snapshots": ["day", "factory_id", "sku_id", "on_hand"],
    "production_actuals": ["day", "factory_id", "output_sku", "new_demand",
                           "produced", "backlog"],
    "decisions": ["decision_id", "day", "factory_id", "sku_id", "order_id"],
    "hazard_events": ["event_id", "scenario_id", "hazard_type", "start_day", "end_day"],
    "asset_impacts": ["impact_id", "event_id", "asset_id", "start_day",
                      "end_day_exclusive", "capacity_multiplier"],
}

# Columns that must never be negative when present.
NON_NEGATIVE_COLUMNS = {
    "products": ["unit_value"],
    "nodes": ["daily_handling_units"],
    "bill_of_materials": ["quantity_per"],
    "factory_products": ["capacity_per_day", "priority"],
    "initial_inventory": ["quantity"],
    "inventory_policies": ["target_units", "review_interval_days", "expedite_trigger_units"],
    "transport_links": ["transit_days", "daily_capacity_units", "departure_interval_days"],
    "routes": ["activation_days"],
    "route_legs": ["sequence"],
    "demand_orders": ["quantity"],
    "purchase_orders": ["quantity"],
    "shipments": ["quantity"],
    "shipment_legs": ["sequence"],
    "inventory_snapshots": ["on_hand"],
    "production_actuals": ["new_demand", "produced", "backlog"],
    "asset_impacts": ["start_day", "end_day_exclusive"],
}


def validate_schema(tables, report, expected_tables=None):
    for name, required in REQUIRED_COLUMNS.items():
        rows = tables.get(name)
        if rows is None:
            if expected_tables is None or name in expected_tables:
                report.error(name, "-", "table is missing from the dataset")
            continue
        if not rows:
            continue  # empty tables are permitted (e.g. baseline hazards)
        columns = set(rows[0].keys())
        missing = [c for c in required if c not in columns]
        if missing:
            report.error(name, "-", f"missing required columns: {', '.join(missing)}")

    for name, columns in NON_NEGATIVE_COLUMNS.items():
        rows = tables.get(name) or []
        for index, row in enumerate(rows):
            for column in columns:
                value = row.get(column)
                if value is None:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    report.error(name, f"row {index}", f"{column} is not numeric: {value!r}")
                    continue
                if numeric < 0:
                    report.error(name, f"row {index}", f"{column} is negative: {numeric}")
    return report
