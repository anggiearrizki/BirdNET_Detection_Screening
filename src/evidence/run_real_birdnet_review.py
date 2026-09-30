"""Run a real BirdNET-Go detection through the review prototype.

Current workflow:

BirdNET-Go detection
→ retrieve metadata
→ retrieve audio
→ normalise BirdNET payload
→ taxonomy resolution
→ Species Register check
→ supporting evidence
→ Gemini interpretation
→ response validation
→ EarthRanger mapping preview

Important:
The audio file is retrieved and attached to the candidate metadata,
but Gemini is not yet receiving the audio contents in this version.
That will be the next integration step.
"""

from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )

from integration.birdnet_review_writer import (
    preview_comment_write,
)

from integration.birdnet_client import (
    get_detection,
    save_detection_audio,
)

from ingestion.birdnet_detection_adapter import (
    build_candidate_from_birdnet,
    print_candidate_preview,
)

from evidence.candidate_evidence_packet import (
    build_candidate_evidence_packet,
    print_candidate_packet,
)

from ai.gemini_prompt import (
    build_gemini_prompt,
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

from integration.birdnet_review_note import (
    build_birdnet_review_note,
    print_birdnet_review_note,
)

def build_packet_from_candidate(
    candidate,
):
    """Pass the normalised BirdNET candidate into the evidence workflow."""

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

    # ---------------------------------------------------------
    # Configuration for this real test
    # ---------------------------------------------------------

    detection_id = 10191

    # Temporary property assignment.
    # Later this should be determined from BirdNET station /
    # deployment configuration automatically.
    island = "Nikoi"

    # ---------------------------------------------------------
    # 1. Retrieve real BirdNET-Go detection
    # ---------------------------------------------------------

    print("=" * 70)
    print("REAL BIRDNET-GO REVIEW WORKFLOW")
    print("=" * 70)

    print(
        f"Retrieving BirdNET-Go detection {detection_id}..."
    )

    detection = get_detection(
        detection_id
    )

    # ---------------------------------------------------------
    # 2. Retrieve actual detection audio
    # ---------------------------------------------------------

    print(
        "Retrieving detection audio..."
    )

    audio_result = save_detection_audio(
        detection_id
    )

    # ---------------------------------------------------------
    # 3. Normalise BirdNET payload
    # ---------------------------------------------------------

    candidate = build_candidate_from_birdnet(
        detection=detection,
        audio_result=audio_result,
        island=island,
        environment="terrestrial",
    )

    print()

    print_candidate_preview(
        candidate
    )

    # ---------------------------------------------------------
    # 4. Build scientific evidence packet
    # ---------------------------------------------------------

    packet = build_packet_from_candidate(
        candidate
    )

    print()

    print_candidate_packet(
        packet
    )

    # ---------------------------------------------------------
    # 5. Generate Gemini prompt
    # ---------------------------------------------------------

    prompt = build_gemini_prompt(
        packet
    )

    # ---------------------------------------------------------
    # 6. Live Gemini interpretation
    # ---------------------------------------------------------

    print()

    print("=" * 70)
    print("LIVE GEMINI INTERPRETATION")
    print("=" * 70)

    print(
        "Sending real BirdNET evidence packet to Gemini..."
    )


    gemini_result = run_gemini_interpretation(
        prompt,
        audio_path=(
            candidate[
                "birdnet_data"
            ][
                "audio_reference"
            ]
        ),
        audio_mime_type=(
            candidate[
                "birdnet_data"
            ][
                "audio_content_type"
            ]
        ),
    )

    print(
        "Gemini response received."
    )

    # ---------------------------------------------------------
    # 7. Validate AI response
    # ---------------------------------------------------------

    validated_gemini_result = validate_gemini_response(
        gemini_result
    )

    print()

    print_gemini_validation_summary(
        validated_gemini_result
    )

    # ---------------------------------------------------------
    # 8. EarthRanger mapping preview
    # ---------------------------------------------------------

    earthranger_event = build_earthranger_event_preview(
        candidate=candidate,
        candidate_packet=packet,
        gemini_result=validated_gemini_result,
    )

    print()

    print_earthranger_event_preview(
        earthranger_event
    )

    # ---------------------------------------------------------
    # 9. Generate BirdNET-Go review note
    # ---------------------------------------------------------

    birdnet_review_note = build_birdnet_review_note(
        candidate=candidate,
        gemini_result=validated_gemini_result,
    )

    print()

    print_birdnet_review_note(
        birdnet_review_note
    )

    # ---------------------------------------------------------
    # 10. Preview BirdNET-Go Notes write-back
    # ---------------------------------------------------------

    print()

    preview_comment_write(
        detection_id=candidate[
            "source_record_id"
        ],
        note_text=birdnet_review_note,
    )


    # ---------------------------------------------------------
    # 11. Current prototype boundary
    # ---------------------------------------------------------

    print()

    print("=" * 70)
    print("CURRENT AUTOMATION BOUNDARY")
    print("=" * 70)

    print(
        "BirdNET detection retrieved: YES"
    )

    print(
    "BirdNET Notes write-back dry run: YES"
    )

    print(
        "BirdNET audio retrieved: YES"
    )

    print(
        "Evidence packet generated: YES"
    )

    print(
        "Live Gemini interpretation: YES"
    )

    print(
        "Gemini output validated: YES"
    )

    print(
        "EarthRanger mapping generated: YES"
    )

    print(
        "Gemini audio analysis: YES"
    )

    print(
        "BirdNET Notes generated: YES"
    )

    print(
        "BirdNET Notes write-back: NOT YET"
    )

    print(
        "BirdNET review status write-back: NOT YET"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
