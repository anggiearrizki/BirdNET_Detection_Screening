"""BirdNET-Go review write-back adapter.

The first implementation is intentionally safe:

- Generates a comment-only review request.
- Does NOT send a verification status.
- Defaults to dry-run mode.
- Therefore it cannot mark a detection Correct or False Positive
  unless that behaviour is explicitly added later.

BirdNET-Go endpoint:
POST /api/v2/detections/:id/review
"""


import os

import requests
from dotenv import load_dotenv


load_dotenv()


BIRDNET_BASE_URL = os.getenv(
    "BIRDNET_BASE_URL",
    "",
).rstrip("/")


class BirdNETReviewWriteError(RuntimeError):
    """Raised when BirdNET-Go review write-back fails."""


def build_comment_payload(
    note_text,
):
    """Build a BirdNET-Go comment-only review payload."""

    if not isinstance(
        note_text,
        str,
    ):
        raise ValueError(
            "note_text must be a string."
        )

    note_text = note_text.strip()

    if not note_text:
        raise ValueError(
            "note_text cannot be empty."
        )

    return {
        "comment": note_text,
    }


def build_review_url(
    detection_id,
):
    """Build the BirdNET-Go review endpoint URL."""

    if not BIRDNET_BASE_URL:
        raise BirdNETReviewWriteError(
            "BIRDNET_BASE_URL is not configured."
        )

    return (
        f"{BIRDNET_BASE_URL}"
        f"/api/v2/detections/"
        f"{detection_id}/review"
    )


def preview_comment_write(
    detection_id,
    note_text,
):
    """Preview the BirdNET-Go write without changing anything."""

    url = build_review_url(
        detection_id
    )

    payload = build_comment_payload(
        note_text
    )

    print("=" * 70)
    print("BIRDNET-GO COMMENT WRITE PREVIEW")
    print("=" * 70)

    print(
        f"Detection ID: {detection_id}"
    )

    print(
        f"Endpoint: {url}"
    )

    print(
        "HTTP method: POST"
    )

    print(
        "Verification status included: NO"
    )

    print(
        "Live request sent: NO"
    )

    print()

    print(
        "Payload:"
    )

    print(
        payload
    )

    print()
    print("=" * 70)

    return {
        "url": url,
        "payload": payload,
        "dry_run": True,
    }


def write_comment(
    detection_id,
    note_text,
    session=None,
):
    """Write a comment to BirdNET-Go.

    IMPORTANT:
    This function sends ONLY the comment field.
    It does not send a verification status.

    Authentication still needs to be configured before this
    function should be used against the live BirdNET-Go system.
    """

    url = build_review_url(
        detection_id
    )

    payload = build_comment_payload(
        note_text
    )

    if session is None:
        raise BirdNETReviewWriteError(
            "Authenticated BirdNET session is required. "
            "No live request was sent."
        )

    response = session.post(
        url,
        json=payload,
        timeout=30,
    )

    if not response.ok:
        raise BirdNETReviewWriteError(
            "BirdNET-Go review write failed. "
            f"HTTP {response.status_code}: "
            f"{response.text}"
        )

    return response
