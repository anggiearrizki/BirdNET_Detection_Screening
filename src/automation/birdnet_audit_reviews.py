"""Read local queue/review records; no API calls or changes to operational state."""
import argparse
import json
from collections import Counter
from pathlib import Path
from birdnet_recent_window import date_boundary, recording_time

ROOT = Path(__file__).resolve().parents[2]
STATIONS = ('CEMPEDAK_MAIN_KAMONG', 'CEMPEDAK_SOUTH_SIDE', 'NIKOI_MAIN')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def category(review, write):
    status = review.get('status')
    posted = write.get('status')
    if posted == 'post_accepted_status_unchanged':
        return 'posted_status_unchanged'
    if posted:
        return 'write_requires_attention'
    if status == 'screening_skipped_known_species':
        return 'skipped_known_species'
    if status == 'review_note_ready':
        return 'note_ready_not_posted'
    if status:
        return 'review_status_' + status
    return 'not_reviewed'

def audit(station, before):
    directory = ROOT / 'data' / 'processed' / 'birdnet' / station.lower()
    queue_path = directory / 'review_queue.json'
    if not queue_path.exists():
        raise ValueError(f'Queue missing: {queue_path}')
    queue = read(queue_path)
    counts = Counter()
    groups = {}
    for item in queue['detections']:
        if recording_time(item) >= before:
            continue
        detection_id = int(item['detection_id'])
        base = directory / 'review_packages' / f'detection_{detection_id}'
        review_path = base.with_name(base.name + '_review.json')
        write_path = base.with_name(base.name + '_writeback.json')
        review = read(review_path) if review_path.exists() else {}
        write = read(write_path) if write_path.exists() else {}
        for record in (review, write):
            if record and (record.get('station') != station or record.get('detection_id') != detection_id):
                raise ValueError(f'Provenance mismatch for {station}/{detection_id}')
        counts[category(review, write)] += 1
        packet = review.get('evidence_packet') or {}
        register = packet.get('register_check') or {}
        if register.get('status') != 'completed' or register.get('already_in_register') is not False:
            continue
        candidate = review.get('candidate') or {}
        name = candidate.get('scientific_name') or item.get('scientific_name') or 'UNKNOWN'
        group = groups.setdefault(name, [])
        result = review.get('gemini_result') or {}
        context = candidate.get('birdnet_data') or {}
        group.append({'id': detection_id, 'date': item.get('date'),
                      'state': category(review, write),
                      'assessment': result.get('audio_assessment'),
                      'recommendation': result.get('review_recommendation'),
                      'latitude': context.get('latitude'), 'longitude': context.get('longitude'),
                      'note': review.get('review_note'),
                      'url': f"{review.get('source_base_url', '').rstrip('/')}/ui/detections/{detection_id}?tab=notes"})
    return counts, groups

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--station', action='append', choices=STATIONS)
    parser.add_argument('--before-date', default='2026-10-01')
    parser.add_argument('--show-notes', action='store_true')
    args = parser.parse_args()
    before = date_boundary(args.before_date)
    for station in args.station or STATIONS:
        counts, groups = audit(station, before)
        print('\nSTATION:', station)
        print('Queued recordings before', args.before_date, '(UTC+7):', sum(counts.values()))
        for key, count in sorted(counts.items()):
            print(' ', key, ':', count)
        print('Distinct taxa absent from exported property list:', len(groups))
        for name, records in sorted(groups.items()):
            print('\nCANDIDATE:', name, '- recordings:', len(records))
            for r in records:
                print(r['id'], r['date'], r['state'], 'audio:', r['assessment'],
                      'recommendation:', r['recommendation'], 'coordinates:', r['latitude'], r['longitude'])
                print(r['url'])
                if args.show_notes and r['note']:
                    print(r['note'])
    print('\nLocal queue audit only: not proof of complete server coverage or current live-list absence.')
    print('Gemini calls: NO. BirdNET changes: NO.')

if __name__ == '__main__':
    main()