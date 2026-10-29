import tempfile
import unittest
from pathlib import Path
from support_routing.anomalies import create_fixtures, validate_anomalies, detect

class AnomalyTests(unittest.TestCase):
    def test_all_five_controlled_anomalies_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            create_fixtures(data)
            report = validate_anomalies(data)
            self.assertEqual(report["cases_checked"], 5)
            self.assertEqual(report["detected"], 5)
            self.assertTrue(report["passed"], report)

    def test_normal_capacity_is_not_flagged(self):
        case = {"issue_type":"agent_over_capacity", "observed_condition":"active_count_exceeds_capacity", "details":"capacity=5;active_count=4"}
        self.assertFalse(detect(case))

if __name__ == "__main__": unittest.main()
