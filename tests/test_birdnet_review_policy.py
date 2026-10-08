import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'automation'))
from birdnet_review_policy import build_history, review_eligibility

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'species_history.json'
        self.config = dict(station='MAIN', property='Cempedak', base_url='http://example')
        self.rows = [dict(id=20, scientificName='Anthracoceros albirostris'),
                     dict(id=10, scientificName='Anthracoceros albirostris')]
        self.path.write_text(json.dumps(build_history(self.rows, self.config)))
    def check(self, member, row):
        return review_eligibility(dict(status='completed', already_in_register=member), row, self.config, self.path)
    def test_known_species_skipped(self):
        self.assertFalse(self.check(True, self.rows[0])['eligible'])
    def test_first_retained_detection_eligible(self):
        self.assertTrue(self.check(True, self.rows[1])['eligible'])
    def test_unlisted_species_remains_eligible_on_repeat(self):
        self.assertTrue(self.check(False, self.rows[0])['eligible'])
    def test_missing_history_needs_review(self):
        self.path.unlink()
        self.assertTrue(self.check(True, self.rows[0])['requires_review'])
    def test_cross_station_history_rejected(self):
        history=json.loads(self.path.read_text()); history['station']='SOUTH'
        self.path.write_text(json.dumps(history))
        with self.assertRaises(ValueError): self.check(True, self.rows[0])
    def test_unknown_membership_rejected(self):
        with self.assertRaises(ValueError): self.check(None, self.rows[0])

if __name__ == '__main__': unittest.main()
