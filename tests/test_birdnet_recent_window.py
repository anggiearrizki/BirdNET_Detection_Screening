import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "automation"))
from birdnet_recent_window import recording_time, recent_ids

class RecentWindowTests(unittest.TestCase):
    def test_offset_and_utc_equal(self):
        self.assertEqual(recording_time({"timestamp":"2026-10-07T12:00:00+07:00"}), recording_time({"timestamp":"2026-10-07T05:00:00Z"}))
    def test_local_fallback(self):
        self.assertEqual(recording_time({"date":"2026-10-07", "time":"12:00:00"}), datetime(2026,10,7,5,tzinfo=timezone.utc))
    def test_boundary_and_newest_first(self):
        rows=[{"detection_id":9,"timestamp":"2026-10-07T05:00:00Z"}, {"detection_id":1,"timestamp":"2026-10-08T05:00:00Z"}, {"detection_id":10,"timestamp":"2026-10-07T04:59:59Z"}]
        self.assertEqual(recent_ids(rows,datetime(2026,10,7,5,tzinfo=timezone.utc)),[1,9])
    def test_missing_time_fails(self):
        with self.assertRaises(ValueError): recording_time({"date":"2026-10-07"})
    def test_empty_queue(self):
        self.assertEqual(recent_ids([],datetime.now(timezone.utc)),[])

if __name__ == "__main__": unittest.main()
