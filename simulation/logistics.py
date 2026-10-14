"""Logistics: effective transport capacity, shipment advancement, and dispatch.

Available capacity of a link on a day is the nominal capacity scaled by the
most restrictive of the link, origin-node and destination-node multipliers
(SRS section 6.4).
"""
from __future__ import annotations


def compute_capacities(ctx, effects, day):
    capacities = {}
    for link in ctx.tables["transport_links"]:
        factor = min(
            effects.multiplier(link["link_id"], day),
            effects.multiplier(link["from_node"], day),
            effects.multiplier(link["to_node"], day),
        )
        capacities[link["link_id"]] = int(link["daily_capacity_units"] * factor)
    return capacities


def advance_shipments(ctx, effects, day, shipments, legs, capacities, ledger):
    """Progress in-transit shipments, complete legs, and receive arrivals."""
    for shipment in shipments:
        if shipment["received_day"] != "":
            continue

        route = ctx.route_map[shipment["route_id"]]

        if shipment["_remaining"] > 0:
            link = ctx.linkmap[route[shipment["_index"]]]
            if min(
                effects.multiplier(link["link_id"], day),
                effects.multiplier(link["to_node"], day),
            ) > 0:
                shipment["_remaining"] -= 1
            if shipment["_remaining"] == 0:
                legs[shipment["_legrow"]]["arrival_day"] = day
                shipment["_index"] += 1
                shipment["_eligible"] = day + 1

        if shipment["_index"] == len(route):
            if effects.multiplier(shipment["factory_id"], day) > 0:
                ledger.apply(
                    day, shipment["factory_id"], shipment["sku_id"],
                    shipment["quantity"], "receipt", shipment["shipment_id"],
                )
                shipment["received_day"] = day
            continue

        if shipment["_remaining"] == 0 and day >= shipment["_eligible"]:
            link_id = route[shipment["_index"]]
            link = ctx.linkmap[link_id]
            if day % link["departure_interval_days"] == 0 and capacities[link_id] >= shipment["quantity"]:
                capacities[link_id] -= shipment["quantity"]
                shipment["_remaining"] = link["transit_days"]
                shipment["_legrow"] = len(legs)
                legs.append(dict(
                    shipment_id=shipment["shipment_id"],
                    sequence=shipment["_index"] + 1, link_id=link_id,
                    departure_day=day, arrival_day="", quantity=shipment["quantity"],
                ))


def dispatch_orders(ctx, effects, day, orders, shipments):
    """Release ready purchase orders into shipments, limited by supplier output."""
    supply = int(5000 * effects.multiplier("S1", day))
    for order in orders:
        if (
            order["dispatched_day"] == ""
            and order["ready_day"] <= day
            and order["quantity"] <= supply
        ):
            supply -= order["quantity"]
            order["dispatched_day"] = day
            shipments.append(dict(
                shipment_id=f"SH{len(shipments) + 1:06}", order_id=order["order_id"],
                factory_id=order["factory_id"], sku_id=order["sku_id"],
                quantity=order["quantity"], route_id=order["route_id"],
                dispatch_day=day, received_day="",
                _index=0, _remaining=0, _eligible=day + 1, _legrow=-1,
            ))
