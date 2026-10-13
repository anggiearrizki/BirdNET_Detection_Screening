"""Plan property-unlisted candidate recordings before audio preparation."""
import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from birdnet_recent_window import date_boundary, recording_time

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / 'data' / 'processed' / 'local_reference_index.csv'

def key(name):
    return ' '.join(str(name or '').split()).casefold()

def confidence(row):
    try:
        value = float(row.get('confidence', 0))
        return value if math.isfinite(value) else 0
    except (ValueError, TypeError):
        return 0

def select_group(rows, reviews, writes, cap):
    """Saved notes first; every started generation counts against sample budget."""
    attempted = [r for r in rows if reviews.get(int(r['detection_id']), {}).get('generation_attempt_started_at')]
    saved = [r for r in rows if reviews.get(int(r['detection_id']), {}).get('status') == 'review_note_ready'
             and writes.get(int(r['detection_id']), {}).get('status') != 'post_accepted_status_unchanged']
    remaining = max(0, cap - len(attempted))
    fresh = [r for r in rows if not reviews.get(int(r['detection_id']), {}).get('generation_attempt_started_at')
             and not writes.get(int(r['detection_id']))]
    fresh.sort(key=lambda r: (confidence(r), recording_time(r)), reverse=True)
    return [int(r['detection_id']) for r in saved] + [int(r['detection_id']) for r in fresh[:remaining]]

def bird_classification(taxonomy):
    classes = {key(row.get('name') or row.get('canonicalName'))
               for row in taxonomy.get('classification', [])
               if str(row.get('rank', '')).upper() == 'CLASS'}
    if classes == {'aves'}:
        return 'bird'
    return 'non_bird' if classes else 'classification_review_required'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def build_plan(station, before_date, cap):
    from birdnet_station_config import get_station_config
    from birdnet_queue_worker import get_worker_paths, save_json, validate_queue
    for directory in (ROOT / 'src', ROOT / 'src' / 'evidence', ROOT / 'src' / 'taxonomy'):
        sys.path.insert(0, str(directory))
    from candidate_taxonomy import resolve_candidate_taxonomy
    from local_ref_lookup import lookup_local_reference
    config = get_station_config(station)
    paths = get_worker_paths(config['station'])
    queue = read(paths['queue_file'])
    # Scanner stores provenance on each detection, not on the queue root.
    validate_queue(queue, config)
    for row in queue['detections']:
        if row.get('source_base_url') not in (None, config['base_url']):
            raise ValueError('Queue item URL does not match selected station.')
    reference_hash = hashlib.sha256(INDEX.read_bytes()).hexdigest()
    before = date_boundary(before_date)
    groups = defaultdict(list)
    for row in queue['detections']:
        if recording_time(row) < before:
            if not key(row.get('scientific_name')):
                raise ValueError('Queue contains missing scientific name.')
            groups[key(row['scientific_name'])].append(row)
    reviews, writes = {}, {}
    for rows in groups.values():
        for row in rows:
            ident = int(row['detection_id'])
            for suffix, target in (('review', reviews), ('writeback', writes)):
                path = paths['package_dir'] / f'detection_{ident}_{suffix}.json'
                if path.exists():
                    record = read(path)
                    if (record.get('station') != config['station'] or record.get('detection_id') != ident
                            or record.get('source_base_url') != config['base_url']):
                        raise ValueError(f'{suffix} provenance mismatch: {ident}')
                    target[ident] = record
    accepted_groups = defaultdict(list)
    classifications = []
    for number, (name, rows) in enumerate(sorted(groups.items()), 1):
        print(f'Checking taxon {number}/{len(groups)}: {rows[0]["scientific_name"]}', flush=True)
        taxonomy = resolve_candidate_taxonomy(rows[0]['scientific_name'], expected_rank='species')
        if taxonomy.get('taxonomy_resolution_status') != 'resolved':
            classifications.append({'input_name': name, 'classification': 'taxonomy_review_required',
                                    'recordings': len(rows), 'taxonomy': taxonomy})
            continue
        bird_status = bird_classification(taxonomy)
        if bird_status != 'bird':
            classifications.append({'input_name': name, 'classification': bird_status,
                                    'recordings': len(rows), 'taxonomy': taxonomy})
            continue
        accepted = taxonomy['accepted_scientific_name']
        reference = lookup_local_reference(accepted, config['property'])
        listed = reference['local_reference_match']
        classifications.append({'input_name': name, 'accepted_name': accepted,
                                'classification': 'listed' if listed else 'unlisted', 'recordings': len(rows)})
        if not listed:
            accepted_groups[key(accepted)].extend(rows)
    # Interleave taxa so distinct candidates get a turn before repeat clips.
    selections = {name: select_group(rows, reviews, writes, cap) for name, rows in sorted(accepted_groups.items())}
    selected = [ids[index] for index in range(max((len(v) for v in selections.values()), default=0))
                for ids in selections.values() if index < len(ids)]
    plan = {'schema_version': '1.1', 'selection_policy': 'property_unlisted_aves_only', 'station': config['station'], 'property': config['property'],
            'source_base_url': config['base_url'], 'before_date': before_date,
            'generated_at': datetime.now(timezone.utc).isoformat(), 'reference_sha256': reference_hash,
            'max_recordings_per_taxon': cap, 'classifications': classifications,
            'candidate_selections': selections, 'selected_ids': selected,
            'scope': 'Absent from exported property list only; live platform not checked.'}
    output = paths['package_dir'].parent / 'candidate_plan.json'
    save_json(output, plan)
    print('Distinct input names checked:', len(groups))
    print('Distinct accepted unlisted taxa:', len(accepted_groups))
    print('Selected recordings:', len(selected))
    print('Plan:', output)
    print('Audio downloads: NO. Gemini calls: NO. BirdNET changes: NO.')

def load_plan(path, config):
    plan = read(Path(path))
    for field, expected in {'station': config['station'], 'property': config['property'],
                            'source_base_url': config['base_url']}.items():
        if plan.get(field) != expected:
            raise ValueError('Candidate plan mismatch: ' + field)
    if plan.get('reference_sha256') != hashlib.sha256(INDEX.read_bytes()).hexdigest():
        raise ValueError('Reference changed; regenerate the candidate plan.')
    if plan.get('selection_policy') != 'property_unlisted_aves_only':
        raise ValueError('Regenerate this plan with the bird-only planner before processing.')
    ids = plan['selected_ids']
    if any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Candidate plan IDs invalid or duplicated.')
    return plan

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--station', required=True)
    parser.add_argument('--before-date', default='2026-10-01')
    parser.add_argument('--per-species', type=int, default=3)
    args = parser.parse_args()
    if args.per_species <= 0:
        parser.error('--per-species must be positive.')
    date_boundary(args.before_date)
    build_plan(args.station, args.before_date, args.per_species)

if __name__ == '__main__':
    main()
