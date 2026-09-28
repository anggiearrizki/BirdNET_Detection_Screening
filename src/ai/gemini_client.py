"""Live Gemini API client for biodiversity detection interpretation.

This module sends a prepared candidate evidence prompt to Gemini and
requires the response to follow the structured schema expected by the
downstream validation and EarthRanger mapping layers.

If the primary Gemini model is temporarily unavailable, the client can
fall back to another stable Flash model.
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from google.genai import types


GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "Brief contextual interpretation of the candidate detection."
            ),
        },

        "register_context": {
            "type": "string",
            "description": (
                "Explain whether the taxon is already present in the "
                "relevant Species Register."
            ),
        },

        "evidence_highlights": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": (
                "Most relevant supporting or conflicting evidence."
            ),
        },

        "uncertainties": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": (
                "Important limitations, uncertainty, or missing evidence."
            ),
        },

        "review_recommendation": {
            "type": "string",
            "description": (
                "Recommended human review action."
            ),
        },

        "suggested_priority": {
            "type": "string",
            "enum": [
                "routine",
                "review",
                "priority_review",
            ],
            "description": (
                "Operational review priority."
            ),
        },

        "notification_text": {
            "type": "string",
            "description": (
                "Concise notification text suitable for EarthRanger."
            ),
        },
    },

    "required": [
        "summary",
        "register_context",
        "evidence_highlights",
        "uncertainties",
        "review_recommendation",
        "suggested_priority",
        "notification_text",
    ],

    "additionalProperties": False,
}


DEFAULT_MODEL_CHAIN = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
]


def _get_model_chain():
    """Build the ordered Gemini model fallback chain."""

    primary_model = os.getenv(
        "GEMINI_MODEL",
        DEFAULT_MODEL_CHAIN[0],
    )

    model_chain = [
        primary_model
    ]

    for model_name in DEFAULT_MODEL_CHAIN:
        if model_name not in model_chain:
            model_chain.append(
                model_name
            )

    return model_chain


def _parse_response(
    response,
):
    """Parse Gemini structured output into a Python dictionary."""

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    try:
        parsed_response = json.loads(
            response.text
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini response could not be parsed as JSON."
        ) from exc

    if not isinstance(
        parsed_response,
        dict,
    ):
        raise RuntimeError(
            "Gemini response must be a JSON object."
        )

    return parsed_response


def run_gemini_interpretation(
    prompt,
):
    """Send evidence to Gemini and return structured JSON.

    Stable Flash models are attempted in order if a model is
    temporarily unavailable.
    """

    load_dotenv()

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not available in the environment."
        )

    client = genai.Client(
        api_key=api_key
    )

    model_chain = _get_model_chain()

    last_error = None

    for model_name in model_chain:

        print(
            f"Trying Gemini model: {model_name}"
        )

        try:
            response = client.models.generate_content(
                model=model_name,

                contents=prompt,

                config=types.GenerateContentConfig(
                    response_mime_type="application/json",

                    response_json_schema=(
                        GEMINI_RESPONSE_SCHEMA
                    ),

                    automatic_function_calling=(
                        types.AutomaticFunctionCallingConfig(
                            disable=True
                        )
                    ),
                ),
            )

            parsed_response = _parse_response(
                response
            )

            print(
                f"Gemini model succeeded: {model_name}"
            )

            return parsed_response

        except errors.ServerError as exc:

            last_error = exc

            error_code = getattr(
                exc,
                "code",
                None,
            )

            if error_code == 503:
                print(
                    f"{model_name} unavailable. "
                    "Trying next stable model..."
                )
                continue

            raise

    raise RuntimeError(
        "All configured Gemini models were unavailable."
    ) from last_error