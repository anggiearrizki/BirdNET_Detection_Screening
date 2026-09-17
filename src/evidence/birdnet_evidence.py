"""Construct BirdNET evidence for a candidate bird record.

BirdNET is an upstream detection source in the Species Register workflow.

This module structures BirdNET acoustic/detection information so it can be
attached to a candidate evidence packet.

Important:
- BirdNET confidence is model output, not probability of biological presence;
- repeated detections are supporting evidence, not confirmation;
- acoustic/human validation remains separate;
- missing BirdNET history does not imply biological absence.
"""


def build_birdnet_evidence(
    scientific_name,
    common_name=None,

    # Current candidate detection
    detection_confidence=None,
    detection_datetime=None,
    station_id=None,
    audio_reference=None,

    # Optional BirdNET history
    historical_detection_count=None,
    historical_avg_confidence=None,
    historical_max_confidence=None,
    first_detected=None,
    last_detected=None,
):
    """Build a standard BirdNET evidence object."""

    history_available = (
        historical_detection_count is not None
    )

    if history_available:
        history_status = "available"
    else:
        history_status = "not_available"

    return {
        "source":
            "BirdNET",

        "evidence_type":
            "acoustic_detection_history",

        "scientific_name":
            scientific_name,

        "common_name":
            common_name,

        # -----------------------------------------------------
        # Current candidate detection
        # -----------------------------------------------------

        "candidate_detection": {
            "confidence":
                detection_confidence,

            "datetime":
                detection_datetime,

            "station_id":
                station_id,

            "audio_reference":
                audio_reference,
        },

        # -----------------------------------------------------
        # Historical BirdNET context
        # -----------------------------------------------------

        "history": {
            "status":
                history_status,

            "detection_count":
                historical_detection_count,

            "average_confidence":
                historical_avg_confidence,

            "maximum_confidence":
                historical_max_confidence,

            "first_detected":
                first_detected,

            "last_detected":
                last_detected,
        },

        # -----------------------------------------------------
        # Interpretation
        # -----------------------------------------------------

        "interpretation": {
            "confidence_note":
                (
                    "BirdNET confidence is a model output and "
                    "must not be interpreted as a probability "
                    "that the species is biologically present."
                ),

            "history_note":
                (
                    "Repeated BirdNET detections provide "
                    "supporting acoustic context but do not "
                    "independently confirm species presence."
                ),

            "human_validation_required":
                True,
        },
    }


def main():

    # Temporary test using the Night Heron candidate.
    #
    # History values here come from the BirdNET species-summary
    # example previously inspected. They are used only to verify
    # the adapter structure.

    evidence = build_birdnet_evidence(
        common_name=(
            "Black-crowned Night Heron"
        ),

        scientific_name=(
            "Nycticorax nycticorax"
        ),

        historical_detection_count=2,
        historical_avg_confidence=0.915,
        historical_max_confidence=0.94,

        first_detected=(
            "2026-09-07 18:01:59"
        ),

        last_detected=(
            "2026-09-08 14:03:54"
        ),
    )

    print("=" * 75)
    print("BIRDNET CANDIDATE EVIDENCE")
    print("=" * 75)

    print(
        f"\nScientific name: "
        f"{evidence['scientific_name']}"
    )

    print(
        f"History status: "
        f"{evidence['history']['status']}"
    )

    print(
        f"Historical detections: "
        f"{evidence['history']['detection_count']}"
    )

    print(
        f"Average confidence: "
        f"{evidence['history']['average_confidence']}"
    )

    print(
        f"Maximum confidence: "
        f"{evidence['history']['maximum_confidence']}"
    )

    print(
        f"First detected: "
        f"{evidence['history']['first_detected']}"
    )

    print(
        f"Last detected: "
        f"{evidence['history']['last_detected']}"
    )

    print(
        "\nHuman acoustic validation required: "
        f"{evidence['interpretation']['human_validation_required']}"
    )

    print("=" * 75)


if __name__ == "__main__":
    main()