"""Production planning and BOM-driven component consumption (SRS section 6.3)."""
from __future__ import annotations

from .master_data import CAPACITY_PER_DAY


def run_production(ctx, effects, day, demand_map, backlog, ledger, records):
    """Execute one day of production for every factory / output SKU."""
    for factory in ctx.factories:
        for p in range(1, 4):
            output = f"P{p}"
            new_demand = demand_map[day, factory, output]
            backlog[factory, output] += new_demand

            requirements = ctx.bom_by_parent[output]
            possible = min(
                ledger.get(factory, b["component_sku"]) // b["quantity_per"]
                for b in requirements
            )
            capacity = int(CAPACITY_PER_DAY * effects.multiplier(factory, day))
            produced = min(backlog[factory, output], possible, capacity)

            for b in requirements:
                if produced:
                    ledger.apply(
                        day, factory, b["component_sku"],
                        -produced * b["quantity_per"],
                        "production_consumption", f"{factory}_{output}_{day}",
                    )
            backlog[factory, output] -= produced
            records.append(dict(
                day=day, factory_id=factory, output_sku=output,
                new_demand=new_demand, produced=produced,
                backlog=backlog[factory, output], capacity=capacity,
                material_limited=int(
                    possible < min(backlog[factory, output] + produced, capacity)
                ),
            ))
