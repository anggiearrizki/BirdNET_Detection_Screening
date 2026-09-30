"""Automatic BirdNET-Go detection scanner.

This module is intentionally read-only.

It:
- scans recent BirdNET-Go detections
- tracks the highest BirdNET detection ID seen
- identifies genuinely newer detections
- adds new unverified detections to a local review queue
- never changes BirdNET-Go data
- never calls Gemini

Later, the pending queue can feed the automated review pipeline.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

STATE_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

STATE_FILE = (
    STATE_DIR
    / "birdnet_scanner_state.json"
)

QUEUE_FILE = (
    STATE_DIR
    / "birdnet_review_queue.json"
)


# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

load_dotenv()

BIRDNET_BASE_URL = os.getenv(
    "BIRDNET_BASE_URL",
    "",
).rstrip("/")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def utc_now():
    """Return an ISO UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def load_json(
    path,
    default,
):
    """Load JSON from disk or return a default value."""

    if not path.exists():
        return default

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def save_json(
    path,
    data,
):
    """Write JSON safely to disk."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------
# BirdNET retrieval
# ---------------------------------------------------------------------

def get_recent_detections(
    limit=100,
):
    """Retrieve recent BirdNET-Go detections."""

    if not BIRDNET_BASE_URL:
        raise RuntimeError(
            "BIRDNET_BASE_URL is not configured."
        )

    url = (
        f"{BIRDNET_BASE_URL}"
        "/api/v2/detections"
    )

    response = requests.get(
        url,
        params={
            "limit": limit,
            "offset": 0,
            "sortBy": "date_desc",
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    detections = payload.get(
        "data",
        [],
    )

    if not isinstance(
        detections,
        list,
    ):
        raise RuntimeError(
            "Unexpected BirdNET-Go response format."
        )

    return detections


# ---------------------------------------------------------------------
# Queue conversion
# ---------------------------------------------------------------------

def build_queue_record(
    detection,
    island,
):
    """Convert a BirdNET detection into a queue record."""

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

        "island":
            island,

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
# Scanner state
# ---------------------------------------------------------------------

def load_state():
    """Load scanner state and migrate older state if necessary."""

    state = load_json(
        STATE_FILE,
        {
            "highest_seen_detection_id": None,
            "last_scan_at": None,
        },
    )

    # Migration from the earlier seen_detection_ids approach.
    if (
        state.get(
            "highest_seen_detection_id"
        )
        is None
    ):

        old_seen_ids = state.get(
            "seen_detection_ids",
            [],
        )

        if old_seen_ids:
            state[
                "highest_seen_detection_id"
            ] = max(
                int(detection_id)
                for detection_id
                in old_seen_ids
            )

    # Remove the old state field.
    state.pop(
        "seen_detection_ids",
        None,
    )

    return state


def load_queue():
    """Load the local BirdNET review queue."""

    return load_json(
        QUEUE_FILE,
        {
            "detections": [],
            "updated_at": None,
        },
    )


# ---------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------

def scan_detections(
    island,
    limit=100,
    bootstrap=False,
):
    """Scan BirdNET-Go and update the local queue."""

    state = load_state()
    queue = load_queue()

    highest_seen_id = state.get(
        "highest_seen_detection_id"
    )

    if highest_seen_id is not None:
        highest_seen_id = int(
            highest_seen_id
        )

    queued_ids = {
        int(item["detection_id"])
        for item in queue.get(
            "detections",
            [],
        )
        if item.get(
            "detection_id"
        ) is not None
    }

    detections = get_recent_detections(
        limit=limit
    )

    valid_detections = [
        detection
        for detection in detections
        if detection.get(
            "id"
        ) is not None
    ]

    if not valid_detections:
        return {
            "retrieved": 0,
            "newly_seen": 0,
            "newly_queued": [],
            "total_queue": len(
                queue["detections"]
            ),
            "bootstrap": bootstrap,
            "highest_seen_detection_id":
                highest_seen_id,
        }

    detection_ids = [
        int(
            detection["id"]
        )
        for detection
        in valid_detections
    ]

    current_max_id = max(
        detection_ids
    )

    # -------------------------------------------------------------
    # Bootstrap
    # -------------------------------------------------------------

    if bootstrap:

        state[
            "highest_seen_detection_id"
        ] = current_max_id

        state[
            "last_scan_at"
        ] = utc_now()

        save_json(
            STATE_FILE,
            state,
        )

        save_json(
            QUEUE_FILE,
            queue,
        )

        return {
            "retrieved":
                len(
                    valid_detections
                ),

            "newly_seen": 0,

            "newly_queued": [],

            "total_queue":
                len(
                    queue[
                        "detections"
                    ]
                ),

            "bootstrap": True,

            "highest_seen_detection_id":
                current_max_id,
        }

    # -------------------------------------------------------------
    # First run protection
    # -------------------------------------------------------------

    if highest_seen_id is None:

        state[
            "highest_seen_detection_id"
        ] = current_max_id

        state[
            "last_scan_at"
        ] = utc_now()

        save_json(
            STATE_FILE,
            state,
        )

        save_json(
            QUEUE_FILE,
            queue,
        )

        return {
            "retrieved":
                len(
                    valid_detections
                ),

            "newly_seen": 0,

            "newly_queued": [],

            "total_queue":
                len(
                    queue[
                        "detections"
                    ]
                ),

            "bootstrap": False,

            "highest_seen_detection_id":
                current_max_id,
        }

    # -------------------------------------------------------------
    # Genuine new detections
    # -------------------------------------------------------------

    new_detections = [
        detection
        for detection
        in valid_detections
        if int(
            detection["id"]
        ) > highest_seen_id
    ]

    newly_queued = []

    # Process new records oldest first.
    new_detections.sort(
        key=lambda detection:
            int(
                detection["id"]
            )
    )

    for detection in new_detections:

        detection_id = int(
            detection["id"]
        )

        verified = str(
            detection.get(
                "verified",
                "",
            )
        ).strip().lower()

        # Only unverified detections enter review queue.
        if verified != "unverified":
            continue

        if detection_id in queued_ids:
            continue

        record = build_queue_record(
            detection=detection,
            island=island,
        )

        queue[
            "detections"
        ].append(
            record
        )

        queued_ids.add(
            detection_id
        )

        newly_queued.append(
            record
        )

    # Advance high-water mark regardless of verification status.
    if current_max_id > highest_seen_id:

        state[
            "highest_seen_detection_id"
        ] = current_max_id

    state[
        "last_scan_at"
    ] = utc_now()

    queue[
        "updated_at"
    ] = utc_now()

    save_json(
        STATE_FILE,
        state,
    )

    save_json(
        QUEUE_FILE,
        queue,
    )

    return {
        "retrieved":
            len(
                valid_detections
            ),

        "newly_seen":
            len(
                new_detections
            ),

        "newly_queued":
            newly_queued,

        "total_queue":
            len(
                queue[
                    "detections"
                ]
            ),

        "bootstrap": False,

        "highest_seen_detection_id":
            state[
                "highest_seen_detection_id"
            ],
    }


# ---------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------

def print_scan_summary(
    result,
):
    """Print the scanner result."""

    print("=" * 72)
    print("BIRDNET-GO AUTOMATIC DETECTION SCANNER")
    print("=" * 72)

    print(
        "BirdNET instance:",
        BIRDNET_BASE_URL,
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
        "Recent detections retrieved:",
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
                f"{item['island']}"
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
    """Parse scanner command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Scan BirdNET-Go for genuinely new "
            "unverified detections."
        )
    )

    parser.add_argument(
        "--island",
        required=True,
        help=(
            "Property/island associated with "
            "this BirdNET-Go deployment."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=(
            "Number of recent BirdNET-Go detections "
            "to inspect. Default: 100."
        ),
    )

    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help=(
            "Set the current highest detection ID "
            "as the starting baseline."
        ),
    )

    return parser.parse_args()


def main():
    """Run the BirdNET-Go automatic scanner."""

    args = parse_args()

    result = scan_detections(
        island=args.island,
        limit=args.limit,
        bootstrap=args.bootstrap,
    )

    print_scan_summary(
        result
    )


if __name__ == "__main__":
    main()
