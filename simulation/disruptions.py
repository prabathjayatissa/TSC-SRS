"""Disruption modelling: hazard events and their time-bounded asset impacts.

Overlapping impacts on the same asset are combined with the most restrictive
(minimum) multiplier rule (SRS section 6.4). This policy is documented here and
applied consistently by :class:`EffectModel`.
"""
from __future__ import annotations

from datetime import timedelta


class EffectModel:
    """Maps ``(asset, day)`` to an effective capacity multiplier in ``[0, 1]``."""

    def __init__(self, impacts):
        self.impacts = impacts
        self._by_asset = {}
        for row in impacts:
            self._by_asset.setdefault(row["asset_id"], []).append(row)

    def multiplier(self, asset, day):
        best = 1.0
        for row in self._by_asset.get(asset, ()):
            if row["start_day"] <= day < row["end_day_exclusive"]:
                if row["capacity_multiplier"] < best:
                    best = row["capacity_multiplier"]
        return best


def build_hazards(scenario, start_date):
    """Return ``(events, impacts)`` for a scenario."""
    iso = lambda d: (start_date + timedelta(days=d)).isoformat()
    events, impacts = [], []

    def event(event_id, hazard, day, duration, lat, lon, metric, value, unit,
              parent="", group=""):
        events.append(dict(
            event_id=event_id, scenario_id=scenario, hazard_type=hazard,
            start_day=day, end_day=day + duration,
            start_date=iso(day), end_date_exclusive=iso(day + duration),
            latitude=lat, longitude=lon, intensity_metric=metric, intensity=value,
            unit=unit, parent_event_id=parent, event_group_id=group or event_id,
            observed_day=max(0, day - 1) if hazard in ("typhoon", "heat") else day,
            uncertainty="scenario_not_probability",
        ))

    def impact(event_id, asset, day, duration, mult, reason):
        impacts.append(dict(
            impact_id=f"I{len(impacts) + 1:03}", event_id=event_id, asset_id=asset,
            start_day=day, end_day_exclusive=day + duration,
            capacity_multiplier=mult, reason=reason,
        ))

    if scenario in ("earthquake", "compound"):
        event("E1", "earthquake", 90, 1, 24.7, 121.1, "PGA", 0.3, "g", group="G1")
        impact("E1", "S1", 90, 3, 0, "inspection_and_power")
        impact("E1", "S1", 93, 5, 0.4, "restart")
        impact("E1", "S1", 98, 5, 0.75, "ramp_up")
        event("E2", "tsunami", 91, 1, 25.2, 121.8, "inundation_depth", 1.5, "m",
              parent="E1", group="G1")
        impact("E2", "TWP", 91, 5, 0, "synthetic_coastal_closure")
        impact("E2", "TWP", 96, 6, 0.5, "recovery")
    if scenario in ("typhoon", "compound"):
        event("E3", "typhoon", 210, 5, 24.9, 121.6, "maximum_wind", 45, "m/s", group="G2")
        impact("E3", "TWP", 210, 5, 0, "port_closure")
        impact("E3", "TWA", 210, 3, 0, "airport_closure")
        impact("E3", "L_DP", 210, 7, 0.4, "road_restriction")
    if scenario in ("landslide", "compound"):
        event("E4", "extreme_rain", 214, 3, 24.9, 121.4, "daily_rainfall", 240, "mm/day",
              parent="E3" if scenario == "compound" else "", group="G2")
        event("E5", "landslide", 215, 8, 24.95, 121.35, "blocked_road_length", 0.5, "km",
              parent="E4", group="G2")
        impact("E5", "L_DP", 215, 8, 0, "road_blockage")
        impact("E5", "L_DA", 215, 4, 0.5, "shared_access_constraints")
    if scenario in ("heat", "compound"):
        event("E6", "heat", 230, 12, 19.4, -99.1, "daily_max_temperature", 42, "C")
        impact("E6", "F4", 230, 12, 0.55, "heat_reduced_productivity")

    return events, impacts
