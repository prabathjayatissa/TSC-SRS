"""Master-data construction for the synthetic Taiwan IT supply chain.

All coordinates are illustrative anchors, not surveyed assets; every parameter
is fictional and is not calibrated to any real operation.
"""
from __future__ import annotations

SCENARIOS = ["baseline", "earthquake", "typhoon", "landslide", "heat", "compound"]

FACTORY_IDS = [f"F{i}" for i in range(1, 7)]
COMPONENT_IDS = [f"C{k:02}" for k in range(1, 16)]
OUTPUT_SKUS = ["P1", "P2", "P3"]
CAPACITY_PER_DAY = 30

DESTINATIONS = [
    ("NL", 51.9, 4.5),
    ("AT", 48.2, 16.4),
    ("US", 33.7, -118.2),
    ("MX", 19.4, -99.1),
    ("JP", 35.6, 139.7),
    ("SG", 1.3, 103.8),
]

SEA_TRANSIT_DAYS = [30, 34, 20, 25, 5, 6]


def build_master_data(scenario, days, seed, start_date):
    """Return the master-data tables for one scenario as ``{table_name: rows}``."""
    tables = {}

    def put(name, rows):
        tables[name] = rows
        return rows

    put("scenarios", [dict(
        scenario_id=scenario, seed=seed, days=days, start_date=str(start_date),
        parameter_status="fictional_not_calibrated",
    )])
    put("suppliers", [dict(
        supplier_id="SUP1", name="Taiwan Digital Systems (fictional)", country="TW",
    )])

    specs = [
        ("S1", "supplier_factory", "TW", 24.78, 121.00),
        ("D1", "supplier_dc", "TW", 25.00, 121.20),
        ("TWP", "port", "TW", 25.15, 121.75),
        ("TWA", "airport", "TW", 25.08, 121.23),
    ]
    for i, (country, lat, lon) in enumerate(DESTINATIONS, 1):
        specs.append((f"H{i}", "destination_hub", country, lat, lon))
        specs.append((f"F{i}", "factory", country, lat + 0.08, lon + 0.08))

    put("nodes", [dict(
        node_id=n, node_type=t, country=c, latitude=la, longitude=lo,
        supplier_id="SUP1" if n in ("S1", "D1") else "",
        daily_handling_units=6000, power_dependency="high",
        water_dependency="high" if n == "S1" else "low",
        coordinate_status="illustrative",
    ) for n, t, c, la, lo in specs])

    products = []
    for k in range(1, 16):
        products.append(dict(
            sku_id=f"C{k:02}",
            product_level=(
                "complete_subsystem" if k > 12 else ("module" if k > 8 else "semiconductor")
            ),
            uom="piece", units_per_pack=10, weight_kg=round(0.02 * k, 2),
            volume_m3=round(0.0001 * k, 4), unit_value=20 * k,
            substitution_group="", handling_class="dry_protected",
        ))
    for k in range(1, 4):
        products.append(dict(
            sku_id=f"P{k}", product_level="manufactured_output", uom="piece",
            units_per_pack=1, weight_kg=5, volume_m3=0.03, unit_value=2500,
            substitution_group="", handling_class="standard",
        ))
    put("products", products)

    put("bill_of_materials", [dict(
        parent_sku=f"P{p}", component_sku=f"C{k:02}",
        quantity_per=2 if k <= 3 else 1,
    ) for p in range(1, 4) for k in [p, p + 3, p + 6, p + 9, p + 12]])

    put("factory_products", [dict(
        factory_id=f, output_sku=f"P{p}", capacity_per_day=30, priority=p,
    ) for f in FACTORY_IDS for p in range(1, 4)])

    links = [
        dict(link_id="L_SD", from_node="S1", to_node="D1", mode="road",
             transit_days=1, daily_capacity_units=5000, departure_interval_days=1,
             cost_per_unit=0.1),
        dict(link_id="L_DP", from_node="D1", to_node="TWP", mode="road",
             transit_days=1, daily_capacity_units=4500, departure_interval_days=1,
             cost_per_unit=0.2),
        dict(link_id="L_DA", from_node="D1", to_node="TWA", mode="road",
             transit_days=1, daily_capacity_units=2000, departure_interval_days=1,
             cost_per_unit=0.4),
    ]
    routes, route_legs, route_map = [], [], {}
    for i, sea_days in enumerate(SEA_TRANSIT_DAYS, 1):
        for mode, transit, cap, interval, cost in (
            ("sea", sea_days, 3500, 7, 2.0),
            ("air", 2, 900, 1, 15.0),
        ):
            mid = f"L_{mode}{i}"
            last = f"L_LAST{i}"
            origin = "TWP" if mode == "sea" else "TWA"
            links.append(dict(
                link_id=mid, from_node=origin, to_node=f"H{i}", mode=mode,
                transit_days=transit, daily_capacity_units=cap,
                departure_interval_days=interval, cost_per_unit=cost,
            ))
            # The final road leg is created once per destination (on the sea pass)
            # and reused by the matching air route.
            if mode == "sea":
                links.append(dict(
                    link_id=last, from_node=f"H{i}", to_node=f"F{i}", mode="road",
                    transit_days=2, daily_capacity_units=1800,
                    departure_interval_days=1, cost_per_unit=0.3,
                ))
            rid = f"R{i}_{mode}"
            route_map[rid] = ["L_SD", "L_DP" if mode == "sea" else "L_DA", mid, last]
            routes.append(dict(
                route_id=rid, factory_id=f"F{i}",
                route_type="primary" if mode == "sea" else "expedite",
                activation_days=0 if mode == "sea" else 2,
            ))
            route_legs.extend(
                dict(route_id=rid, sequence=j, link_id=l)
                for j, l in enumerate(route_map[rid], 1)
            )

    put("transport_links", links)
    put("routes", routes)
    put("route_legs", route_legs)

    put("initial_inventory", [
        dict(factory_id=f, sku_id=c, quantity=1500 if int(c[1:]) <= 3 else 750)
        for f in FACTORY_IDS for c in COMPONENT_IDS
    ])

    put("inventory_policies", [dict(
        factory_id=f, sku_id=c,
        target_units=2400 if int(c[1:]) <= 3 else 1200,
        review_interval_days=7,
        expedite_trigger_units=300 if int(c[1:]) <= 3 else 150,
    ) for f in FACTORY_IDS for c in COMPONENT_IDS])

    return tables
