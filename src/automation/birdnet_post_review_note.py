"""Post saved notes. Retry only a recorded explicit HTTP 401 rejection.
Unknown outcomes never cause automatic repeat posting. Accepted POSTs can
resume metadata readback without sending another POST.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SRC_DIR.parent / '.env', override=True)
sys.path[:0] = [str(SRC_DIR), str(SRC_DIR / 'automation')]
from birdnet_station_config import get_station_config
from birdnet_queue_worker import get_worker_paths, save_json, utc_now
from integration.birdnet_client import get_detection
from integration import birdnet_review_writer as writer
from ai.gemini_response import validate_gemini_response

SUCCESS = 'post_accepted_status_unchanged'
READBACK = {'post_accepted', 'post_accepted_readback_failed'}

def post_note(station, detection_id, station_credentials=False):
    config = get_station_config(station)
    directory = get_worker_paths(config['station'])['package_dir']
    record_path = directory / f'detection_{detection_id}_writeback.json'
    review = json.loads((directory / f'detection_{detection_id}_review.json').read_text(encoding='utf-8'))
    expected = dict(station=config['station'], property=config['property'],
                    detection_id=detection_id, source_base_url=config['base_url'])
    for key, value in expected.items():
        if review.get(key) != value:
            raise ValueError(f'Review mismatch: {key}')
    if review.get('status') != 'review_note_ready':
        raise ValueError('Review note is not ready.')
    validate_gemini_response(review.get('gemini_result'))
    note = review.get('review_note')
    writer.build_comment_payload(note)
    note_hash = hashlib.sha256(note.strip().encode()).hexdigest()
    previous = None
    if record_path.exists():
        previous = json.loads(record_path.read_text(encoding='utf-8'))
        for key, value in expected.items():
            if previous.get(key) != value:
                raise ValueError(f'Write record mismatch: {key}')
        if previous.get('status') == SUCCESS:
            print('Already completed. No POST or Gemini call.')
            return
        if previous.get('status') not in READBACK | {'authentication_rejected'}:
            raise RuntimeError('Uncertain write outcome. Check BirdNET Notes; no repeat POST.')
        if previous.get('note_sha256') not in (None, note_hash):
            raise RuntimeError('Saved note changed since write attempt; inspect it first.')
    writer.BIRDNET_BASE_URL = config['base_url']
    # Accepted writes only need readback, not a new authenticated POST.
    if previous and previous['status'] in READBACK:
        record = previous
    else:
        before = get_detection(detection_id, base_url=config['base_url'])
        if int(before['id']) != detection_id:
            raise ValueError('Wrong detection returned.')
        if before.get('verified') != 'unverified' or before.get('locked') is not False:
            raise ValueError('Detection has been reviewed or locked; no POST.')
        session = writer.build_authenticated_session(
            config['station'] if station_credentials else None)
        record = dict(**expected, started_at=utc_now(), status='request_started',
                      note_sha256=note_hash, verified_before=before['verified'],
                      locked_before=before['locked'], verification_status_sent=False,
                      lock_status_sent=False, attempts=list((previous or {}).get('attempts', [])))
        record['attempts'].append({'started_at': record['started_at']})
        try:
            if previous:
                save_json(record_path, record)
            else:
                with record_path.open('x', encoding='utf-8') as handle:
                    json.dump(record, handle, indent=2)
            try:
                response = writer.write_comment(detection_id, note, session=session)
                record.update(http_status=response.status_code, status='post_accepted')
                record['attempts'][-1]['http_status'] = response.status_code
                save_json(record_path, record)
            except Exception as exc:
                status = getattr(exc, 'http_status', None)
                record.update(status='authentication_rejected' if status == 401
                              else 'write_outcome_requires_check',
                              http_status=status, error_type=type(exc).__name__,
                              finished_at=utc_now())
                record['attempts'][-1]['http_status'] = status
                save_json(record_path, record)
                if status == 401:
                    print('Authentication expired. Refresh .env credentials and resume; saved Gemini review retained.')
                raise
        finally:
            session.close()
    try:
        after = get_detection(detection_id, base_url=config['base_url'])
        if int(after['id']) != detection_id:
            raise ValueError('Wrong detection returned during readback.')
        unchanged = (after.get('verified') == record['verified_before']
                     and after.get('locked') == record['locked_before'])
        record.update(verified_after=after.get('verified'), locked_after=after.get('locked'),
                      status_fields_unchanged=unchanged, finished_at=utc_now(),
                      status=SUCCESS if unchanged else 'post_accepted_status_changed')
        save_json(record_path, record)
    except Exception:
        record['status'] = 'post_accepted_readback_failed'
        save_json(record_path, record)
        raise
    if not unchanged:
        raise RuntimeError('Status changed after POST; inspect BirdNET. No repeat POST.')
    print('BirdNET accepted the comment POST; status fields unchanged: True')
    print('Gemini calls made: NO')
    print('Write record:', record_path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--station', required=True)
    parser.add_argument('--detection-id', type=int, required=True)
    parser.add_argument('--station-credentials', action='store_true')
    args = parser.parse_args()
    if args.detection_id <= 0:
        parser.error('Detection ID must be positive.')
    post_note(args.station, args.detection_id, args.station_credentials)

if __name__ == '__main__':
    main()
