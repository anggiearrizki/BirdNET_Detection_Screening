"""BirdNET-Go review write-back adapter.

This module supports:

- dry-run preview
- authenticated BirdNET-Go sessions
- CSRF-protected comment write-back
- comment-only review requests

Important:
This implementation does NOT send a verification status.
It therefore does not mark detections Correct or False Positive.
"""

import os

import requests
from dotenv import load_dotenv


load_dotenv()


BIRDNET_BASE_URL = os.getenv(
    "BIRDNET_BASE_URL",
    "",
).rstrip("/")


BIRDNET_SESSION_COOKIE = os.getenv(
    "BIRDNET_SESSION_COOKIE",
    "",
)


BIRDNET_CSRF_TOKEN = os.getenv(
    "BIRDNET_CSRF_TOKEN",
    "",
)


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


def build_authenticated_session():
    """Build an authenticated BirdNET-Go requests session."""

    if not BIRDNET_SESSION_COOKIE:
        raise BirdNETReviewWriteError(
            "BIRDNET_SESSION_COOKIE is not configured."
        )

    if not BIRDNET_CSRF_TOKEN:
        raise BirdNETReviewWriteError(
            "BIRDNET_CSRF_TOKEN is not configured."
        )

    session = requests.Session()

    session.cookies.set(
        "_gothic_session",
        BIRDNET_SESSION_COOKIE,
    )

    session.cookies.set(
        "csrf",
        BIRDNET_CSRF_TOKEN,
    )

    session.headers.update(
        {
            "X-CSRF-Token":
                BIRDNET_CSRF_TOKEN,

            "Content-Type":
                "application/json",
        }
    )

    return session


def test_authenticated_session(
    session=None,
):
    """Test access to a protected BirdNET-Go endpoint."""

    if session is None:
        session = build_authenticated_session()

    url = (
        f"{BIRDNET_BASE_URL}"
        "/api/v2/detections/ignored"
    )

    response = session.get(
        url,
        timeout=15,
    )

    if not response.ok:
        raise BirdNETReviewWriteError(
            "BirdNET-Go authentication test failed. "
            f"HTTP {response.status_code}: "
            f"{response.text}"
        )

    return response


def preview_comment_write(
    detection_id,
    note_text,
):
    """Preview a BirdNET-Go comment write without changing data."""

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
        "Authentication required: YES"
    )

    print(
        "CSRF protection: YES"
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
    """Write a comment-only review to BirdNET-Go.

    This sends only:

        {
            "comment": "..."
        }

    No verification status is sent.
    """

    url = build_review_url(
        detection_id
    )

    payload = build_comment_payload(
        note_text
    )

    if session is None:
        session = build_authenticated_session()

    response = session.post(
        url,
        json=payload,
        timeout=30,
    )

    if not response.ok:
        raise BirdNETReviewWriteError(
            "BirdNET-Go comment write failed. "
            f"HTTP {response.status_code}: "
            f"{response.text}"
        )

    return response