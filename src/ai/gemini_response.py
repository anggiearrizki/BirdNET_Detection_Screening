"""Validate structured Gemini output before EarthRanger mapping.

Gemini is used as a contextual interpretation layer only.

Its response must match the expected structure before any values are
passed downstream to EarthRanger.
"""


ALLOWED_PRIORITIES = {
    "routine",
    "review",
    "priority_review",
}


REQUIRED_FIELDS = {
    "summary",
    "register_context",
    "evidence_highlights",
    "uncertainties",
    "review_recommendation",
    "suggested_priority",
    "notification_text",
}


class GeminiResponseValidationError(ValueError):
    """Raised when Gemini output does not match the expected structure."""


def _require_non_empty_string(
    data,
    field_name,
):
    """Require a field to contain a non-empty string."""

    value = data.get(
        field_name
    )

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
            f"{field_name} must not be empty."
        )

    return value


def _require_string_list(
    data,
    field_name,
):
    """Require a field to contain a list of non-empty strings."""

    value = data.get(
        field_name
    )

    if not isinstance(
        value,
        list,
    ):
        raise GeminiResponseValidationError(
            f"{field_name} must be a list."
        )

    cleaned_values = []

    for index, item in enumerate(
        value
    ):
        if not isinstance(
            item,
            str,
        ):
            raise GeminiResponseValidationError(
                f"{field_name}[{index}] must be a string."
            )

        item = item.strip()

        if not item:
            raise GeminiResponseValidationError(
                f"{field_name}[{index}] must not be empty."
            )

        cleaned_values.append(
            item
        )

    return cleaned_values


def validate_gemini_response(
    response,
):
    """
    Validate and normalise structured Gemini output.

    Returns a cleaned dictionary if valid.

    Raises GeminiResponseValidationError if the response is unsafe
    or structurally incompatible with the downstream workflow.
    """

    if not isinstance(
        response,
        dict,
    ):
        raise GeminiResponseValidationError(
            "Gemini response must be a dictionary."
        )

    missing_fields = (
        REQUIRED_FIELDS
        - set(
            response.keys()
        )
    )

    if missing_fields:
        raise GeminiResponseValidationError(
            "Gemini response is missing required fields: "
            + ", ".join(
                sorted(
                    missing_fields
                )
            )
        )

    summary = _require_non_empty_string(
        response,
        "summary",
    )

    register_context = _require_non_empty_string(
        response,
        "register_context",
    )

    evidence_highlights = _require_string_list(
        response,
        "evidence_highlights",
    )

    uncertainties = _require_string_list(
        response,
        "uncertainties",
    )

    review_recommendation = _require_non_empty_string(
        response,
        "review_recommendation",
    )

    suggested_priority = _require_non_empty_string(
        response,
        "suggested_priority",
    ).lower()

    notification_text = _require_non_empty_string(
        response,
        "notification_text",
    )

    if suggested_priority not in ALLOWED_PRIORITIES:
        raise GeminiResponseValidationError(
            "suggested_priority must be one of: "
            + ", ".join(
                sorted(
                    ALLOWED_PRIORITIES
                )
            )
        )

    validated_response = {
        "summary":
            summary,

        "register_context":
            register_context,

        "evidence_highlights":
            evidence_highlights,

        "uncertainties":
            uncertainties,

        "review_recommendation":
            review_recommendation,

        "suggested_priority":
            suggested_priority,

        "notification_text":
            notification_text,
    }

    return validated_response


def print_gemini_validation_summary(
    validated_response,
):
    """Print a concise validation result during prototyping."""

    print("=" * 70)
    print("GEMINI RESPONSE VALIDATION")
    print("=" * 70)

    print(
        "Status: VALID"
    )

    print(
        "Suggested priority:",
        validated_response[
            "suggested_priority"
        ],
    )

    print(
        "Review recommendation:",
        validated_response[
            "review_recommendation"
        ],
    )

    print(
        "Evidence highlights:",
        len(
            validated_response[
                "evidence_highlights"
            ]
        ),
    )

    print(
        "Uncertainties:",
        len(
            validated_response[
                "uncertainties"
            ]
        ),
    )

    print("=" * 70)
    