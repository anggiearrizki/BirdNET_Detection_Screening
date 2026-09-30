"""Validate structured Gemini screening output.

This validation layer sits between Gemini and downstream integrations
such as BirdNET-Go and EarthRanger.

Gemini is an interpretation layer only. A structurally valid response
does not itself confirm or reject biological presence.
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


ALLOWED_PRIORITIES = {
    "routine",
    "review",
    "priority_review",
}


class GeminiResponseValidationError(ValueError):
    """Raised when Gemini output does not meet the required schema."""


def _clean_string(
    value,
    field_name,
):
    """Validate and clean a required string field."""

    if not isinstance(
        value,
        str,
    ):
        raise GeminiResponseValidationError(
            f"{field_name} must be a string."
        )

    value = value.strip()

    if not value:
        raise GeminiResponseValidationError(
            f"{field_name} cannot be empty."
        )

    return value


def _clean_string_list(
    value,
    field_name,
):
    """Validate a list containing non-empty strings."""

    if not isinstance(
        value,
        list,
    ):
        raise GeminiResponseValidationError(
            f"{field_name} must be a list."
        )

    cleaned = []

    for item in value:

        if not isinstance(
            item,
            str,
        ):
            raise GeminiResponseValidationError(
                f"Every item in {field_name} must be a string."
            )

        item = item.strip()

        if item:
            cleaned.append(
                item
            )

    return cleaned


def validate_gemini_response(
    response,
):
    """Validate and normalise Gemini structured output."""

    if not isinstance(
        response,
        dict,
    ):
        raise GeminiResponseValidationError(
            "Gemini response must be a dictionary."
        )

    model_used = _clean_string(
        response.get(
            "model_used"
        ),
        "model_used",
    )

    summary = _clean_string(
        response.get(
            "summary"
        ),
        "summary",
    )

    register_context = _clean_string(
        response.get(
            "register_context"
        ),
        "register_context",
    )

    audio_assessment = _clean_string(
        response.get(
            "audio_assessment"
        ),
        "audio_assessment",
    ).lower()

    if (
        audio_assessment
        not in ALLOWED_AUDIO_ASSESSMENTS
    ):
        raise GeminiResponseValidationError(
            "audio_assessment must be one of: "
            "consistent, inconsistent, uncertain."
        )

    audio_evidence = _clean_string(
        response.get(
            "audio_evidence"
        ),
        "audio_evidence",
    )

    evidence_highlights = _clean_string_list(
        response.get(
            "evidence_highlights"
        ),
        "evidence_highlights",
    )

    uncertainties = _clean_string_list(
        response.get(
            "uncertainties"
        ),
        "uncertainties",
    )

    recommended_status = _clean_string(
        response.get(
            "recommended_status"
        ),
        "recommended_status",
    ).lower()

    if (
        recommended_status
        not in ALLOWED_RECOMMENDED_STATUSES
    ):
        raise GeminiResponseValidationError(
            "recommended_status must be one of: "
            "correct, false_positive, review_required."
        )

    review_recommendation = _clean_string(
        response.get(
            "review_recommendation"
        ),
        "review_recommendation",
    )

    suggested_priority = _clean_string(
        response.get(
            "suggested_priority"
        ),
        "suggested_priority",
    ).lower()

    if (
        suggested_priority
        not in ALLOWED_PRIORITIES
    ):
        raise GeminiResponseValidationError(
            "suggested_priority must be one of: "
            "routine, review, priority_review."
        )

    notification_text = _clean_string(
        response.get(
            "notification_text"
        ),
        "notification_text",
    )

    validated = {
        "model_used":
            model_used,

        "summary":
            summary,

        "register_context":
            register_context,

        "audio_assessment":
            audio_assessment,

        "audio_evidence":
            audio_evidence,

        "evidence_highlights":
            evidence_highlights,

        "uncertainties":
            uncertainties,

        "recommended_status":
            recommended_status,

        "review_recommendation":
            review_recommendation,

        "suggested_priority":
            suggested_priority,

        "notification_text":
            notification_text,
    }

    return validated


def print_gemini_validation_summary(
    validated_response,
):
    """Print a concise summary of validated Gemini output."""

    print("=" * 70)
    print("GEMINI RESPONSE VALIDATION")
    print("=" * 70)

    print(
        "Status: VALID"
    )

    print(
        "Gemini model:",
        validated_response.get(
            "model_used"
        ),
    )

    print(
        "Audio assessment:",
        validated_response.get(
            "audio_assessment"
        ),
    )

    print(
        "Recommended BirdNET status:",
        validated_response.get(
            "recommended_status"
        ),
    )

    print(
        "Suggested priority:",
        validated_response.get(
            "suggested_priority"
        ),
    )

    print(
        "Review recommendation:",
        validated_response.get(
            "review_recommendation"
        ),
    )

    print(
        "Evidence highlights:",
        len(
            validated_response.get(
                "evidence_highlights",
                [],
            )
        ),
    )

    print(
        "Uncertainties:",
        len(
            validated_response.get(
                "uncertainties",
                [],
            )
        ),
    )

    print("=" * 70)
    