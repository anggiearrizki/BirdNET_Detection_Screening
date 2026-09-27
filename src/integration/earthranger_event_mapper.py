"""Map screening and Gemini outputs to the existing EarthRanger event.

This module uses the existing EarthRanger event type:

    Bird Acoustic New Species

The field names below are based on the event form currently configured
in the Bintan EarthRanger Admin Portal.

This is currently a logical mapping preview, not the final EarthRanger
API payload. EarthRanger internal field identifiers can be added later
without changing the upstream screening workflow.
"""

import json


EARTHRANGER_EVENT_TYPE = "Bird Acoustic New Species"


def _first_value(*values):
    """Return the first value that is not None or empty."""

    for value in values:
        if value is not None and value != "":
            return value

    return None


def _confidence_percent(value):
    """Convert a 0-1 confidence value to percent where possible."""

    if value is None:
        return None

    try:
        numeric_value = float(value)

        if 0 <= numeric_value <= 1:
            return round(
                numeric_value * 100,
                2,
            )

        return round(
            numeric_value,
            2,
        )

    except (TypeError, ValueError):
        return None


def build_earthranger_event_preview(
    candidate,
    candidate_packet,
    gemini_result,
):
    """
    Build a logical EarthRanger event representation.

    Existing EarthRanger fields are preserved under their current
    form sections.

    Proposed Gemini fields are kept in a separate section so they can
    later be added to the existing event type without creating a new
    EarthRanger event type.
    """

    birdnet_data = (
        candidate.get("birdnet_data")
        or {}
    )

    accepted_taxon = (
        candidate_packet.get(
            "accepted_taxon"
        )
        or {}
    )

    scientific_name = _first_value(
        accepted_taxon.get(
            "scientific_name"
        ),
        accepted_taxon.get(
            "accepted_scientific_name"
        ),
        candidate.get(
            "scientific_name"
        ),
    )

    common_name = _first_value(
        candidate.get(
            "common_name"
        ),
        accepted_taxon.get(
            "common_name"
        ),
    )

    confidence = _first_value(
        birdnet_data.get(
            "confidence"
        ),
        birdnet_data.get(
            "current_confidence"
        ),
    )

    event_preview = {
        "event_type":
            EARTHRANGER_EVENT_TYPE,

        "geometry_type":
            "Point",

        "default_state":
            "Active",

        "existing_earthranger_fields": {

            "Species": {
                "Common Name":
                    common_name,

                "Scientific Name":
                    scientific_name,

                "Confidence":
                    confidence,

                "Confidence Percent":
                    _confidence_percent(
                        confidence
                    ),
            },

            "BirdNET-Go": {
                "BirdNET Detection ID":
                    candidate.get(
                        "source_record_id"
                    ),

                "BirdNET Location":
                    _first_value(
                        birdnet_data.get(
                            "location"
                        ),
                        candidate.get(
                            "birdnet_location"
                        ),
                    ),

                "Island":
                    candidate.get(
                        "island"
                    ),
            },

            "References": {
                "BirdNET Detection URL":
                    candidate.get(
                        "source_reference"
                    ),

                "Bird Image URL":
                    birdnet_data.get(
                        "bird_image_url"
                    ),
            },

            "Detection Context": {
                "Days Since First Seen":
                    birdnet_data.get(
                        "days_since_first_seen"
                    ),

                "Source System":
                    candidate.get(
                        "candidate_source"
                    ),
            },

            "Audio": {
                "Audio Filename":
                    birdnet_data.get(
                        "audio_filename"
                    ),

                "Audio Content Type":
                    birdnet_data.get(
                        "audio_content_type"
                    ),

                "Audio Size Bytes":
                    birdnet_data.get(
                        "audio_size_bytes"
                    ),

                "Audio SHA-256":
                    birdnet_data.get(
                        "audio_sha256"
                    ),
            },
        },

        "proposed_gemini_fields": {

            "AI Assessment":
                gemini_result.get(
                    "summary"
                ),

            "Species Register Context":
                gemini_result.get(
                    "register_context"
                ),

            "Evidence Highlights":
                gemini_result.get(
                    "evidence_highlights",
                    [],
                ),

            "Uncertainties":
                gemini_result.get(
                    "uncertainties",
                    [],
                ),

            "Review Recommendation":
                gemini_result.get(
                    "review_recommendation"
                ),

            "Suggested Priority":
                gemini_result.get(
                    "suggested_priority"
                ),
        },

        "notification": {
            "text":
                gemini_result.get(
                    "notification_text"
                )
        },

        "mapping_status": {
            "schema_basis":
                (
                    "Existing EarthRanger "
                    "'Bird Acoustic New Species' "
                    "event form"
                ),

            "api_payload_status":
                "not_yet_mapped",

            "note":
                (
                    "This preview uses EarthRanger display field names. "
                    "Internal EarthRanger field identifiers and API "
                    "payload structure still need to be mapped before "
                    "live event creation."
                ),
        },
    }

    return event_preview


def print_earthranger_event_preview(
    event_preview,
):
    """Print the mapped EarthRanger event during prototyping."""

    print("=" * 70)
    print("EARTHRANGER EVENT MAPPING PREVIEW")
    print("=" * 70)
    print()

    print(
        json.dumps(
            event_preview,
            indent=2,
            default=str,
        )
    )

    print()
    print("=" * 70)