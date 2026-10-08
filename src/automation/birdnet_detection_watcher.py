"""Scan, prepare, review, and optionally post BirdNET notes.
Run only one watcher per station. Do not run separate scanner,
worker, review, or posting commands against that station concurrently.
Gemini reviews are bounded by --max-reviews for the entire run.
Existing generation attempts and write records are never repeated.
Verification and lock status are not sent by the posting script.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from birdnet_recent_window import recent_ids
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_DIR = Path(__file__).resolve().parent
# Refresh credentials before importing station configuration.
load_dotenv(PROJECT_ROOT / ".env", override=True)
import requests
from birdnet_station_config import get_station_config
from birdnet_detection_scanner import scan_detections, print_scan_summary
from birdnet_queue_worker import (
    get_worker_paths,
    process_queue,
    save_json, utc_now,
    print_summary as print_worker_summary,
)
def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be positive.")
    return number
def read_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
def run_stage(script_name, station, detection_id, extra_args=()):
    """Run a stage in a fresh process using this virtual environment."""
    command = [
        sys.executable,
        str(AUTOMATION_DIR / script_name),
        "--station", station,
        "--detection-id", str(detection_id),
        *extra_args,
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{script_name} failed for detection {detection_id}. "
            "Watcher stopped; saved results and attempt records are preserved."
        )
def next_review_item(station, selected_ids=None):
    """Find prepared work without repeating recorded attempts."""
    config = get_station_config(station)
    package_dir = Path(get_worker_paths(station)["package_dir"])
    packages = []
    for path in package_dir.glob("detection_*.json"):
        suffix = path.stem.removeprefix("detection_")
        if suffix.isdigit():
            packages.append((int(suffix), path))
    order = None if selected_ids is None else {value: index for index, value in enumerate(selected_ids)}
    if order is not None:
        packages = [item for item in packages if item[0] in order]
    for detection_id, package_path in sorted(packages, key=lambda item: item[0] if order is None else order[item[0]]):
        write_path = (
            package_dir / f"detection_{detection_id}_writeback.json"
        )
        review_path = (
            package_dir / f"detection_{detection_id}_review.json"
        )
        if write_path.exists():
            record = read_json(write_path)
            for field, value in {"station": config["station"], "property": config["property"],
                                 "source_base_url": config["base_url"], "detection_id": detection_id}.items():
                if record.get(field) != value:
                    raise ValueError(f"Write record mismatch: {field}")
            if record.get("status") not in {"post_accepted_status_unchanged", "authentication_rejected", "post_accepted", "post_accepted_readback_failed"}:
                raise RuntimeError(
                    f"Detection {detection_id} has an unresolved write record: "
                    f"{record.get('status')}. Check it before continuing."
                )
            if record.get("status") == "post_accepted_status_unchanged":
                continue
        package = read_json(package_path)
        expected = {
            "station": config["station"],
            "property": config["property"],
            "source_base_url": config["base_url"],
            "detection_id": detection_id,
        }
        for field, value in expected.items():
            if package.get(field) != value:
                raise ValueError(
                    f"Detection {detection_id}: package mismatch in {field}."
                )
        if package.get("pipeline_status") != "ready_for_ai":
            continue
        if review_path.exists():
            review = read_json(review_path)
            for field, value in expected.items():
                if review.get(field) != value:
                    raise ValueError(
                        f"Detection {detection_id}: review mismatch in {field}."
                    )
            if review.get("status") == "review_note_ready":
                return detection_id, "saved_note"
            if review.get("generation_attempt_started_at"):
                print(
                    f"Skipping {detection_id}: a Gemini attempt is "
                    "already recorded and requires manual inspection."
                )
                continue
            if review.get("status") in {"taxonomy_review_required", "screening_skipped_known_species", "eligibility_review_required"}:
                continue
        return detection_id, "needs_review"
    return None
def sync_completion(station):
    config = get_station_config(station)
    paths = get_worker_paths(config["station"])
    if not paths["queue_file"].exists():
        return
    queue = read_json(paths["queue_file"])
    changed = False
    for item in queue["detections"]:
        record_path = paths["package_dir"] / f"detection_{int(item['detection_id'])}_writeback.json"
        if not record_path.exists():
            continue
        record = read_json(record_path)
        if (record.get("station") != config["station"]
                or record.get("property") != config["property"]
                or record.get("source_base_url") != config["base_url"]
                or record.get("detection_id") != int(item["detection_id"])):
            raise ValueError("Write record provenance mismatch.")
        if record.get("status") == "post_accepted_status_unchanged" and item.get("queue_status") != "completed":
            item.update(queue_status="completed", completed_at=record.get("finished_at"))
            changed = True
    if changed:
        queue["updated_at"] = utc_now()
        save_json(paths["queue_file"], queue)

def watch(args):
    config = get_station_config(args.station)
    station = config["station"]
    cycle = 0
    items_handled = 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.recent_days)
              if args.recent_days else None)
    print("=" * 72)
    print("BIRDNET AUTOMATED SCREENING WATCHER")
    print("=" * 72)
    print("Station:", station)
    print("Property:", config["property"])
    print("BirdNET:", config["base_url"])
    print("Recording window starts:", cutoff.isoformat() if cutoff else "All queued recordings")
    print("Gemini enabled:", args.run_gemini)
    print("Note posting enabled:", args.post_notes)
    print("Maximum review items for this entire run:", args.max_reviews)
    print("Maximum review items per cycle:", args.reviews_per_cycle)
    print("Model:", args.model if args.run_gemini else "Not used")
    print()
    try:
        while args.max_cycles is None or cycle < args.max_cycles:
            cycle += 1
            print(f"\nWATCH CYCLE {cycle}")
            try:
                result = scan_detections(
                    station=station,
                    limit=args.limit,
                    bootstrap=False,
                    max_pages=args.max_pages,
                    recorded_since=cutoff,
                )
                print_scan_summary(result)
            except requests.RequestException as exc:
                print("Scan connection failed:", type(exc).__name__)
                print("Existing queued work will still be processed.")
            sync_completion(station)
            selected_ids = None
            if cutoff is not None:
                queue_path = get_worker_paths(station)["queue_file"]
                selected_ids = recent_ids(read_json(queue_path)["detections"], cutoff)
                print("Recent queued recordings:", len(selected_ids))
            # Detect blocked posting records before downloading more audio.
            if args.run_gemini:
                next_review_item(station, selected_ids)
            worker_result = process_queue(
                station=station,
                max_items=args.max_items,
                max_attempts=args.max_attempts,
                detection_ids=selected_ids,
            )
            print_worker_summary(worker_result)
            if args.run_gemini:
                for _ in range(args.reviews_per_cycle):
                    if items_handled >= args.max_reviews:
                        break
                    selected = next_review_item(station, selected_ids)
                    if selected is None:
                        print("No eligible review items.")
                        break
                    detection_id, stage = selected
                    print(f"\nSCREENING DETECTION {detection_id}")
                    if stage == "needs_review":
                        run_stage(
                            "birdnet_package_review.py",
                            station,
                            detection_id,
                            ("--run-gemini", "--model", args.model),
                        )
                    else:
                        print("Using saved Gemini review; no new Gemini call.")
                    review_path = (
                        Path(get_worker_paths(station)["package_dir"])
                        / f"detection_{detection_id}_review.json"
                    )
                    review = read_json(review_path)
                    if review.get("status") != "review_note_ready":
                        print("No note to post:", review.get("status"))
                        continue
                    if (
                        args.post_notes
                        and review.get("status") == "review_note_ready"
                    ):
                        run_stage(
                            "birdnet_post_review_note.py",
                            station,
                            detection_id,
                            ("--station-credentials",) if args.station_credentials else (),
                        )
                        write_path = (
                            review_path.parent
                            / f"detection_{detection_id}_writeback.json"
                        )
                        record = read_json(write_path)
                        if record.get("status") != (
                            "post_accepted_status_unchanged"
                        ):
                            raise RuntimeError(
                                f"Detection {detection_id}: write-back "
                                "requires inspection."
                            )
                    sync_completion(station)
                    items_handled += 1
                    # Without posting, leave saved notes available for a
                    # later posting run, rather than selecting them again.
                    if not args.post_notes:
                        break
                if items_handled >= args.max_reviews:
                    print("\nTotal review-item limit reached. Watcher stopped.")
                    break
                if not args.post_notes and items_handled:
                    print("\nReview saved locally. Watcher stopped.")
                    break
            if args.max_cycles is not None and cycle >= args.max_cycles:
                break
            print(f"\nWaiting {args.interval} seconds...")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        print("\nCycles started:", cycle)
        print("Review items handled:", items_handled)
        print("Local queue, packages, and attempt records preserved.")
def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan, prepare, review, and optionally post BirdNET notes."
    )
    parser.add_argument("--station", required=True)
    parser.add_argument("--recent-days", type=positive_int, help="Backfill and process recordings from the last N days, newest first; preserve older work.")
    parser.add_argument("--max-pages", type=positive_int, default=1000)
    parser.add_argument("--station-credentials", action="store_true")
    parser.add_argument("--limit", type=positive_int, default=200)
    parser.add_argument("--interval", type=positive_int, default=60)
    parser.add_argument("--max-cycles", type=positive_int)
    parser.add_argument("--max-items", type=positive_int, default=5)
    parser.add_argument("--max-attempts", type=positive_int, default=3)
    parser.add_argument("--run-gemini", action="store_true")
    parser.add_argument("--post-notes", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--max-reviews", type=positive_int, default=1)
    parser.add_argument("--reviews-per-cycle", type=positive_int, default=1)
    args = parser.parse_args()
    if args.run_gemini and not args.model:
        parser.error("--run-gemini requires --model.")
    if args.post_notes and not args.run_gemini:
        parser.error("--post-notes requires --run-gemini.")
    return args
if __name__ == "__main__":
    try:
        watch(parse_args())
    except Exception as exc:
        print(f"\nSTOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
