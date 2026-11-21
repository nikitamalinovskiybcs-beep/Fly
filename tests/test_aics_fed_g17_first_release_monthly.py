"""Original Fed G17 release dates must not leak future semis observations into AICS."""
import copy
import unittest

from scripts.aics_fed_g17_first_release_monthly import INPUT, INITIAL, read, initial_publication
import json

class FedG17FirstReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(INPUT.read_text(encoding="utf-8"))

    def test_monthly_24_observations_reproduced(self):
        events=read(self.data)
        self.assertEqual(len(events),24)
        self.assertEqual(events[0]["observation_month"],"2024-11")
        self.assertEqual(events[0]["available_at"],"2024-12-17")
        self.assertEqual(events[0]["score"],"78.80")
        self.assertEqual(events[-1]["observation_month"],"2026-10")
        self.assertEqual(events[-1]["score"],"74.40")
        self.assertTrue(all(x["historically_pit_certified"] is False for x in events))


    def test_oct_2024_fed_original_first_available_nov_15(self):
        original=json.loads(INITIAL.read_text(encoding="utf-8"))
        event=initial_publication(original)
        self.assertEqual(event["observation_month"],"2024-10")
        self.assertEqual(event["available_at"],"2024-11-15")
        self.assertEqual(event["score"],"78.70")
        self.assertFalse(event["historically_pit_certified"])
        self.assertTrue(event["observation_first_published"])

    def test_oct_2024_release_not_eligible_before_actual_date(self):
        original=json.loads(INITIAL.read_text(encoding="utf-8"))
        for key,badval in (
            ("available_at","2024-10-31"),
            ("official_release_date","2024-10-15"),
            ("score","78.80"),
            ("independent_original_source_bytes_rehashed",True),
            ("source_original_bytes_sha256","0"*64),
            ("certified_aics",39.35),
        ):
            bad=copy.deepcopy(original)
            bad[key]=badval
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,"date gate"):
                initial_publication(bad)

    def test_shutdown_values_released_in_december_not_earlier(self):
        events={x["observation_month"]:x for x in read(self.data)}
        self.assertEqual(events["2025-09"]["available_at"],"2025-12-03")
        self.assertEqual(events["2025-10"]["available_at"],"2025-12-23")
        self.assertEqual(events["2025-11"]["available_at"],"2025-12-23")
        bad=copy.deepcopy(self.data)
        bad["observations"][11]["official_release_date"]="2025-11-17"
        bad["observations"][11]["asof_eligible_from"]="2025-11-17"
        with self.assertRaisesRegex(ValueError,"Government shutdown"):
            read(bad)

    def test_nonsequential_month_rejected(self):
        bad=copy.deepcopy(self.data)
        bad["observations"][3]["observation_month"]="2026-11"
        with self.assertRaisesRegex(ValueError,"date sequence"):
            read(bad)

    def test_mutable_current_cannot_be_immutable_fake_url(self):
        bad=copy.deepcopy(self.data)
        bad["observations"][-1]["source_url"]="https://www.federalreserve.gov/releases/g17/20261117/table2_sup.htm"
        with self.assertRaisesRegex(ValueError,"Original Fed source receipt"):
            read(bad)

    def test_no_raw_hash_or_certification_claim(self):
        bad=copy.deepcopy(self.data)
        bad["observations"][5]["original_bytes_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"Original Fed source"):
            read(bad)
        bad=copy.deepcopy(self.data)
        bad["independent_historical_pit_certified"]=True
        with self.assertRaisesRegex(ValueError,"promoted"):
            read(bad)

if __name__=="__main__":
    unittest.main()
