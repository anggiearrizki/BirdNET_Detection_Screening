"""Review one prepared station-specific package.

Default: build evidence and save a prompt without calling Gemini.
With --run-gemini: make one generation attempt using an explicit model,
validate the result, and save a review note locally.

No BirdNET write-back or verification changes.
Run sequentially; do not run concurrent reviews for the same detection.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parents[1]

# Existing evidence modules use bare sibling imports.
# Include their source directories without executing any runners.
for directory in (
    SRC_DIR,
    SRC_DIR / "taxonomy",
    SRC_DIR / "local_reference",
    SRC_DIR / "evidence",
    CURRENT_FILE.parent,
):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from birdnet_station_config import get_station_config
from birdnet_queue_worker import get_worker_paths, save_json, utc_now
from ingestion.birdnet_detection_adapter import build_candidate_from_birdnet
from evidence.candidate_evidence_packet import build_candidate_evidence_packet
from ai.gemini_prompt import build_gemini_prompt
from ai.gemini_response import validate_gemini_response
from integration.birdnet_review_note import build_birdnet_review_note


def review_package(station, detection_id, run_gemini=False, model=None):
    config = get_station_config(station)
    paths = get_worker_paths(config["station"])
    package_path = (
        paths["package_dir"] / f"detection_{detection_id}.json"
    )
    output_path = (
        paths["package_dir"] / f"detection_{detection_id}_review.json"
    )

    with package_path.open("r", encoding="utf-8") as file:
        package = json.load(file)

    if (
        package.get("station") != config["station"]
        or package.get("property") != config["property"]
        or int(package["detection_id"]) != detection_id
        or package.get("source_base_url") != config["base_url"]
    ):
        raise ValueError("Package provenance does not match station configuration.")

    detection = package["birdnet_detection"]
    if int(detection["id"]) != detection_id:
        raise ValueError("Metadata ID does not match package ID.")

    audio = package["audio"]
    if int(audio["detection_id"]) != detection_id:
        raise ValueError("Audio ID does not match package ID.")

    audio_path = Path(audio["path"]).resolve()
    if audio_path.parent != paths["audio_dir"].resolve():
        raise ValueError("Audio is outside the selected station directory.")

    audio_bytes = audio_path.read_bytes()
    if not audio_bytes or len(audio_bytes) != int(audio["size_bytes"]):
        raise ValueError("Audio is empty or its size has changed.")
    if hashlib.sha256(audio_bytes).hexdigest() != audio["sha256"]:
        raise ValueError("Audio checksum does not match the prepared package.")

    # Preserve completed results and block ambiguous repeat API attempts.
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as file:
            previous = json.load(file)
        if previous.get("generation_attempt_started_at"):
            print("A generation attempt is already recorded for this detection.")
            print("Existing review:", output_path)
            print("No additional Gemini request made.")
            return

    candidate = build_candidate_from_birdnet(
        detection=detection,
        audio_result=audio,
        island=config["property"],
        environment="terrestrial",
    )
    candidate["source_reference"] = (
        f"{config['base_url']}/api/v2/detections/{detection_id}"
    )

    birdnet_data = candidate["birdnet_data"]
    birdnet_data["station_id"] = config["station"]
    birdnet_data["detection_confidence"] = birdnet_data.get("confidence")
    birdnet_data["detection_datetime"] = birdnet_data.get("datetime")

    packet = build_candidate_evidence_packet(
        scientific_name=candidate["scientific_name"],
        common_name=candidate.get("common_name"),
        island=candidate["island"],
        taxon_group=candidate["taxon_group"],
        environment=candidate["environment"],
        expected_rank=candidate["expected_rank"],
        candidate_source=candidate["candidate_source"],
        source_record_id=candidate["source_record_id"],
        source_reference=candidate["source_reference"],
        birdnet_data=birdnet_data,
    )

    # The existing builder focuses on register additions and skips specialist
    # evidence for registered taxa. Always retain this recording's context.
    packet["detection_context"] = {
        "station": config["station"],
        "property": config["property"],
        "detection_id": detection_id,
        "birdnet_data": birdnet_data,
        "audio_sha256": audio["sha256"],
        "interpretation": (
            "These are current detection metadata, not collected historical "
            "or independent acoustic verification evidence."
        ),
    }

    prompt = build_gemini_prompt(packet)
    result = {
        "schema_version": "1.0",
        "station": config["station"],
        "property": config["property"],
        "detection_id": detection_id,
        "source_base_url": config["base_url"],
        "prepared_package": str(package_path),
        "audio_sha256": audio["sha256"],
        "generated_at": utc_now(),
        "candidate": candidate,
        "evidence_packet": packet,
        "prompt": prompt,
        "status": "evidence_prepared",
        "generation_attempt_started_at": None,
        "gemini_result": None,
        "review_note": None,
        "birdnet_writeback": "not_requested",
    }
    save_json(output_path, result)

    print("Station:", config["station"])
    print("Detection:", detection_id)
    print("Species:", candidate["scientific_name"])
    print("Taxonomy:", packet["taxonomy"]["taxonomy_resolution_status"])
    print("Register check:", packet["register_check"])
    print("Evidence/review file:", output_path)

    if packet["taxonomy"]["taxonomy_resolution_status"] != "resolved":
        result["status"] = "taxonomy_review_required"
        save_json(output_path, result)
        print("Gemini skipped: taxonomy requires review.")
        return

    if packet["register_check"].get("status") != "completed":
        raise ValueError("Register check has not completed.")

    if not run_gemini:
        print("Gemini generation requests: 0")
        print("BirdNET records modified: NO")
        return

    if not model:
        raise ValueError("An explicit --model is required for generation.")

    # Import only when live generation is requested.
    from ai.gemini_client import run_gemini_interpretation

    result["status"] = "generation_attempt_started"
    result["generation_attempt_started_at"] = utc_now()
    result["requested_model"] = model
    save_json(output_path, result)

    try:
        raw_result = run_gemini_interpretation(
            prompt,
            audio_path=str(audio_path),
            audio_mime_type=audio["content_type"].split(";")[0].strip(),
            model_override=model,
            allow_fallback=False,
            max_retries_per_model=1,
        )
        # Save returned output before validation to support error investigation.
        result["raw_gemini_result"] = raw_result
        result["status"] = "generation_response_received"
        save_json(output_path, result)

        validated = validate_gemini_response(raw_result)
        note = build_birdnet_review_note(candidate, validated)

        result["gemini_result"] = validated
        result["review_note"] = note
        result["status"] = "review_note_ready"
        save_json(output_path, result)
    except Exception:
        result["status"] = "generation_or_validation_failed"
        save_json(output_path, result)
        raise

    print("Review note saved:", output_path)
    print()
    print(result["review_note"])
    print()
    print("BirdNET records modified: NO")
    print("Verification statuses changed: NO")


def main():
    parser = argparse.ArgumentParser(
        description="Build evidence and optionally review one prepared package."
    )
    parser.add_argument("--station", required=True)
    parser.add_argument("--detection-id", type=int, required=True)
    parser.add_argument("--run-gemini", action="store_true")
    parser.add_argument("--model")
    args = parser.parse_args()

    if args.detection_id <= 0:
        parser.error("--detection-id must be positive.")
    if args.run_gemini and not args.model:
        parser.error("--run-gemini requires --model.")

    review_package(
        station=args.station,
        detection_id=args.detection_id,
        run_gemini=args.run_gemini,
        model=args.model,
    )


if __name__ == "__main__":
    main()