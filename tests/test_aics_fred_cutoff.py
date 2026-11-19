"""Clock boundary tests; no fake price/vintage observations are generated."""
import datetime as dt
import unittest

from scripts.aics_fred_cutoff import fred_realtime_day


class TestFredRealtimeDate(unittest.TestCase):
    def test_utc_midnight_while_st_louis_still_previous_day(self):
        clock=dt.datetime(2026,11,19,0,2,tzinfo=dt.timezone.utc)
        self.assertEqual(fred_realtime_day(clock),dt.date(2026,11,18))

    def test_utc_and_st_louis_calendar_agree(self):
        clock=dt.datetime(2026,11,19,20,0,tzinfo=dt.timezone.utc)
        self.assertEqual(fred_realtime_day(clock),dt.date(2026,11,19))

    def test_summer_daylight_time_uses_actual_timezone_database(self):
        clock=dt.datetime(2026,6,1,3,0,tzinfo=dt.timezone.utc)
        self.assertEqual(fred_realtime_day(clock),dt.date(2026,5,31))

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"offset-aware"):
            fred_realtime_day(dt.datetime(2026,11,19,0,0))


if __name__=="__main__":
    unittest.main()
