"""Validation-layer tests (SRS section 5)."""
import unittest
from datetime import date

from simulation import master_data
from validation import validate_dataset


def base_tables():
    tables = master_data.build_master_data("baseline", 30, 1, date(2027, 1, 1))
    tables["hazard_events"] = []
    tables["asset_impacts"] = []
    tables["demand_orders"] = [
        dict(demand_id="D1", day=0, date="2027-01-01", factory_id="F1",
             output_sku="P1", quantity=1)
    ]
    return tables


class ValidationTest(unittest.TestCase):
    def test_valid_dataset_passes(self):
        tables = base_tables()
        report = validate_dataset(tables, expected_tables=tuple(tables))
        self.assertTrue(report.ok, report.format())

    def test_missing_table_is_error_when_expected(self):
        tables = base_tables()
        del tables["transport_links"]
        report = validate_dataset(tables, expected_tables=("transport_links",))
        self.assertFalse(report.ok)

    def test_bad_foreign_key_detected(self):
        tables = base_tables()
        tables["initial_inventory"][0]["sku_id"] = "CX"
        report = validate_dataset(tables)
        self.assertFalse(report.ok)
        self.assertTrue(any("does not reference" in i["message"] for i in report.errors))

    def test_self_referencing_bom_detected(self):
        tables = base_tables()
        tables["bill_of_materials"].append(
            dict(parent_sku="P1", component_sku="P1", quantity_per=1)
        )
        report = validate_dataset(tables)
        self.assertFalse(report.ok)

    def test_circular_bom_detected(self):
        tables = base_tables()
        tables["bill_of_materials"].extend([
            dict(parent_sku="P1", component_sku="P2", quantity_per=1),
            dict(parent_sku="P2", component_sku="P1", quantity_per=1),
        ])
        report = validate_dataset(tables)
        self.assertFalse(report.ok)

    def test_duplicate_logical_key_detected(self):
        tables = base_tables()
        tables["initial_inventory"].append(dict(tables["initial_inventory"][0]))
        report = validate_dataset(tables)
        self.assertFalse(report.ok)

    def test_negative_quantity_detected(self):
        tables = base_tables()
        tables["initial_inventory"][0]["quantity"] = -5
        report = validate_dataset(tables)
        self.assertFalse(report.ok)

    def test_out_of_range_multiplier_flagged(self):
        tables = base_tables()
        tables["hazard_events"] = [dict(
            event_id="E1", scenario_id="baseline", hazard_type="earthquake",
            start_day=1, end_day=2)]
        tables["asset_impacts"] = [dict(
            impact_id="I001", event_id="E1", asset_id="S1", start_day=1,
            end_day_exclusive=2, capacity_multiplier=1.5, reason="test")]
        report = validate_dataset(tables)
        # >1 is a warning, not a hard error
        self.assertTrue(any(i["level"] == "warning" for i in report.issues))


if __name__ == "__main__":
    unittest.main()
