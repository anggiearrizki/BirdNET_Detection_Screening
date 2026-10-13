import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'automation'))
from birdnet_candidate_plan import select_group

def row(ident, value):
    return {'detection_id': ident, 'confidence': value, 'timestamp': '2026-09-30T12:00:00+07:00'}

class CandidatePlanTests(unittest.TestCase):
    def test_prefers_high_confidence_without_id_assumption(self):
        self.assertEqual(select_group([row(5, .2), row(1, .9)], {}, {}, 1), [1])
    def test_completed_generations_exhaust_species_budget(self):
        reviews = {1: {'generation_attempt_started_at': 'saved', 'status': 'review_note_ready'}}
        writes = {1: {'status': 'post_accepted_status_unchanged'}}
        self.assertEqual(select_group([row(1, .9), row(2, .8)], reviews, writes, 1), [])
    def test_saved_note_is_retained_for_posting_even_at_cap(self):
        reviews = {1: {'generation_attempt_started_at': 'saved', 'status': 'review_note_ready'}}
        self.assertEqual(select_group([row(1, .9), row(2, .8)], reviews, {}, 1), [1])
    def test_failed_generation_is_not_repeated(self):
        reviews = {1: {'generation_attempt_started_at': 'saved', 'status': 'generation_or_validation_failed'}}
        self.assertEqual(select_group([row(1, .9), row(2, .8)], reviews, {}, 1), [])
    def test_unknown_write_is_not_selected_for_fresh_generation(self):
        self.assertEqual(select_group([row(1, .9)], {}, {1: {'status': 'request_started'}}, 3), [])

if __name__ == '__main__': unittest.main()
