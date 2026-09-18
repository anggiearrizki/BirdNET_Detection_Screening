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
    print_prompt_preview,
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
    # In production this payload will come from BirdNET-Go /
    # the integration layer automatically.

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

    packet = process_candidate(
        incoming_candidate
    )

    print_candidate_packet(
        packet
    )

    print()

    print_prompt_preview(
        packet
    )


if __name__ == "__main__":
    main()