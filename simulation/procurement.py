"""Procurement planning: periodic-review replenishment and decision logging.

The policy is intentionally simple: on each review day, raise a purchase order
to bring on-hand plus in-transit pipeline up to the target stock level. The
planner has no access to future disruption events (SRS FR-06).
"""
from __future__ import annotations

import math


def _pipeline(orders, shipments, factory, sku):
    outstanding_orders = sum(
        o["quantity"] for o in orders
        if o["factory_id"] == factory and o["sku_id"] == sku and o["dispatched_day"] == ""
    )
    in_transit = sum(
        s["quantity"] for s in shipments
        if s["factory_id"] == factory and s["sku_id"] == sku and s["received_day"] == ""
    )
    return outstanding_orders + in_transit


def plan_replenishment(ctx, day, ledger, orders, shipments, decisions):
    for factory in ctx.factories:
        for sku in ctx.components:
            policy = ctx.policies[factory, sku]
            pipeline = _pipeline(orders, shipments, factory, sku)
            quantity = max(0, policy["target_units"] - ledger.get(factory, sku) - pipeline)
            if not quantity:
                continue

            quantity = int(math.ceil(quantity / 10) * 10)
            order_id = f"O{len(orders) + 1:06}"
            expedite = ledger.get(factory, sku) < policy["expedite_trigger_units"]
            route_id = f"R{factory[1:]}_" + ("air" if expedite else "sea")
            ready_day = day + 3 + (2 if expedite else 0)

            orders.append(dict(
                order_id=order_id, supplier_id="SUP1", factory_id=factory, sku_id=sku,
                quantity=quantity, order_day=day, ready_day=ready_day,
                requested_receipt_day=day + 35, route_id=route_id, dispatched_day="",
            ))
            decisions.append(dict(
                decision_id=f"B{len(decisions) + 1:06}", day=day, factory_id=factory,
                sku_id=sku, order_id=order_id,
                observed_inventory=ledger.get(factory, sku),
                observed_pipeline=pipeline,
                action="expedite" if expedite else "standard",
                reason="inventory_threshold_only_no_future_event_access",
            ))
