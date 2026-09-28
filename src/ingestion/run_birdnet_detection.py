"""Run one real BirdNET-Go detection through the ingestion adapter.

This is a read-only prototype step.

It retrieves:
- the real BirdNET-Go detection
- the associated audio recording
- converts both into the project's internal screening structure

No BirdNET review status or notes are modified.
"""

from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from integration.birdnet_client import (
    get_detection,
    save_detection_audio,
)

from ingestion.birdnet_detection_adapter import (
    build_candidate_from_birdnet,
    print_candidate_preview,
)


def main():

    detection_id = 10191

    # For this test only.
    # Later the property should come from station / deployment configuration.
    island = "Nikoi"

    print(
        f"Retrieving real BirdNET-Go detection {detection_id}..."
    )

    detection = get_detection(
        detection_id
    )

    audio_result = save_detection_audio(
        detection_id
    )

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


if __name__ == "__main__":
    main()