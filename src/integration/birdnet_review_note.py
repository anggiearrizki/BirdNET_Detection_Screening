"""Build a controlled BirdNET-Go review note from validated AI output.

This module generates the text that can eventually be written into the
Notes section of a BirdNET-Go detection.

Important:
This does NOT change the BirdNET review status.
AI recommendations remain screening recommendations until the workflow
has been empirically validated against human-reviewed detections.
"""


ALLOWED_AUDIO_ASSESSMENTS = {
    "consistent",
    "inconsistent",
    "uncertain",
}


ALLOWED_RECOMMENDED_STATUSES = {
    "correct",
    "false_positive",
    "review_required",
}


def _clean_text(
    value,
):
    """Return a safe stripped string."""

    if value is None:
        return ""

    return str(
        value
    ).strip()


def build_birdnet_review_note(
    candidate,
    gemini_result,
):
    """Build a concise BirdNET-Go Notes entry."""

    if not isinstance(
        candidate,
        dict,
    ):
        raise ValueError(
            "candidate must be a dictionary."
        )

    if not isinstance(
        gemini_result,
        dict,
    ):
        raise ValueError(
            "gemini_result must be a dictionary."
        )

    birdnet_data = candidate.get(
        "birdnet_data",
        {},
    )

    common_name = _clean_text(
        candidate.get(
            "common_name"
        )
    )

    scientific_name = _clean_text(
        candidate.get(
            "scientific_name"
        )
    )

    detection_id = candidate.get(
        "source_record_id"
    )

    confidence = birdnet_data.get(
        "confidence"
    )

    audio_assessment = _clean_text(
        gemini_result.get(
            "audio_assessment"
        )
    ).lower()

    recommended_status = _clean_text(
        gemini_result.get(
            "recommended_status"
        )
    ).lower()

    audio_evidence = _clean_text(
        gemini_result.get(
            "audio_evidence"
        )
    )

    review_recommendation = _clean_text(
        gemini_result.get(
            "review_recommendation"
        )
    )

    uncertainties = gemini_result.get(
        "uncertainties",
        [],
    )

    if (
        audio_assessment
        not in ALLOWED_AUDIO_ASSESSMENTS
    ):
        raise ValueError(
            "Invalid Gemini audio_assessment."
        )

    if (
        recommended_status
        not in ALLOWED_RECOMMENDED_STATUSES
    ):
        raise ValueError(
            "Invalid Gemini recommended_status."
        )

    if confidence is None:
        confidence_text = "Not available"

    else:
        confidence_text = (
            f"{float(confidence) * 100:.0f}%"
        )

    uncertainty_lines = []

    for item in uncertainties:
        text = _clean_text(
            item
        )

        if text:
            uncertainty_lines.append(
                f"- {text}"
            )

    if uncertainty_lines:
        uncertainty_section = (
            "\n".join(
                uncertainty_lines
            )
        )

    else:
        uncertainty_section = (
            "- No additional uncertainty supplied."
        )

    note = (
        "Automated Screening Assessment\n\n"
        f"Detection ID: {detection_id}\n"
        f"Species: {common_name} "
        f"({scientific_name})\n"
        f"BirdNET confidence: {confidence_text}\n\n"

        f"Audio assessment: "
        f"{audio_assessment}\n"
        f"Audio evidence: "
        f"{audio_evidence}\n\n"

        "Uncertainties:\n"
        f"{uncertainty_section}\n\n"

        f"AI screening recommendation: "
        f"{recommended_status}\n"
        f"Recommended action: "
        f"{review_recommendation}\n\n"

        "Note: This is an automated screening recommendation. "
        "It does not independently confirm biological presence. "
        "Final BirdNET verification remains human-controlled "
        "until the automated review workflow has been validated."
    )

    return note


def print_birdnet_review_note(
    note,
):
    """Print the proposed BirdNET-Go Notes content."""

    print("=" * 70)
    print("BIRDNET-GO NOTE PREVIEW")
    print("=" * 70)
    print()
    print(note)
    print()
    print("=" * 70)