"""Foreign-key and logical-key validation (SRS section 5).

Every foreign key must resolve to an existing entity unless the column is
explicitly nullable (for example ``nodes.supplier_id``). Polymorphic references
such as ``asset_impacts.asset_id`` are validated against both nodes and links.
"""
from __future__ import annotations

from collections import Counter


def _ids(rows, column):
    return {row[column] for row in rows}


def _check_reference(report, table, rows, column, target_ids, target_name, nullable=False):
    for index, row in enumerate(rows):
        value = row.get(column)
        if value in (None, ""):
            if not nullable:
                report.error(table, f"row {index}", f"{column} is empty but required")
            continue
        if value not in target_ids:
            report.error(table, f"row {index}",
                         f"{column}={value!r} does not reference an existing {target_name}")


def _check_unique(report, table, rows, columns):
    seen = Counter(tuple(row.get(c) for c in columns) for row in rows)
    for key, count in seen.items():
        if count > 1:
            report.error(table, str(key), f"duplicate logical key on {columns} ({count} rows)")


COMPOSITE_KEYS = {
    "bill_of_materials": ["parent_sku", "component_sku"],
    "initial_inventory": ["factory_id", "sku_id"],
    "factory_products": ["factory_id", "output_sku"],
    "inventory_policies": ["factory_id", "sku_id"],
    "inventory_snapshots": ["day", "factory_id", "sku_id"],
    "production_actuals": ["day", "factory_id", "output_sku"],
    "route_legs": ["route_id", "sequence"],
    "shipment_legs": ["shipment_id", "sequence"],
    "transport_links": ["link_id"],
    "routes": ["route_id"],
    "nodes": ["node_id"],
    "products": ["sku_id"],
}


def validate_foreign_keys(tables, report):
    get = lambda name: tables.get(name) or []

    node_ids = _ids(get("nodes"), "node_id")
    product_ids = _ids(get("products"), "sku_id")
    supplier_ids = _ids(get("suppliers"), "supplier_id")
    link_ids = _ids(get("transport_links"), "link_id")
    route_ids = _ids(get("routes"), "route_id")
    order_ids = _ids(get("purchase_orders"), "order_id")
    shipment_ids = _ids(get("shipments"), "shipment_id")
    event_ids = _ids(get("hazard_events"), "event_id")
    asset_ids = node_ids | link_ids

    _check_reference(report, "nodes", get("nodes"), "supplier_id", supplier_ids,
                     "supplier", nullable=True)

    _check_reference(report, "bill_of_materials", get("bill_of_materials"),
                     "parent_sku", product_ids, "product")
    _check_reference(report, "bill_of_materials", get("bill_of_materials"),
                     "component_sku", product_ids, "product")

    _check_reference(report, "factory_products", get("factory_products"),
                     "factory_id", node_ids, "node")
    _check_reference(report, "factory_products", get("factory_products"),
                     "output_sku", product_ids, "product")

    _check_reference(report, "initial_inventory", get("initial_inventory"),
                     "factory_id", node_ids, "node")
    _check_reference(report, "initial_inventory", get("initial_inventory"),
                     "sku_id", product_ids, "product")

    _check_reference(report, "inventory_policies", get("inventory_policies"),
                     "factory_id", node_ids, "node")
    _check_reference(report, "inventory_policies", get("inventory_policies"),
                     "sku_id", product_ids, "product")

    _check_reference(report, "transport_links", get("transport_links"),
                     "from_node", node_ids, "node")
    _check_reference(report, "transport_links", get("transport_links"),
                     "to_node", node_ids, "node")

    _check_reference(report, "routes", get("routes"), "factory_id", node_ids, "node")
    _check_reference(report, "route_legs", get("route_legs"), "route_id", route_ids, "route")
    _check_reference(report, "route_legs", get("route_legs"), "link_id", link_ids, "transport link")

    _check_reference(report, "demand_orders", get("demand_orders"),
                     "factory_id", node_ids, "node")
    _check_reference(report, "demand_orders", get("demand_orders"),
                     "output_sku", product_ids, "product")

    _check_reference(report, "purchase_orders", get("purchase_orders"),
                     "supplier_id", supplier_ids, "supplier")
    _check_reference(report, "purchase_orders", get("purchase_orders"),
                     "factory_id", node_ids, "node")
    _check_reference(report, "purchase_orders", get("purchase_orders"),
                     "sku_id", product_ids, "product")
    _check_reference(report, "purchase_orders", get("purchase_orders"),
                     "route_id", route_ids, "route")

    _check_reference(report, "shipments", get("shipments"), "order_id", order_ids,
                     "purchase order")
    _check_reference(report, "shipments", get("shipments"), "factory_id", node_ids, "node")
    _check_reference(report, "shipments", get("shipments"), "sku_id", product_ids, "product")
    _check_reference(report, "shipments", get("shipments"), "route_id", route_ids, "route")

    _check_reference(report, "shipment_legs", get("shipment_legs"), "shipment_id",
                     shipment_ids, "shipment")
    _check_reference(report, "shipment_legs", get("shipment_legs"), "link_id",
                     link_ids, "transport link")

    # Polymorphic asset reference: must resolve to a node OR a link.
    _check_reference(report, "asset_impacts", get("asset_impacts"), "asset_id",
                     asset_ids, "node or transport link")
    _check_reference(report, "asset_impacts", get("asset_impacts"), "event_id",
                     event_ids, "hazard event")

    _check_reference(report, "hazard_events", get("hazard_events"), "parent_event_id",
                     event_ids, "hazard event", nullable=True)

    for table, columns in COMPOSITE_KEYS.items():
        rows = get(table)
        if rows:
            _check_unique(report, table, rows, columns)

    return report
