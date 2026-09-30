"""Run a small historical BirdNET-Go validation benchmark.

This script compares the automated Gemini screening recommendation
against existing human-reviewed BirdNET-Go detections.

Important:
- BirdNET-Go is read only.
- No comments are written.
- No review statuses are changed.
- One fixed Gemini model is used for the entire benchmark.
- `review_required` is treated as an abstention, not as a direct error.
"""

import sys
from pathlib import Path


# ---------------------------------------------------------
# Project path setup
# ---------------------------------------------------------


CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parents[1]
EVIDENCE_DIR = SRC_DIR / "evidence"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )

if str(EVIDENCE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(EVIDENCE_DIR),
    )


# ---------------------------------------------------------
# Project imports
# ---------------------------------------------------------

from ai.gemini_client import run_gemini_interpretation
from ai.gemini_prompt import build_gemini_prompt
from ai.gemini_response import validate_gemini_response

from evidence.run_real_birdnet_review import (
    build_packet_from_candidate,
)

from ingestion.birdnet_detection_adapter import (
    build_candidate_from_birdnet,
)

from integration.birdnet_client import (
    get_detection,
    save_detection_audio,
)


# ---------------------------------------------------------
# Benchmark configuration
# ---------------------------------------------------------

BENCHMARK_MODEL = "gemini-3.5-flash"


BENCHMARK_CASES = [
    {
        "detection_id": 9423,
        "human_status": "correct",
    },
    {
        "detection_id": 9175,
        "human_status": "correct",
    },
    {
        "detection_id": 9109,
        "human_status": "correct",
    },
    {
        "detection_id": 7078,
        "human_status": "correct",
    },
    {
        "detection_id": 7071,
        "human_status": "correct",
    },
    {
        "detection_id": 8836,
        "human_status": "false_positive",
    },
    {
        "detection_id": 7166,
        "human_status": "false_positive",
    },
    {
        "detection_id": 6664,
        "human_status": "false_positive",
    },
    {
        "detection_id": 6616,
        "human_status": "false_positive",
    },
    {
        "detection_id": 6100,
        "human_status": "false_positive",
    },
]


# Temporary property assignment for this prototype.
# Later this should come from the BirdNET station/deployment mapping.
BENCHMARK_ISLAND = "Nikoi"


# ---------------------------------------------------------
# Single detection benchmark
# ---------------------------------------------------------

def run_benchmark_case(
    detection_id,
    human_status,
):
    """Run one historical detection through the AI review workflow."""

    print()
    print("=" * 72)
    print(
        f"BENCHMARK DETECTION {detection_id}"
    )
    print("=" * 72)

    print(
        f"Human status: {human_status}"
    )

    # -----------------------------------------------------
    # 1. Retrieve historical BirdNET-Go detection
    # -----------------------------------------------------

    detection = get_detection(
        detection_id
    )

    # -----------------------------------------------------
    # 2. Retrieve the original BirdNET-Go audio
    # -----------------------------------------------------

    audio_result = save_detection_audio(
        detection_id
    )

    # -----------------------------------------------------
    # 3. Normalise BirdNET detection
    # -----------------------------------------------------

    candidate = build_candidate_from_birdnet(
        detection=detection,
        audio_result=audio_result,
        island=BENCHMARK_ISLAND,
        environment="terrestrial",
    )

    # -----------------------------------------------------
    # 4. Build evidence packet
    # -----------------------------------------------------

    packet = build_packet_from_candidate(
        candidate
    )

    # -----------------------------------------------------
    # 5. Build Gemini prompt
    # -----------------------------------------------------

    prompt = build_gemini_prompt(
        packet
    )

    # -----------------------------------------------------
    # 6. Run one FIXED Gemini model
    # -----------------------------------------------------

    raw_result = run_gemini_interpretation(
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
        model_override=BENCHMARK_MODEL,
        allow_fallback=False,
    )

    # -----------------------------------------------------
    # 7. Validate Gemini output
    # -----------------------------------------------------

    ai_result = validate_gemini_response(
        raw_result
    )

    ai_status = ai_result[
        "recommended_status"
    ]

    audio_assessment = ai_result[
        "audio_assessment"
    ]

    model_used = ai_result[
        "model_used"
    ]

    # -----------------------------------------------------
    # 8. Compare against human review
    # -----------------------------------------------------

    if ai_status == "review_required":
        comparison = "abstain"

    elif ai_status == human_status:
        comparison = "match"

    else:
        comparison = "mismatch"

    print()
    print(
        f"Species: "
        f"{candidate.get('common_name')} "
        f"({candidate.get('scientific_name')})"
    )

    print(
        "BirdNET confidence:",
        candidate[
            "birdnet_data"
        ].get(
            "confidence"
        ),
    )

    print(
        "Gemini model:",
        model_used,
    )

    print(
        "Audio assessment:",
        audio_assessment,
    )

    print(
        "AI status:",
        ai_status,
    )

    print(
        "Human status:",
        human_status,
    )

    print(
        "Comparison:",
        comparison.upper(),
    )

    return {
        "detection_id":
            detection_id,

        "common_name":
            candidate.get(
                "common_name"
            ),

        "scientific_name":
            candidate.get(
                "scientific_name"
            ),

        "birdnet_confidence":
            candidate[
                "birdnet_data"
            ].get(
                "confidence"
            ),

        "human_status":
            human_status,

        "model_used":
            model_used,

        "audio_assessment":
            audio_assessment,

        "ai_status":
            ai_status,

        "comparison":
            comparison,
    }


# ---------------------------------------------------------
# Benchmark summary
# ---------------------------------------------------------

def print_benchmark_summary(
    results,
):
    """Print simple benchmark metrics."""

    total = len(
        results
    )

    matches = sum(
        1
        for result in results
        if result[
            "comparison"
        ] == "match"
    )

    mismatches = sum(
        1
        for result in results
        if result[
            "comparison"
        ] == "mismatch"
    )

    abstentions = sum(
        1
        for result in results
        if result[
            "comparison"
        ] == "abstain"
    )

    automated_decisions = (
        matches
        +
        mismatches
    )

    print()
    print("=" * 72)
    print("HISTORICAL BENCHMARK SUMMARY")
    print("=" * 72)

    print(
        f"Model: {BENCHMARK_MODEL}"
    )

    print(
        f"Total completed cases: {total}"
    )

    print(
        f"Direct matches: {matches}"
    )

    print(
        f"Direct mismatches: {mismatches}"
    )

    print(
        f"Review-required abstentions: {abstentions}"
    )

    if automated_decisions:

        agreement_rate = (
            matches
            /
            automated_decisions
        )

        print(
            "Agreement among automated decisions: "
            f"{agreement_rate * 100:.1f}%"
        )

    if total:

        automation_coverage = (
            automated_decisions
            /
            total
        )

        print(
            "Automation coverage: "
            f"{automation_coverage * 100:.1f}%"
        )

    print()
    print("-" * 72)

    for result in results:

        print(
            f"{result['detection_id']} | "
            f"{result['human_status']} | "
            f"{result['ai_status']} | "
            f"{result['comparison']}"
        )

    print("-" * 72)

    print()
    print(
        "These results are exploratory only. "
        "Ten detections are not sufficient to establish "
        "safe automated verification thresholds."
    )

    print(
        "No BirdNET-Go records were modified."
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    """Run the historical benchmark."""

    print("=" * 72)
    print("BIRDNET-GO HISTORICAL AI BENCHMARK")
    print("=" * 72)

    print(
        f"Fixed Gemini model: {BENCHMARK_MODEL}"
    )

    print(
        f"Cases: {len(BENCHMARK_CASES)}"
    )

    print(
        "Fallback enabled: NO"
    )

    print(
        "BirdNET-Go write-back: NO"
    )

    results = []

    failures = []

    for case in BENCHMARK_CASES:

        detection_id = case[
            "detection_id"
        ]

        human_status = case[
            "human_status"
        ]

        try:

            result = run_benchmark_case(
                detection_id=detection_id,
                human_status=human_status,
            )

            results.append(
                result
            )

        except Exception as exc:

            print()
            print(
                f"FAILED detection {detection_id}: "
                f"{type(exc).__name__}: {exc}"
            )

            failures.append(
                {
                    "detection_id":
                        detection_id,

                    "human_status":
                        human_status,

                    "error":
                        str(exc),
                }
            )

    print_benchmark_summary(
        results
    )

    if failures:

        print()
        print("=" * 72)
        print("FAILED CASES")
        print("=" * 72)

        for failure in failures:

            print(
                f"{failure['detection_id']} | "
                f"{failure['human_status']} | "
                f"{failure['error']}"
            )


if __name__ == "__main__":
    main()