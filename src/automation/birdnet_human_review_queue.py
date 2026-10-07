"""Build a local human-review page from saved BirdNET reviews."""

import argparse
import hashlib
import html
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from birdnet_station_config import get_station_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed" / "birdnet"
DEFAULT_STATIONS = [
    "CEMPEDAK_MAIN_KAMONG",
    "CEMPEDAK_SOUTH_SIDE",
]


def read_json(path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def escape(value):
    return html.escape(str(value if value is not None else ""))


def collect_reviews(stations):
    cases = {}
    problems = []
    inspected = 0
    unfinished = 0

    for station in stations:
        config = get_station_config(station)
        directory = DATA_DIR / config["station"].lower() / "review_packages"

        if not directory.exists():
            problems.append(f"{config['station']}: no review package folder.")
            continue

        for path in sorted(directory.glob("detection_*_review.json")):
            inspected += 1
            try:
                review = read_json(path)
                detection_id = int(review["detection_id"])
                expected = {
                    "station": config["station"],
                    "property": config["property"],
                    "source_base_url": config["base_url"],
                }
                for field, value in expected.items():
                    if review.get(field) != value:
                        raise ValueError(f"Provenance mismatch: {field}")

                if path.name != f"detection_{detection_id}_review.json":
                    raise ValueError("Filename and detection ID differ.")

                if review.get("status") != "review_note_ready":
                    unfinished += 1
                    continue

                candidate = review["candidate"]
                packet = review["evidence_packet"]
                register = packet["register_check"]
                gemini = review["gemini_result"]

                if not isinstance(gemini, dict):
                    raise ValueError("Missing validated Gemini result.")

                reasons = []
                if register.get("status") != "completed":
                    reasons.append("Species-list check incomplete")
                elif (
                    register.get("already_in_register") is False
                    or register.get("species_register_review_required") is True
                ):
                    reasons.append("Species absent from reference / register review")

                assessment = gemini.get("audio_assessment")
                if assessment in ("inconsistent", "uncertain"):
                    reasons.append(f"Audio assessment: {assessment}")

                if gemini.get("recommended_status") in (
                    "false_positive",
                    "review_required",
                ):
                    reasons.append(
                        f"AI recommendation: {gemini['recommended_status']}"
                    )

                if not reasons:
                    continue

                metadata = {}
                package_path = directory / f"detection_{detection_id}.json"
                if package_path.exists():
                    package = read_json(package_path)
                    for field, value in expected.items():
                        if package.get(field) != value:
                            raise ValueError(f"Prepared package mismatch: {field}")
                    if int(package["detection_id"]) != detection_id:
                        raise ValueError("Prepared package ID mismatch.")
                    metadata = package.get("birdnet_detection", {})

                birdnet = candidate.get("birdnet_data", {})
                scientific_name = candidate.get("scientific_name")
                if not scientific_name:
                    raise ValueError("Scientific name is missing.")

                write_path = directory / f"detection_{detection_id}_writeback.json"
                write_status = "No local write record"
                if write_path.exists():
                    write_record = read_json(write_path)
                    for field, value in expected.items():
                        if write_record.get(field) != value:
                            raise ValueError(f"Write record mismatch: {field}")
                    if int(write_record["detection_id"]) != detection_id:
                        raise ValueError("Write record ID mismatch.")
                    write_status = write_record.get("status", "Unknown")

                key = (config["station"], detection_id)
                cases[key] = {
                    "station": config["station"],
                    "property": config["property"],
                    "detection_id": detection_id,
                    "scientific_name": scientific_name,
                    "common_name": candidate.get("common_name"),
                    "timestamp": (
                        metadata.get("timestamp")
                        or birdnet.get("detection_datetime")
                        or birdnet.get("datetime")
                    ),
                    "begin_time": metadata.get("beginTime"),
                    "end_time": metadata.get("endTime"),
                    "confidence": metadata.get(
                        "confidence",
                        birdnet.get("detection_confidence",
                                    birdnet.get("confidence")),
                    ),
                    "audio_sha256": review.get("audio_sha256"),
                    "reasons": reasons,
                    "audio_assessment": assessment,
                    "audio_explanation": gemini.get("audio_evidence", ""),
                    "uncertainties": gemini.get("uncertainties", []),
                    "register_check": register,
                    "write_status": write_status,
                    "birdnet_url": (
                        f"{config['base_url']}/ui/detections/"
                        f"{detection_id}?tab=notes"
                    ),
                    "source_review_file": str(path),
                }

            except (ValueError, KeyError, TypeError, OSError) as exc:
                problems.append(f"{path.name} ({config['station']}): {exc}")

    return list(cases.values()), problems, inspected, unfinished


def render_page(cases, problems, inspected, unfinished):
    groups = defaultdict(list)
    for case in cases:
        groups[(case["property"], case["scientific_name"])].append(case)

    sections = []
    for (property_name, species), records in sorted(groups.items()):
        records.sort(key=lambda item: (item["station"], item["detection_id"]))
        hashes = defaultdict(list)
        for record in records:
            if record["audio_sha256"]:
                hashes[record["audio_sha256"]].append(record)

        cards = []
        for record in records:
            same_audio = hashes.get(record["audio_sha256"], [])
            duplicate = (
                "<p class='warning'>Identical audio bytes occur in another "
                "case in this group. These are not independent recordings.</p>"
                if len(same_audio) > 1 else ""
            )
            uncertainties = record["uncertainties"]
            if not isinstance(uncertainties, list):
                uncertainties = [str(uncertainties)]
            uncertainty_html = "".join(
                f"<li>{escape(item)}</li>" for item in uncertainties
            )

            cards.append(f"""
            <article>
              <h3>{escape(record['station'])} · {record['detection_id']}</h3>
              <p><strong>Review reasons:</strong>
                 {escape('; '.join(record['reasons']))}</p>
              <p>Recorded: {escape(record['timestamp'] or 'Not available')}
                 <br>Clip interval:
                 {escape(record['begin_time'] or 'Not available')} to
                 {escape(record['end_time'] or 'Not available')}
                 <br>BirdNET confidence (0–1):
                 {escape(record['confidence'])}</p>
              {duplicate}
              <p>{escape(record['audio_explanation'])}</p>
              <ul>{uncertainty_html}</ul>
              <p class="small">Local posting status:
                 {escape(record['write_status'])}</p>
              <a href="{escape(record['birdnet_url'])}"
                 target="_blank" rel="noopener noreferrer">
                 Open detection, audio and Notes in BirdNET</a>
            </article>
            """)

        sections.append(f"""
        <section>
          <h2>{escape(species)} · {escape(property_name)}</h2>
          <p>{escape(records[0]['common_name'])} ·
             {len(records)} flagged detection(s)</p>
          <p class="small">Detection count is not a count of independent
          observations. Compare clip intervals and listen for overlapping
          recordings before assessing the evidence.</p>
          {''.join(cards)}
        </section>
        """)

    problems_html = "".join(f"<li>{escape(item)}</li>" for item in problems)
    body = "".join(sections) or "<p>No flagged completed reviews found.</p>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BirdNET human review</title>
<style>
body {{font-family:Arial,sans-serif;background:#f3f6f5;color:#20332d;
       max-width:1050px;margin:36px auto;padding:0 20px;line-height:1.6}}
section {{margin:28px 0}}
article {{background:white;border:1px solid #d8e2dd;border-radius:12px;
          padding:20px;margin:14px 0}}
h1,h2,h3 {{line-height:1.3}}
a {{color:#146546}}
.small {{color:#52645c;font-size:14px}}
.warning {{color:#875000}}
</style>
</head>
<body>
<h1>BirdNET human review</h1>
<p>{inspected} saved review files inspected · {len(cases)} flagged detections ·
{len(groups)} species/property groups · {unfinished} unfinished reviews</p>
<p>This page summarizes saved AI assessments and reference-list checks.
It does not confirm species presence or change BirdNET verification or the
species register. Reference-list findings reflect the saved review date.</p>
{body}
<h2>Files requiring inspection</h2>
<ul>{problems_html or '<li>None</li>'}</ul>
<p class="small">Generated:
{escape(datetime.now(timezone.utc).isoformat())}</p>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", action="append",
                        help="Repeat to select stations; default is both.")
    args = parser.parse_args()

    cases, problems, inspected, unfinished = collect_reviews(
        args.station or DEFAULT_STATIONS
    )
    output = DATA_DIR / "human_review"
    output.mkdir(parents=True, exist_ok=True)

    json_path = output / "human_review_queue.json"
    html_path = output / "human_review.html"

    json_path.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cases": cases,
            "problems": problems,
            "review_files_inspected": inspected,
            "unfinished_reviews": unfinished,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    html_path.write_text(
        render_page(cases, problems, inspected, unfinished),
        encoding="utf-8",
    )

    print("Review files inspected:", inspected)
    print("Flagged detections:", len(cases))
    print("Unfinished reviews:", unfinished)
    print("Files requiring inspection:", len(problems))
    print("HTML:", html_path)
    print("JSON:", json_path)
    print("Gemini calls: NO")
    print("BirdNET / species register changes: NO")


if __name__ == "__main__":
    main()