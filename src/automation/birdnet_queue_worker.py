"""Prepare station-specific BirdNET detections for later AI review.
Retrieves metadata and real audio, then saves a local preparation package.
No Gemini calls, BirdNET write-back, or verification changes.
Run sequentially with the scanner. Concurrent queue writers are not supported.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parents[1]
PROJECT_ROOT = CURRENT_FILE.parents[2]
for directory in (SRC_DIR, CURRENT_FILE.parent):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
from birdnet_station_config import get_station_config
from integration.birdnet_client import get_detection, save_detection_audio
def utc_now():
    return datetime.now(timezone.utc).isoformat()
def get_worker_paths(station):
    station_dir = (
        PROJECT_ROOT / "data" / "processed" / "birdnet" / station.lower()
    )
    return {
        "queue_file": station_dir / "review_queue.json",
        "package_dir": station_dir / "review_packages",
        "audio_dir": (
            PROJECT_ROOT / "data" / "raw" / "birdnet_audio"
            / station.lower()
        ),
    }
def load_queue(path):
    # A missing queue should not masquerade as an empty initialized queue.
    if not path.exists():
        raise RuntimeError(
            f"Station queue does not exist: {path}. "
            "Check the station scanner baseline first."
        )
    with path.open("r", encoding="utf-8") as file:
        queue = json.load(file)
    if not isinstance(queue, dict):
        raise ValueError("Queue must be a JSON object.")
    items = queue.get("detections")
    if not isinstance(items, list):
        raise ValueError("Queue detections must be a list.")
    return queue
def save_json(path, data):
    """Atomically replace JSON using a unique temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
def validate_queue(queue, config):
    """Reject mixed-station or malformed queues before making requests."""
    seen_ids = set()
    for item in queue["detections"]:
        if not isinstance(item, dict):
            raise ValueError("Each queue item must be a JSON object.")
        if item.get("station") != config["station"]:
            raise ValueError(
                "Queue item station does not match the selected station."
            )
        if item.get("property") != config["property"]:
            raise ValueError(
                "Queue item property does not match station configuration."
            )
        detection_id = int(item["detection_id"])
        if detection_id <= 0 or detection_id in seen_ids:
            raise ValueError("Queue contains an invalid or duplicate ID.")
        seen_ids.add(detection_id)
        attempts = int(item.get("preparation_attempts", 0))
        if attempts < 0:
            raise ValueError("Preparation attempts cannot be negative.")
def validate_audio(audio, detection_id, audio_dir):
    """Check local bytes and basic format without claiming playability."""
    if int(audio["detection_id"]) != detection_id:
        raise ValueError("Audio detection ID does not match requested ID.")
    path = Path(audio["path"]).resolve()
    if path.parent != audio_dir.resolve():
        raise ValueError("Audio was saved outside the selected station folder.")
    data = path.read_bytes()
    if not data or len(data) != int(audio["size_bytes"]):
        raise ValueError("Audio is empty or its byte count is inconsistent.")
    content_type = str(audio["content_type"]).split(";")[0].strip().lower()
    header = data[:512].lstrip().lower()
    if header.startswith((b"<!doctype html", b"<html", b"{", b"[")):
        raise ValueError("Downloaded content appears to be HTML or JSON.")
    known_signature = (
        (
            len(data) >= 12
            and data[:4] in (b"RIFF", b"RF64")
            and data[8:12] == b"WAVE"
        )
        or data.startswith((b"fLaC", b"OggS", b"ID3"))
        or (
            len(data) >= 2
            and data[0] == 0xFF
            and data[1] & 0xE0 == 0xE0
        )
        or (len(data) >= 12 and data[4:8] == b"ftyp")
    )
    if not content_type.startswith("audio/") and not known_signature:
        raise ValueError("Downloaded content cannot be identified as audio.")
    return {
        **audio,
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "validation": "nonempty_audio_content_checked",
        "playability_verified": False,
    }
def prepare_detection(queue_item, config, paths):
    detection_id = int(queue_item["detection_id"])
    base_url = config["base_url"]
    detection = get_detection(detection_id, base_url=base_url)
    if detection.get("id") is None:
        raise ValueError("Detection metadata has no ID.")
    if int(detection["id"]) != detection_id:
        raise ValueError("Metadata ID does not match requested detection ID.")
    package_path = paths["package_dir"] / f"detection_{detection_id}.json"
    if package_path.exists():
        existing = json.loads(package_path.read_text(encoding="utf-8"))
        expected = dict(station=config["station"], property=config["property"],
                        source_base_url=base_url, detection_id=detection_id)
        for key, value in expected.items():
            if existing.get(key) != value:
                raise ValueError(f"Existing package mismatch: {key}")
        audio = validate_audio(existing["audio"], detection_id, paths["audio_dir"])
        if audio["sha256"] != existing["audio"]["sha256"]:
            raise ValueError("Existing audio checksum changed.")
        if existing.get("pipeline_status") != "ready_for_ai":
            raise ValueError("Existing package is not ready.")
        return dict(detection_id=detection_id, package_path=str(package_path),
                    audio_path=audio["path"], audio_content_type=audio["content_type"],
                    audio_size_bytes=audio["size_bytes"])
    audio = save_detection_audio(
        detection_id,
        output_dir=paths["audio_dir"],
        base_url=base_url,
    )
    audio = validate_audio(audio, detection_id, paths["audio_dir"])
    package = {
        "schema_version": "1.1",
        "package_type": "birdnet_detection_review",
        "detection_id": detection_id,
        "station": config["station"],
        "property": config["property"],
        "source": "BirdNET-Go",
        "source_base_url": base_url,
        "record_key": f"{config['station']}:{detection_id}",
        "prepared_at": utc_now(),
        "pipeline_status": "ready_for_ai",
        "preparation_scope": "metadata_and_audio_only",
        "queue_context": {
            "discovered_by_scanner_at": queue_item.get(
                "discovered_by_scanner_at"
            ),
            "queue_status_before_preparation": queue_item.get("queue_status"),
        },
        "birdnet_detection": detection,
        "audio": audio,
        "evidence_construction": {"status": "not_started"},
        "ai_review": {
            "status": "not_started",
            "model": None,
            "result": None,
        },
        "birdnet_writeback": {
            "status": "not_requested",
            "note_written": False,
            "verification_changed": False,
        },
    }
    package_path = (
        paths["package_dir"] / f"detection_{detection_id}.json"
    )
    save_json(package_path, package)
    return {
        "detection_id": detection_id,
        "package_path": str(package_path),
        "audio_path": audio["path"],
        "audio_content_type": audio["content_type"],
        "audio_size_bytes": audio["size_bytes"],
    }
def process_queue(
    station,
    max_items=None,
    detection_ids=None,
    max_attempts=3,
):
    """Prepare pending items and retry failures within the attempt limit."""
    if max_items is not None and max_items <= 0:
        raise ValueError("max_items must be positive.")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive.")
    config = get_station_config(station)
    paths = get_worker_paths(config["station"])
    queue = load_queue(paths["queue_file"])
    validate_queue(queue, config)
    target_ids = (
        {int(value) for value in detection_ids}
        if detection_ids is not None else None
    )
    selected = []
    exhausted = 0
    for item in queue["detections"]:
        if item.get("queue_status") not in ("pending", "preparation_failed"):
            continue
        if int(item.get("preparation_attempts", 0)) >= max_attempts:
            exhausted += 1
            continue
        if target_ids is not None:
            if int(item["detection_id"]) not in target_ids:
                continue
        selected.append(item)
    if detection_ids is not None:
        order = {int(value): index for index, value in enumerate(detection_ids)}
        selected.sort(key=lambda item: order[int(item["detection_id"])])
    if max_items is not None:
        selected = selected[:max_items]
    prepared = []
    failed = []
    for item in selected:
        detection_id = int(item["detection_id"])
        # Persist the attempt before network work. An interrupted preparation
        # stays eligible on restart, subject to the attempt limit.
        item["preparation_attempts"] = (
            int(item.get("preparation_attempts", 0)) + 1
        )
        item["last_preparation_attempt_at"] = utc_now()
        queue["updated_at"] = utc_now()
        save_json(paths["queue_file"], queue)
        print(f"Preparing {config['station']} detection {detection_id}...")
        try:
            result = prepare_detection(item, config, paths)
        except Exception as exc:
            item["queue_status"] = "preparation_failed"
            item["processed_at"] = utc_now()
            item["processing_note"] = str(exc)
            item["last_preparation_error"] = str(exc)
            failed.append({
                "detection_id": detection_id,
                "error": str(exc),
            })
            print(f"Detection {detection_id}: FAILED: {exc}")
        else:
            item["queue_status"] = "ready_for_ai"
            item["processed_at"] = utc_now()
            item["processing_note"] = (
                "Metadata and audio prepared. Evidence construction "
                "and AI review have not started."
            )
            item["last_preparation_error"] = None
            item["review_package_path"] = result["package_path"]
            item["audio_path"] = result["audio_path"]
            prepared.append(result)
            print(f"Detection {detection_id}: READY FOR AI")
        # Keep persistence errors visible: do not treat them as network failures.
        queue["updated_at"] = utc_now()
        save_json(paths["queue_file"], queue)
    return {
        "station": config["station"],
        "property": config["property"],
        "base_url": config["base_url"],
        "queue_file": str(paths["queue_file"]),
        "pending_found": len(selected),
        "prepared": prepared,
        "failed": failed,
        "attempt_limit_reached": exhausted,
        "total_queue": len(queue["detections"]),
    }
def print_summary(result):
    print()
    print("=" * 72)
    print("BIRDNET-GO STATION-SPECIFIC PRE-GEMINI QUEUE WORKER")
    print("=" * 72)
    print("Property:", result["property"])
    print("Station:", result["station"])
    print("BirdNET instance:", result["base_url"])
    print("Queue:", result["queue_file"])
    print("Pending/retry items selected:", result["pending_found"])
    print("Prepared successfully:", len(result["prepared"]))
    print("Preparation failures:", len(result["failed"]))
    print("Items at attempt limit:", result["attempt_limit_reached"])
    print("Total detections in queue:", result["total_queue"])
    for item in result["prepared"]:
        print()
        print("Detection ID:", item["detection_id"])
        print("Audio:", item["audio_path"])
        print("Audio size:", item["audio_size_bytes"], "bytes")
        print("Review package:", item["package_path"])
    print()
    print("Gemini calls made: NO")
    print("BirdNET-Go records modified: NO")
    print("Verification statuses changed: NO")
    print("=" * 72)
def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be positive.")
    return number
def main():
    parser = argparse.ArgumentParser(
        description="Prepare one station's queued metadata and audio."
    )
    parser.add_argument("--station", required=True)
    parser.add_argument("--max-items", type=positive_int, default=None)
    parser.add_argument(
        "--max-attempts",
        type=positive_int,
        default=3,
        help="Total preparation attempts per item. Default: 3.",
    )
    args = parser.parse_args()
    result = process_queue(
        station=args.station,
        max_items=args.max_items,
        max_attempts=args.max_attempts,
    )
    print_summary(result)
if __name__ == "__main__":
    main()
