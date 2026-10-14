"""Engine integration tests (SRS section 8 acceptance criteria)."""
import unittest

from simulation import engine


class EngineTest(unittest.TestCase):
    def test_baseline_short_run_reconciles(self):
        summary, _inputs, outputs = engine.run_scenario("baseline", days=120, seed=7)
        self.assertEqual(summary["validation"], "passed")
        self.assertGreater(summary["total_demand"], 0)
        self.assertGreaterEqual(summary["ending_backlog"], 0)
        self.assertIn("inventory_transactions", outputs)
        self.assertIn("shipment_legs", outputs)

    def test_baseline_long_run_clears_backlog(self):
        summary, _inputs, _outputs = engine.run_scenario("baseline", days=730, seed=42)
        self.assertEqual(summary["ending_backlog"], 0)
        self.assertEqual(summary["demand_fulfilment_rate"], 1.0)

    def test_runs_are_reproducible_with_same_seed(self):
        first, _, _ = engine.run_scenario("typhoon", days=260, seed=11)
        second, _, _ = engine.run_scenario("typhoon", days=260, seed=11)
        self.assertEqual(first, second)

    def test_seed_changes_demand_stream(self):
        first, _, _ = engine.run_scenario("baseline", days=120, seed=1)
        second, _, _ = engine.run_scenario("baseline", days=120, seed=2)
        self.assertNotEqual(first["total_demand"], second["total_demand"])

    def test_disruption_changes_outcome(self):
        baseline, _, _ = engine.run_scenario("baseline", days=300, seed=11)
        compound, _, _ = engine.run_scenario("compound", days=300, seed=11)
        self.assertEqual(baseline["total_demand"], compound["total_demand"])
        self.assertNotEqual(
            baseline["transport_cost_incurred"],
            compound["transport_cost_incurred"],
        )


if __name__ == "__main__":
    unittest.main()
