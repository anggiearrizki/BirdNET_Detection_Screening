"""Automatic BirdNET-Go detection scanner.
Each BirdNET-Go station maintains its own:
- base URL
- high-water mark
- scanner state
- review queue
The scanner is read-only against BirdNET-Go.
It never calls Gemini and never modifies BirdNET records.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
from birdnet_station_config import get_station_config
# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "birdnet"
# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def utc_now():
    """Return an ISO UTC timestamp."""
    return datetime.now(
        timezone.utc
    ).isoformat()
def load_json(path, default):
    """Load JSON from disk or return a default value."""
    if not path.exists():
        return default
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)
from birdnet_queue_worker import save_json
def get_station_paths(station):
    """Return station-specific state and queue paths."""
    station_dir = (
        PROCESSED_DIR
        / station.lower()
    )
    return {
        "station_dir": station_dir,
        "state_file":
            station_dir
            / "scanner_state.json",
        "queue_file":
            station_dir
            / "review_queue.json",
    }
# ---------------------------------------------------------------------
# BirdNET retrieval
# ---------------------------------------------------------------------
def get_recent_detections(base_url, limit=200, offset=0):
    response = requests.get(
        f"{base_url}/api/v2/detections",
        params={"limit": limit, "offset": offset, "sortBy": "date_desc"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("Unexpected BirdNET list response; state unchanged.")
    rows = payload["data"]
    for row in rows:
        if not isinstance(row, dict) or int(row.get("id", 0)) <= 0:
            raise ValueError("Invalid detection ID; state unchanged.")
    return rows


def retrieve_complete_listing(base_url, limit, max_pages):
    # Date order does not prove ID order. Traverse the complete listing rather
    # than stopping as soon as one old ID appears.
    first = get_recent_detections(base_url, limit, 0)
    rows = {}; offset = 0; page = first
    signatures = set()
    for page_number in range(max_pages):
        if not page:
            break
        signature = tuple(int(row["id"]) for row in page)
        if signature in signatures:
            raise RuntimeError("BirdNET repeated a page; state unchanged.")
        signatures.add(signature)
        rows.update((int(row["id"]), row) for row in page)
        offset += len(page)
        page = get_recent_detections(base_url, limit, offset)
    else:
        raise RuntimeError("Page limit reached; state unchanged. Increase --max-pages.")
    check = get_recent_detections(base_url, limit, 0)
    if [r["id"] for r in check] != [r["id"] for r in first]:
        raise RuntimeError("Listing changed during scan; retry later. State unchanged.")
    return list(rows.values()), len(signatures)

def build_queue_record(
    detection,
    property_name,
    station,
):
    """Convert a BirdNET detection into a local queue record."""
    return {
        "detection_id":
            detection.get(
                "id"
            ),
        "common_name":
            detection.get(
                "commonName"
            ),
        "scientific_name":
            detection.get(
                "scientificName"
            ),
        "confidence":
            detection.get(
                "confidence"
            ),
        "verified":
            detection.get(
                "verified"
            ),
        "date":
            detection.get(
                "date"
            ),
        "time":
            detection.get(
                "time"
            ),
        "timestamp":
            detection.get(
                "timestamp"
            ),
        "clip_name":
            detection.get(
                "clipName"
            ),
        "days_since_first_seen":
            detection.get(
                "daysSinceFirstSeen"
            ),
        "is_new_this_season":
            detection.get(
                "isNewThisSeason"
            ),
        "days_this_year":
            detection.get(
                "daysThisYear"
            ),
        "current_season":
            detection.get(
                "currentSeason"
            ),
        # Keep "island" temporarily for compatibility
        # with the existing queue worker.
        "island":
            property_name,
        "property":
            property_name,
        "station":
            station,
        "source":
            "BirdNET-Go",
        "queue_status":
            "pending",
        "discovered_by_scanner_at":
            utc_now(),
        "processed_at":
            None,
        "processing_note":
            None,
    }
# ---------------------------------------------------------------------
# State and queue
# ---------------------------------------------------------------------
def load_state(state_file):
    """Load station-specific scanner state."""
    return load_json(
        state_file,
        {
            "highest_seen_detection_id": None,
            "last_scan_at": None,
        },
    )
def load_queue(queue_file):
    """Load station-specific review queue."""
    return load_json(
        queue_file,
        {
            "detections": [],
            "updated_at": None,
        },
    )
# ---------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------
def scan_detections(station, limit=200, bootstrap=False, max_pages=1000,
                    since_id=None, recorded_since=None):
    if limit <= 0 or max_pages <= 0:
        raise ValueError("Page size and page limit must be positive.")
    config = get_station_config(station)
    station = config["station"]
    paths = get_station_paths(station)
    state = load_state(paths["state_file"])
    queue = load_queue(paths["queue_file"])
    from birdnet_queue_worker import validate_queue
    validate_queue(queue, config)
    for key in ("station", "property"):
        if state.get(key) is not None and state[key] != config[key]:
            raise ValueError("Scanner state belongs to another station.")
    if state.get("source_base_url") not in (None, config["base_url"]):
        raise ValueError("Scanner state URL does not match station.")
    old = state.get("highest_seen_detection_id")
    if old is None and not bootstrap:
        raise RuntimeError("No baseline. Use --bootstrap explicitly for a new station.")
    if bootstrap and old is not None:
        raise RuntimeError("Station already initialized; bootstrap would skip work.")
    if since_id is not None and (since_id < 0 or bootstrap):
        raise ValueError("--since-id must be nonnegative and cannot accompany bootstrap.")
    if bootstrap:
        detections = get_recent_detections(config["base_url"], limit)
        pages = 1
    else:
        detections, pages = retrieve_complete_listing(config["base_url"], limit, max_pages)
    floor = since_id if since_id is not None else int(old or 0)
    maximum = max([int(old or 0)] + [int(d["id"]) for d in detections])
    new = [] if bootstrap else [d for d in detections if int(d["id"]) > floor]
    candidates = new
    if recorded_since is not None:
        if bootstrap:
            raise ValueError("A recent window cannot accompany bootstrap.")
        from birdnet_recent_window import recording_time
        # Backfill recent recordings even if an earlier baseline passed them.
        candidates = [d for d in detections if recording_time(d) >= recorded_since]
    queued = {int(i["detection_id"]) for i in queue["detections"]}
    added = []
    for d in sorted(candidates, key=lambda r: int(r["id"])):
        if str(d.get("verified", "")).lower() != "unverified" or int(d["id"]) in queued:
            continue
        record = build_queue_record(d, config["property"], station)
        record["source_base_url"] = config["base_url"]
        queue["detections"].append(record)
        queued.add(int(d["id"]))
        added.append(record)
    queue["updated_at"] = utc_now()
    # Queue first: interruption after this save can only cause a deduplicated
    # rescan, never a watermark advancing past unsaved queue entries.
    save_json(paths["queue_file"], queue)
    state.update(highest_seen_detection_id=maximum, last_scan_at=utc_now(),
                 station=station, property=config["property"],
                 source_base_url=config["base_url"])
    if not bootstrap:
        from birdnet_review_policy import build_history
        history = build_history(detections, config)
        history["generated_at"] = utc_now()
        save_json(paths["station_dir"] / "species_history.json", history)
    save_json(paths["state_file"], state)
    return dict(property=config["property"], station=station,
                base_url=config["base_url"], retrieved=len(detections),
                newly_seen=len(new), newly_queued=added,
                total_queue=len(queue["detections"]), bootstrap=bootstrap,
                highest_seen_detection_id=maximum, pages=pages)

def print_scan_summary(
    result,
):
    """Print scanner results."""
    print("=" * 72)
    print("BIRDNET-GO AUTOMATIC DETECTION SCANNER")
    print("=" * 72)
    print(
        "Property:",
        result[
            "property"
        ],
    )
    print(
        "Station:",
        result[
            "station"
        ],
    )
    print(
        "BirdNET instance:",
        result[
            "base_url"
        ],
    )
    print(
        "Mode:",
        (
            "BOOTSTRAP"
            if result[
                "bootstrap"
            ]
            else "NORMAL"
        ),
    )
    print(
        "Detections inspected across pages:",
        result[
            "retrieved"
        ],
    )
    print(
        "Highest detection ID seen:",
        result[
            "highest_seen_detection_id"
        ],
    )
    print(
        "Genuinely new detections:",
        result[
            "newly_seen"
        ],
    )
    print(
        "New detections added to queue:",
        len(
            result[
                "newly_queued"
            ]
        ),
    )
    print(
        "Total detections in review queue:",
        result[
            "total_queue"
        ],
    )
    if result[
        "newly_queued"
    ]:
        print()
        print("NEW REVIEW QUEUE ITEMS")
        print("-" * 72)
        for item in result[
            "newly_queued"
        ]:
            print(
                f"ID {item['detection_id']} | "
                f"{item['common_name']} | "
                f"{item['confidence']} | "
                f"{item['station']}"
            )
    print()
    print(
        "BirdNET-Go records modified: NO"
    )
    print(
        "Gemini calls made: NO"
    )
    print("=" * 72)
# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def parse_args():
    """Parse scanner CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan one BirdNET-Go station "
            "for genuinely new detections."
        )
    )
    parser.add_argument(
        "--station",
        required=True,
        help=(
            "BirdNET station key, for example "
            "CEMPEDAK_01 or CEMPEDAK_02."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help=(
            "Number of recent detections "
            "to inspect. Default: 200."
        ),
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help=(
            "Set the station's current highest "
            "detection ID as its baseline."
        ),
    )
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--since-id", type=int, help="One-time recovery: queue unverified IDs above this ID, deduplicated.")
    return parser.parse_args()
def main():
    """Run the station-aware scanner."""
    args = parse_args()
    result = scan_detections(
        station=args.station,
        limit=args.limit,
        bootstrap=args.bootstrap,
        max_pages=args.max_pages,
        since_id=args.since_id,
    )
    print_scan_summary(
        result
    )
if __name__ == "__main__":
    main()
