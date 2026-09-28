"""Run the candidate workflow from an incoming detection payload.

This represents the interface between an upstream monitoring system,
such as BirdNET-Go, and the Species Register evidence workflow.

In production, this dictionary would be populated automatically by
the BirdNET integration rather than entered manually.
"""

from pathlib import Path
import sys


# Add src/ to the Python path so modules outside this folder
# can be imported during the prototype.
SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from ai.gemini_prompt import (
    build_gemini_prompt,
    print_prompt_preview,
)

from ai.gemini_client import (
    run_gemini_interpretation,
)

from ai.gemini_response import (
    validate_gemini_response,
    print_gemini_validation_summary,
)

from integration.earthranger_event_mapper import (
    build_earthranger_event_preview,
    print_earthranger_event_preview,
)

from candidate_evidence_packet import (
    build_candidate_evidence_packet,
    print_candidate_packet,
)


def process_candidate(candidate):
    """Process one incoming candidate detection."""

    return build_candidate_evidence_packet(
        common_name=candidate.get(
            "common_name"
        ),

        scientific_name=candidate.get(
            "scientific_name"
        ),

        expected_rank=candidate.get(
            "expected_rank",
            "species",
        ),

        island=candidate.get(
            "island"
        ),

        taxon_group=candidate.get(
            "taxon_group"
        ),

        environment=candidate.get(
            "environment"
        ),

        candidate_source=candidate.get(
            "candidate_source"
        ),

        source_record_id=candidate.get(
            "source_record_id"
        ),

        source_reference=candidate.get(
            "source_reference"
        ),

        birdnet_data=candidate.get(
            "birdnet_data"
        ),
    )


def main():

    # Simulation only.
    #
    # The upstream candidate is still entered manually while
    # BirdNET-Go integration is unavailable.
    #
    # Gemini interpretation below is LIVE.

    incoming_candidate = {
        "candidate_source":
            "BirdNET",

        "common_name":
            "Black-crowned Night Heron",

        "scientific_name":
            "Nycticorax nycticorax",

        "expected_rank":
            "species",

        "taxon_group":
            "birds",

        "environment":
            "terrestrial",

        "island":
            "Nikoi",

        "birdnet_data": {
            "historical_detection_count":
                2,

            "historical_avg_confidence":
                0.915,

            "historical_max_confidence":
                0.94,

            "first_detected":
                "2026-09-07 18:01:59",

            "last_detected":
                "2026-09-08 14:03:54",
        },
    }

    # ---------------------------------------------------------
    # 1. Build candidate evidence packet
    # ---------------------------------------------------------

    packet = process_candidate(
        incoming_candidate
    )

    print_candidate_packet(
        packet
    )

    print()

    # ---------------------------------------------------------
    # 2. Build Gemini prompt
    # ---------------------------------------------------------

    print_prompt_preview(
        packet
    )

    prompt = build_gemini_prompt(
        packet
    )

    # ---------------------------------------------------------
    # 3. LIVE Gemini interpretation
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("LIVE GEMINI INTERPRETATION")
    print("=" * 70)
    print("Sending structured evidence packet to Gemini...")

    gemini_result = run_gemini_interpretation(
        prompt
    )

    print("Gemini response received.")
    print("=" * 70)

    # ---------------------------------------------------------
    # 4. Validate Gemini structured output
    # ---------------------------------------------------------

    validated_gemini_result = validate_gemini_response(
        gemini_result
    )

    print()

    print_gemini_validation_summary(
        validated_gemini_result
    )

    # ---------------------------------------------------------
    # 5. Map validated result to existing EarthRanger event
    # ---------------------------------------------------------

    earthranger_event = build_earthranger_event_preview(
        candidate=incoming_candidate,
        candidate_packet=packet,
        gemini_result=validated_gemini_result,
    )

    print()

    print_earthranger_event_preview(
        earthranger_event
    )


if __name__ == "__main__":
    main()