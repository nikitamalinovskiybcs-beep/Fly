import unittest
from decimal import Decimal

from scripts.aics_release_check import RELEASE, check_release, load


class ResearchReleaseTest(unittest.TestCase):
    def test_dated_release_and_original_rubric(self):
        report = check_release(load(RELEASE))
        self.assertEqual((report["technical_steps_completed"], report["original_rubric_completed"]), (66, 55))
        self.assertEqual((report["untouched_24m_oos_nodes"], report["independently_certified_nodes"]), (0, 0))
        self.assertEqual(len(report["nodes"]), 11)
        self.assertIsNone(report["certified_aics"])
        self.assertEqual(sum(Decimal(n["points"]) for n in report["nodes"]), Decimal("669.09375"))

    def test_changed_source_loses_acceptance(self):
        release = load(RELEASE)
        source = release["inputs_by_node"]["Power/Data Centers"][1]
        release["input_sha256"][source] = "0" * 64
        report = check_release(release)
        power = next(r for r in report["nodes"] if r["node"] == "Power/Data Centers")
        self.assertEqual(power["changed_inputs"], [source])
        self.assertEqual(power["completed"], 2)
        self.assertLess(report["technical_steps_completed"], 66)

    def test_changed_score_cannot_be_hidden_by_unchanged_index(self):
        release = load(RELEASE)
        release["first_publication"]["scores"]["UST 30Y"] += 1
        report = check_release(release)
        ust = next(r for r in report["nodes"] if r["node"] == "UST 30Y")
        self.assertIn("node_score_reproduced", ust["failed_checks"])
        self.assertLess(report["technical_steps_completed"], 66)

    def test_mismatch_with_published_total_blocks_all_final_steps(self):
        release = load(RELEASE)
        release["first_publication"]["research_aics"] += 1
        report = check_release(release)
        self.assertEqual(report["technical_steps_completed"], 55)
        self.assertTrue(all(r["failed_checks"] == ["contribution_reconciled"] for r in report["nodes"]))
