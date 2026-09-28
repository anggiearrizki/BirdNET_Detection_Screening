"""Read-only BirdNET-Go API client.

This module retrieves real BirdNET-Go detection metadata and the
associated audio recording so that detections can be passed into the
screening and Gemini interpretation workflow.

Write-back and review-status changes are intentionally not implemented
here yet.
"""

from pathlib import Path
import os
import sys

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUDIO_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "birdnet_audio"
)


class BirdNETClientError(RuntimeError):
    """Raised when communication with BirdNET-Go fails."""


def get_base_url():
    """Load and normalise the configured BirdNET-Go base URL."""

    load_dotenv()

    base_url = os.getenv(
        "BIRDNET_BASE_URL"
    )

    if not base_url:
        raise BirdNETClientError(
            "BIRDNET_BASE_URL is not configured."
        )

    return base_url.rstrip("/")


def get_detection(
    detection_id,
):
    """Retrieve one BirdNET-Go detection record."""

    base_url = get_base_url()

    url = (
        f"{base_url}"
        f"/api/v2/detections/"
        f"{detection_id}"
    )

    response = requests.get(
        url,
        timeout=30,
    )

    if response.status_code != 200:
        raise BirdNETClientError(
            "Failed to retrieve BirdNET detection "
            f"{detection_id}: "
            f"HTTP {response.status_code}"
        )

    try:
        detection = response.json()

    except requests.exceptions.JSONDecodeError as exc:
        raise BirdNETClientError(
            "BirdNET detection response was not valid JSON."
        ) from exc

    if not isinstance(
        detection,
        dict,
    ):
        raise BirdNETClientError(
            "BirdNET detection response must be a JSON object."
        )

    return detection


def get_detection_audio(
    detection_id,
):
    """Retrieve the audio bytes associated with one detection."""

    base_url = get_base_url()

    url = (
        f"{base_url}"
        f"/api/v2/audio/"
        f"{detection_id}"
    )

    response = requests.get(
        url,
        timeout=60,
    )

    if response.status_code == 503:
        retry_after = response.headers.get(
            "Retry-After"
        )

        message = (
            f"Audio for detection {detection_id} "
            "is still being prepared by BirdNET-Go."
        )

        if retry_after:
            message += (
                f" Retry after approximately "
                f"{retry_after} seconds."
            )

        raise BirdNETClientError(
            message
        )

    if response.status_code != 200:
        raise BirdNETClientError(
            "Failed to retrieve BirdNET audio "
            f"for detection {detection_id}: "
            f"HTTP {response.status_code}"
        )

    content_type = response.headers.get(
        "Content-Type",
        "application/octet-stream",
    )

    return {
        "detection_id":
            detection_id,

        "content_type":
            content_type,

        "size_bytes":
            len(
                response.content
            ),

        "audio_bytes":
            response.content,
    }


def _extension_from_content_type(
    content_type,
):
    """Choose a reasonable file extension from the response content type."""

    content_type = (
        content_type
        .split(";")[0]
        .strip()
        .lower()
    )

    extension_map = {
        "audio/wav":
            ".wav",

        "audio/x-wav":
            ".wav",

        "audio/wave":
            ".wav",

        "audio/mpeg":
            ".mp3",

        "audio/mp3":
            ".mp3",

        "audio/ogg":
            ".ogg",

        "audio/flac":
            ".flac",

        "audio/x-flac":
            ".flac",

        "audio/mp4":
            ".m4a",

        "audio/x-m4a":
            ".m4a",
    }

    return extension_map.get(
        content_type,
        ".audio",
    )


def save_detection_audio(
    detection_id,
    output_dir=DEFAULT_AUDIO_DIR,
):
    """Download and save one BirdNET-Go detection audio file."""

    audio = get_detection_audio(
        detection_id
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    extension = _extension_from_content_type(
        audio[
            "content_type"
        ]
    )

    output_path = (
        output_dir
        / f"detection_{detection_id}{extension}"
    )

    output_path.write_bytes(
        audio[
            "audio_bytes"
        ]
    )

    return {
        "detection_id":
            detection_id,

        "content_type":
            audio[
                "content_type"
            ],

        "size_bytes":
            audio[
                "size_bytes"
            ],

        "path":
            str(
                output_path
            ),
    }


def print_detection_summary(
    detection,
):
    """Print selected BirdNET detection fields without assuming all exist."""

    print("=" * 70)
    print("BIRDNET-GO DETECTION")
    print("=" * 70)

    fields = [
        "id",
        "date",
        "time",
        "scientificName",
        "commonName",
        "confidence",
        "verified",
        "latitude",
        "longitude",
        "clipName",
    ]

    for field_name in fields:

        if field_name in detection:
            print(
                f"{field_name}: "
                f"{detection.get(field_name)}"
            )

    print("=" * 70)


def main():

    if len(
        sys.argv
    ) < 2:
        print(
            "Usage: "
            "python src/integration/birdnet_client.py "
            "<detection_id>"
        )

        sys.exit(
            1
        )

    detection_id = sys.argv[1]

    print(
        f"Retrieving BirdNET-Go detection "
        f"{detection_id}..."
    )

    detection = get_detection(
        detection_id
    )

    print_detection_summary(
        detection
    )

    print()

    print(
        "Downloading detection audio..."
    )

    audio_result = save_detection_audio(
        detection_id
    )

    print(
        "Audio saved successfully."
    )

    print(
        "Content type:",
        audio_result[
            "content_type"
        ],
    )

    print(
        "Size bytes:",
        audio_result[
            "size_bytes"
        ],
    )

    print(
        "Saved to:",
        audio_result[
            "path"
        ],
    )


if __name__ == "__main__":
    main()