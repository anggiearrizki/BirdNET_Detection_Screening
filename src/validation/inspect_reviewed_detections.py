"""Inspect previously human-reviewed BirdNET-Go detections.

This script is intentionally read-only.

It retrieves BirdNET-Go detections in pages and filters the returned
records locally by their verification status.

This avoids depending on server-side `verified` filtering, which may
not be supported by the deployed BirdNET-Go version.
"""

import os

import requests
from dotenv import load_dotenv


load_dotenv()


BIRDNET_BASE_URL = os.getenv(
    "BIRDNET_BASE_URL",
    "",
).rstrip("/")


TARGET_PER_STATUS = 5

PAGE_SIZE = 500

MAX_PAGES = 30


def get_detection_page(
    limit,
    offset,
):
    """Retrieve one read-only page of BirdNET-Go detections."""

    if not BIRDNET_BASE_URL:
        raise RuntimeError(
            "BIRDNET_BASE_URL is not configured."
        )

    url = (
        f"{BIRDNET_BASE_URL}"
        "/api/v2/detections"
    )

    params = {
        "limit": limit,
        "offset": offset,
        "sortBy": "date_desc",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Unexpected BirdNET-Go response format."
        )

    detections = payload.get(
        "data",
        [],
    )

    if not isinstance(
        detections,
        list,
    ):
        raise RuntimeError(
            "BirdNET-Go response field 'data' "
            "is not a list."
        )

    return payload


def collect_reviewed_detections():
    """Collect a small sample of reviewed detections locally."""

    correct = []

    false_positive = []

    offset = 0

    total_available = None

    pages_checked = 0

    while pages_checked < MAX_PAGES:

        print(
            f"Scanning detections "
            f"{offset} to {offset + PAGE_SIZE - 1}..."
        )

        payload = get_detection_page(
            limit=PAGE_SIZE,
            offset=offset,
        )

        detections = payload.get(
            "data",
            [],
        )

        total_available = payload.get(
            "total",
            total_available,
        )

        if not detections:
            break

        for detection in detections:

            verified = str(
                detection.get(
                    "verified",
                    "",
                )
            ).strip().lower()

            if (
                verified == "correct"
                and len(correct) < TARGET_PER_STATUS
            ):
                correct.append(
                    detection
                )

            elif (
                verified == "false_positive"
                and len(false_positive) < TARGET_PER_STATUS
            ):
                false_positive.append(
                    detection
                )

        pages_checked += 1

        if (
            len(correct) >= TARGET_PER_STATUS
            and
            len(false_positive) >= TARGET_PER_STATUS
        ):
            break

        offset += PAGE_SIZE

        if (
            total_available is not None
            and offset >= total_available
        ):
            break

    return {
        "correct": correct,
        "false_positive": false_positive,
        "total_available": total_available,
        "pages_checked": pages_checked,
    }


def print_detection(
    detection,
):
    """Print one detection."""

    print(
        "ID:",
        detection.get(
            "id"
        ),
    )

    print(
        "Species:",
        detection.get(
            "commonName"
        ),
        f"({detection.get('scientificName')})",
    )

    confidence = detection.get(
        "confidence"
    )

    if confidence is not None:
        print(
            "Confidence:",
            f"{float(confidence) * 100:.1f}%",
        )

    print(
        "Verified:",
        detection.get(
            "verified"
        ),
    )

    print(
        "Date/time:",
        detection.get(
            "date"
        ),
        detection.get(
            "time"
        ),
    )

    print(
        "Clip:",
        detection.get(
            "clipName"
        ),
    )

    print("-" * 72)


def print_sample(
    heading,
    detections,
):
    """Print one reviewed sample."""

    print()
    print("=" * 72)
    print(heading)
    print("=" * 72)

    print(
        f"Retrieved: {len(detections)}"
    )

    print()

    for detection in detections:
        print_detection(
            detection
        )


def main():
    """Find reviewed BirdNET-Go detections."""

    print("=" * 72)
    print("BIRDNET-GO HISTORICAL REVIEW SAMPLE")
    print("=" * 72)

    print(
        "Server-side verification filtering is not assumed."
    )

    print(
        "Scanning detections and filtering verification status locally..."
    )

    result = collect_reviewed_detections()

    print_sample(
        "HUMAN VERIFIED: CORRECT",
        result[
            "correct"
        ],
    )

    print_sample(
        "HUMAN VERIFIED: FALSE POSITIVE",
        result[
            "false_positive"
        ],
    )

    print()
    print("=" * 72)
    print("SCAN SUMMARY")
    print("=" * 72)

    print(
        "Total detections reported by BirdNET-Go:",
        result[
            "total_available"
        ],
    )

    print(
        "Pages checked:",
        result[
            "pages_checked"
        ],
    )

    print(
        "Correct found:",
        len(
            result[
                "correct"
            ]
        ),
    )

    print(
        "False positives found:",
        len(
            result[
                "false_positive"
            ]
        ),
    )

    print()
    print(
        "No BirdNET-Go records were modified."
    )


if __name__ == "__main__":
    main()