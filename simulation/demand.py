"""Deterministic-stochastic demand generation.

The demand random stream (``seed + 100``) is deliberately independent of the
transport / disruption streams so that identical demand is produced for every
scenario sharing a seed (SRS FR-05, FR-12).
"""
from __future__ import annotations

import math
import random
from datetime import timedelta


def build_demand(days, seed, factories, start_date):
    """Return ``(rows, lookup)`` where lookup is ``{(day, factory, sku): qty}``."""
    rng = random.Random(seed + 100)
    rows, lookup = [], {}
    for day in range(days):
        date_str = (start_date + timedelta(days=day)).isoformat()
        for factory in factories:
            for p in range(1, 4):
                qty = max(0, round(
                    15 * (1 + 0.15 * math.sin(2 * math.pi * day / 365))
                    + (4 if day % 7 < 5 else -5)
                    + rng.gauss(0, 2)
                ))
                sku = f"P{p}"
                rows.append(dict(
                    demand_id=f"D{len(rows) + 1:06}", day=day, date=date_str,
                    factory_id=factory, output_sku=sku, quantity=qty,
                ))
                lookup[day, factory, sku] = qty
    return rows, lookup
