"""Build a property-level human-review shortlist from saved results. No API calls."""
import argparse
import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
from birdnet_audit_reviews import ROOT, STATIONS, category, read
from birdnet_recent_window import date_boundary, recording_time

PROPERTIES = {'CEMPEDAK_MAIN_KAMONG': 'Cempedak', 'CEMPEDAK_SOUTH_SIDE': 'Cempedak', 'NIKOI_MAIN': 'Nikoi'}


def build_shortlist(root, stations, before):
    groups = {}
    for station in stations:
        directory = root / 'data/processed/birdnet' / station.lower()
        queue = read(directory / 'review_queue.json')
        for item in queue['detections']:
            if recording_time(item) >= before:
                continue
            detection_id = int(item['detection_id'])
            path = directory / 'review_packages' / f'detection_{detection_id}_review.json'
            if not path.exists():
                continue
            review = read(path)
            if review.get('station') != station or review.get('detection_id') != detection_id or review.get('property') != PROPERTIES[station]:
                raise ValueError(f'Review provenance mismatch: {station}/{detection_id}')
            packet = review.get('evidence_packet') or {}
            register = packet.get('register_check') or {}
            if register.get('status') != 'completed' or register.get('already_in_register') is not False:
                continue
            candidate = review.get('candidate') or {}
            taxonomy = packet.get('taxonomy') or {}
            accepted = taxonomy.get('accepted_scientific_name')
            resolved = taxonomy.get('taxonomy_resolution_status') == 'resolved' and bool(accepted)
            name = accepted if resolved else candidate.get('scientific_name') or item.get('scientific_name') or 'UNKNOWN'
            # Unresolved labels are kept separate from accepted taxonomic groups.
            key = (PROPERTIES[station], str(name).strip().casefold(), resolved)
            group = groups.setdefault(key, {'property': PROPERTIES[station], 'scientific_name': name,
                'taxonomy_resolved': resolved, 'input_names': set(), 'common_names': set(), 'records': []})
            group['input_names'].add(candidate.get('scientific_name') or name)
            if candidate.get('common_name'):
                group['common_names'].add(candidate['common_name'])
            write_path = path.with_name(path.name.replace('_review.json', '_writeback.json'))
            write = read(write_path) if write_path.exists() else {}
            if write and (write.get('station') != station or write.get('detection_id') != detection_id):
                raise ValueError(f'Writeback provenance mismatch: {station}/{detection_id}')
            result = review.get('gemini_result') or {}
            base = review.get('source_base_url') or item.get('source_base_url') or ''
            parsed = urlsplit(base)
            url = f'{base.rstrip("/")}/ui/detections/{detection_id}?tab=notes' if parsed.scheme in ('http', 'https') and parsed.netloc else None
            group['records'].append({'station': station, 'detection_id': detection_id, 'date': item.get('date'),
                'assessment': result.get('audio_assessment'), 'write_state': category(review, write),
                'note': review.get('review_note'), 'recommendation': result.get('review_recommendation'), 'url': url})
    output = []
    for group in groups.values():
        counts = Counter(r['assessment'] for r in group['records'] if r['assessment'] in ('consistent', 'inconsistent', 'uncertain'))
        if not group['taxonomy_resolved']:
            priority = 'taxonomy_review_required'
        elif counts['consistent']:
            priority = 'supporting_audio_for_human_review'
        elif counts['uncertain']:
            priority = 'uncertain_audio_for_human_review'
        elif counts['inconsistent']:
            priority = 'inconsistent_audio_only'
        else:
            priority = 'assessment_pending'
        group.update(priority=priority, assessment_counts=dict(counts),
                     input_names=sorted(group['input_names']), common_names=sorted(group['common_names']),
                     live_list_check='not_performed', biological_confirmation='not_established')
        group['records'].sort(key=lambda r: (r['date'] or '', r['station'], r['detection_id']))
        output.append(group)
    order = {'supporting_audio_for_human_review': 0, 'uncertain_audio_for_human_review': 1,
             'taxonomy_review_required': 2, 'assessment_pending': 3, 'inconsistent_audio_only': 4}
    return sorted(output, key=lambda g: (g['property'], order[g['priority']], g['scientific_name']))


def write_html(path, groups, before_date):
    def esc(value):
        return html.escape(str(value), quote=True)
    content = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>BirdNET species shortlist</title>',
        '<style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#243447}h1,h2{color:#173952}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}th{background:#edf3f6}article{border-top:2px solid #dde6ec;margin-top:35px}summary{cursor:pointer;padding:10px;background:#f3f6f8}a{color:#146489}small{color:#526477}</style>',
        '<h1>BirdNET species shortlist</h1>', f'<p>Saved recordings before {esc(before_date)} (UTC+7). Cempedak stations are combined at property level.</p>',
        '<p><strong>For human review:</strong> list absence is based on saved checks against an exported list. The live Flora and Fauna list has not been checked by this report. Supporting Gemini audio is not confirmation of presence. No species additions or verification changes have been made.</p>',
        '<table><tr><th>Property</th><th>Candidate groups</th><th>Supporting audio</th><th>Uncertain</th><th>Inconsistent only</th><th>Pending / taxonomy</th></tr>']
    for prop in sorted({g['property'] for g in groups}):
        gs = [g for g in groups if g['property'] == prop]; counts = Counter(g['priority'] for g in gs)
        content.append('<tr>' + ''.join(f'<td>{esc(v)}</td>' for v in [prop,len(gs),counts['supporting_audio_for_human_review'],counts['uncertain_audio_for_human_review'],counts['inconsistent_audio_only'],counts['assessment_pending']+counts['taxonomy_review_required']]) + '</tr>')
    content.append('</table>')
    for group in groups:
        content.extend([f'<article><h2>{esc(group["property"])}: {esc(group["scientific_name"])}</h2>',
            f'<p>{esc(", ".join(group["common_names"]))}<br><strong>{esc(group["priority"].replace("_", " "))}</strong><br>Assessments: {esc(group["assessment_counts"])}<br>Original labels: {esc(", ".join(group["input_names"]))}</p>'])
        for r in group['records']:
            link = f'<a href="{esc(r["url"])}" target="_blank" rel="noopener">Open BirdNET notes</a>' if r['url'] else 'BirdNET URL unavailable'
            content.append(f'<details><summary>{esc(r["station"])} / {r["detection_id"]} / {esc(r["date"])} / {esc(r["assessment"] or "pending")}</summary><p>{link}<br><small>Writeback: {esc(r["write_state"])}</small></p>')
            content.append(f'<p>{esc(r["note"] or "No saved review note.")}</p><p><small>Model recommendation: {esc(r["recommendation"] or "Not available")}</small></p></details>')
        content.append('</article>')
    content.append('</html>')
    path.write_text('\n'.join(content), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--station', action='append', choices=STATIONS)
    parser.add_argument('--before-date', default='2026-10-01')
    args = parser.parse_args()
    groups = build_shortlist(ROOT, args.station or STATIONS, date_boundary(args.before_date))
    output = ROOT / 'data/processed/birdnet/human_review'
    output.mkdir(parents=True, exist_ok=True)
    stem = f'species_shortlist_before_{args.before_date}'
    data = output / (stem + '.json'); page = output / (stem + '.html')
    data.write_text(json.dumps({'before_date': args.before_date, 'source': 'saved local reviews', 'live_list_check': 'not_performed', 'groups': groups}, indent=2, ensure_ascii=False), encoding='utf-8')
    write_html(page, groups, args.before_date)
    for prop in sorted({g['property'] for g in groups}):
        selected = [g for g in groups if g['property'] == prop]
        print(prop, '| candidate groups:', len(selected), '| priorities:', dict(Counter(g['priority'] for g in selected)))
    print('HTML:', page); print('JSON:', data)
    print('API calls: NO. Gemini calls: NO. BirdNET / species list changes: NO.')

if __name__ == '__main__':
    main()
