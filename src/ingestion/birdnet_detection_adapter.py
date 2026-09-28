"""Convert a real BirdNET-Go detection into the internal screening format.

BirdNET-Go uses its own detection payload structure. The rest of this
project should not depend directly on those raw field names.

This adapter normalises a BirdNET-Go detection and its downloaded audio
into the generic candidate structure consumed by the screening workflow.
"""

from datetime import datetime


class BirdNETAdapterError(ValueError):
    """Raised when a BirdNET detection cannot be normalised safely."""


def _first_value(
    data,
    *field_names,
):
    """Return the first non-empty value from several possible field names."""

    for field_name in field_names:

        value = data.get(
            field_name
        )

        if value not in (
            None,
            "",
        ):
            return value

    return None


def _build_detection_datetime(
    detection,
):
    """Build a single detection datetime from BirdNET date/time fields."""

    date_value = _first_value(
        detection,
        "date",
        "detectionDate",
        "detection_date",
    )

    time_value = _first_value(
        detection,
        "time",
        "detectionTime",
        "detection_time",
    )

    if date_value and time_value:
        return (
            f"{date_value} "
            f"{time_value}"
        )

    return _first_value(
        detection,
        "datetime",
        "timestamp",
        "createdAt",
        "created_at",
    )


def _normalise_confidence(
    value,
):
    """Convert BirdNET confidence into a 0-1 float where possible."""

    if value is None:
        return None

    try:
        confidence = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    # Some sources may expose 92 instead of 0.92.
    if confidence > 1:
        confidence = (
            confidence / 100.0
        )

    return confidence


def build_candidate_from_birdnet(
    detection,
    audio_result=None,
    island=None,
    environment="terrestrial",
):
    """Convert BirdNET-Go detection data to the internal candidate schema."""

    if not isinstance(
        detection,
        dict,
    ):
        raise BirdNETAdapterError(
            "BirdNET detection must be a dictionary."
        )

    detection_id = _first_value(
        detection,
        "id",
        "detectionId",
        "detection_id",
    )

    common_name = _first_value(
        detection,
        "commonName",
        "common_name",
    )

    scientific_name = _first_value(
        detection,
        "scientificName",
        "scientific_name",
    )

    confidence = _normalise_confidence(
        _first_value(
            detection,
            "confidence",
            "score",
        )
    )

    detection_datetime = (
        _build_detection_datetime(
            detection
        )
    )

    verified_status = _first_value(
        detection,
        "verified",
        "verification",
        "reviewStatus",
        "review_status",
    )

    clip_name = _first_value(
        detection,
        "clipName",
        "clip_name",
        "filename",
    )

    latitude = _first_value(
        detection,
        "latitude",
        "lat",
    )

    longitude = _first_value(
        detection,
        "longitude",
        "lon",
        "lng",
    )

    station_id = _first_value(
        detection,
        "stationId",
        "station_id",
        "source",
    )

    if not scientific_name:
        raise BirdNETAdapterError(
            "BirdNET detection does not contain a scientific name."
        )

    audio_reference = None
    audio_content_type = None
    audio_size_bytes = None

    if audio_result:

        audio_reference = audio_result.get(
            "path"
        )

        audio_content_type = audio_result.get(
            "content_type"
        )

        audio_size_bytes = audio_result.get(
            "size_bytes"
        )

    candidate = {
        "candidate_source":
            "BirdNET-Go",

        "source_record_id":
            detection_id,

        "source_reference":
            None,

        "common_name":
            common_name,

        "scientific_name":
            scientific_name,

        "expected_rank":
            "species",

        "taxon_group":
            "birds",

        "environment":
            environment,

        "island":
            island,

        "birdnet_data": {
            "confidence":
                confidence,

            "datetime":
                detection_datetime,

            "station_id":
                station_id,

            "audio_reference":
                audio_reference,

            "audio_content_type":
                audio_content_type,

            "audio_size_bytes":
                audio_size_bytes,

            "clip_name":
                clip_name,

            "verified_status":
                verified_status,

            "latitude":
                latitude,

            "longitude":
                longitude,

            # Historical evidence is deliberately separate.
            # It can be added later from the history aggregation layer.
            "historical_detection_count":
                None,

            "historical_avg_confidence":
                None,

            "historical_max_confidence":
                None,

            "first_detected":
                None,

            "last_detected":
                None,
        },
    }

    return candidate


def print_candidate_preview(
    candidate,
):
    """Print the normalised BirdNET candidate for prototype inspection."""

    print("=" * 70)
    print("NORMALISED BIRDNET CANDIDATE")
    print("=" * 70)

    print(
        "Source:",
        candidate.get(
            "candidate_source"
        ),
    )

    print(
        "Detection ID:",
        candidate.get(
            "source_record_id"
        ),
    )

    print(
        "Common name:",
        candidate.get(
            "common_name"
        ),
    )

    print(
        "Scientific name:",
        candidate.get(
            "scientific_name"
        ),
    )

    print(
        "Island:",
        candidate.get(
            "island"
        ),
    )

    birdnet_data = candidate.get(
        "birdnet_data",
        {},
    )

    print(
        "Confidence:",
        birdnet_data.get(
            "confidence"
        ),
    )

    print(
        "Datetime:",
        birdnet_data.get(
            "datetime"
        ),
    )

    print(
        "Verified status:",
        birdnet_data.get(
            "verified_status"
        ),
    )

    print(
        "Audio:",
        birdnet_data.get(
            "audio_reference"
        ),
    )

    print(
        "Audio type:",
        birdnet_data.get(
            "audio_content_type"
        ),
    )

    print(
        "Audio size:",
        birdnet_data.get(
            "audio_size_bytes"
        ),
    )

    print("=" * 70)