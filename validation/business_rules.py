"""Business-rule validation (SRS section 5).

Covers BOM self-reference and cycles, scenario parameters, impact-multiplier
ranges, and route-leg continuity.
"""
from __future__ import annotations

from collections import defaultdict


def _validate_bom(report, tables):
    bom = tables.get("bill_of_materials") or []
    edges = defaultdict(list)
    for row in bom:
        parent, component = row["parent_sku"], row["component_sku"]
        if parent == component:
            report.error("bill_of_materials", parent,
                         "self-referencing component is not permitted")
        edges[parent].append(component)

    # Cycle detection via DFS colouring.
    WHITE, GREY, BLACK = 0, 1, 2
    colour = defaultdict(int)

    def visit(node, stack):
        colour[node] = GREY
        for child in edges.get(node, ()):
            if colour[child] == GREY:
                report.error("bill_of_materials", node,
                             f"circular BOM dependency detected: {' -> '.join(stack + [child])}")
                return
            if colour[child] == WHITE:
                visit(child, stack + [child])
        colour[node] = BLACK

    for node in list(edges):
        if colour[node] == WHITE:
            visit(node, [node])


def _validate_scenarios(report, tables):
    for index, row in enumerate(tables.get("scenarios") or []):
        days = row.get("days")
        seed = row.get("seed")
        if days is not None and float(days) <= 0:
            report.error("scenarios", f"row {index}", "simulation duration must be positive")
        if seed is not None and float(seed) < 0:
            report.error("scenarios", f"row {index}", "random seed must be non-negative")
        if not row.get("start_date"):
            report.error("scenarios", f"row {index}", "start_date is required")


def _validate_impacts(report, tables):
    for index, row in enumerate(tables.get("asset_impacts") or []):
        multiplier = float(row["capacity_multiplier"])
        if multiplier < 0:
            report.error("asset_impacts", row.get("impact_id", f"row {index}"),
                         f"capacity multiplier must be >= 0 (got {multiplier})")
        elif multiplier > 1:
            report.warning("asset_impacts", row.get("impact_id", f"row {index}"),
                           f"capacity multiplier above 1.0 increases capacity ({multiplier})")
        if row["end_day_exclusive"] < row["start_day"]:
            report.error("asset_impacts", row.get("impact_id", f"row {index}"),
                         "impact ends before it starts")
    for index, row in enumerate(tables.get("hazard_events") or []):
        if row["end_day"] < row["start_day"]:
            report.error("hazard_events", row.get("event_id", f"row {index}"),
                         "event ends before it starts")


def _validate_routes(report, tables):
    links = {l["link_id"]: l for l in (tables.get("transport_links") or [])}
    legs_by_route = defaultdict(list)
    for leg in tables.get("route_legs") or []:
        legs_by_route[leg["route_id"]].append(leg)

    for route_id, legs in legs_by_route.items():
        ordered = sorted(legs, key=lambda x: x["sequence"])
        expected = list(range(1, len(ordered) + 1))
        actual = [leg["sequence"] for leg in ordered]
        if actual != expected:
            report.error("route_legs", route_id,
                         f"sequence must be contiguous from 1 (got {actual})")
            continue
        for previous, current in zip(ordered, ordered[1:]):
            prev_link = links.get(previous["link_id"])
            curr_link = links.get(current["link_id"])
            if prev_link and curr_link and prev_link["to_node"] != curr_link["from_node"]:
                report.error(
                    "route_legs", route_id,
                    f"discontinuous route: {previous['link_id']} ends at "
                    f"{prev_link['to_node']} but {current['link_id']} starts at "
                    f"{curr_link['from_node']}",
                )


def validate_business_rules(tables, report):
    _validate_bom(report, tables)
    _validate_scenarios(report, tables)
    _validate_impacts(report, tables)
    _validate_routes(report, tables)
    return report
