"""Live Gemini API client for biodiversity detection interpretation.

This module sends a prepared candidate evidence prompt to Gemini and
requires the response to follow the structured schema expected by the
downstream validation and EarthRanger mapping layers.

The client supports:
- BirdNET audio input
- Structured JSON responses
- Model fallback for normal workflow use
- Fixed-model benchmarking
- Retry handling for temporary Gemini 503 capacity errors
- Audit tracking of the Gemini model that produced each result
"""

import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from google.genai import types


# ---------------------------------------------------------------------
# Structured Gemini response schema
# ---------------------------------------------------------------------

GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "Brief conservative interpretation of the BirdNET detection."
            ),
        },

        "register_context": {
            "type": "string",
            "description": (
                "Explain whether the taxon is already present in the "
                "relevant Species Register."
            ),
        },

        "audio_assessment": {
            "type": "string",
            "enum": [
                "consistent",
                "inconsistent",
                "uncertain",
            ],
            "description": (
                "Assessment of whether the supplied audio appears acoustically "
                "consistent with the proposed BirdNET species identification. "
                "This is supporting evidence only, not biological confirmation."
            ),
        },

        "audio_evidence": {
            "type": "string",
            "description": (
                "Complete species-specific explanation of the attached "
                "recording for BirdNET Notes. One coherent paragraph, "
                "normally 100-180 words where supported. Describe audible "
                "characteristics, their relationship to the proposed "
                "species, relevant recording conditions, and acoustic "
                "uncertainty. No register context, technical metadata, "
                "workflow commentary, headings, or generic disclaimers. "
                "Do not invent sounds or measurements."
            ),
        },

        "evidence_highlights": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": (
                "Evidence actually present in the supplied packet. "
                "Do not treat pending or unrequested sources as evidence."
            ),
        },

        "uncertainties": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": (
                "Important limitations, missing evidence, or uncertainty."
            ),
        },

        "recommended_status": {
            "type": "string",
            "enum": [
                "correct",
                "false_positive",
                "review_required",
            ],
            "description": (
                "Recommended BirdNET review outcome. This is a screening "
                "recommendation and is not yet an automatic final verification."
            ),
        },

        "review_recommendation": {
            "type": "string",
            "description": (
                "Recommended next human or automated review action."
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
                "Concise notification suitable for downstream systems."
            ),
        },
    },

    "required": [
        "summary",
        "register_context",
        "audio_assessment",
        "audio_evidence",
        "evidence_highlights",
        "uncertainties",
        "recommended_status",
        "review_recommendation",
        "suggested_priority",
        "notification_text",
    ],

    "additionalProperties": False,
}


# ---------------------------------------------------------------------
# Default Gemini model chain
# ---------------------------------------------------------------------

DEFAULT_MODEL_CHAIN = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
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
    audio_path=None,
    audio_mime_type=None,
    model_override=None,
    allow_fallback=True,
    max_retries_per_model=3,
):
    """Send evidence to Gemini and return structured JSON.

    Parameters
    ----------
    prompt:
        Prepared biodiversity evidence prompt.

    audio_path:
        Optional BirdNET audio file to attach to the Gemini request.

    audio_mime_type:
        MIME type for the supplied audio file.

    model_override:
        Optional Gemini model to try first.

    allow_fallback:
        If True, another configured model may be attempted after all
        retries for the current model fail.

        If False, only the selected model is used. This is important
        for controlled historical benchmarking.

    max_retries_per_model:
        Maximum number of attempts for each model when temporary
        503 capacity errors occur.

    Returns
    -------
    dict
        Structured Gemini response plus a locally added `model_used`
        field for auditability.
    """

    # -----------------------------------------------------------------
    # Environment and API client
    # -----------------------------------------------------------------

    load_dotenv()

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not available in the environment."
        )

    if max_retries_per_model < 1:
        raise ValueError(
            "max_retries_per_model must be at least 1."
        )

    client = genai.Client(
        api_key=api_key
    )

    # -----------------------------------------------------------------
    # Determine which models are allowed for this run
    # -----------------------------------------------------------------

    if model_override:

        if allow_fallback:

            model_chain = [
                model_override
            ]

            for model_name in _get_model_chain():

                if model_name not in model_chain:
                    model_chain.append(
                        model_name
                    )

        else:

            model_chain = [
                model_override
            ]

    else:

        model_chain = _get_model_chain()

    # -----------------------------------------------------------------
    # Build Gemini request contents
    # -----------------------------------------------------------------

    contents = [
        prompt
    ]

    if audio_path:

        if not audio_mime_type:
            raise RuntimeError(
                "audio_mime_type is required when audio_path is provided."
            )

        with open(
            audio_path,
            "rb",
        ) as audio_file:
            audio_bytes = audio_file.read()

        contents.append(
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type=audio_mime_type,
            )
        )

        print(
            f"Audio attached to Gemini request: {audio_path}"
        )

    # -----------------------------------------------------------------
    # Run Gemini
    # -----------------------------------------------------------------

    last_error = None

    for model_index, model_name in enumerate(
        model_chain
    ):

        for attempt in range(
            1,
            max_retries_per_model + 1,
        ):

            print(
                f"Trying Gemini model: {model_name} "
                f"(attempt {attempt}/{max_retries_per_model})"
            )

            try:

                response = client.models.generate_content(
                    model=model_name,

                    contents=contents,

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

                # -----------------------------------------------------
                # Add model audit information locally.
                #
                # This is deliberately not part of the Gemini response
                # schema because Gemini should not decide which model
                # produced its own output.
                # -----------------------------------------------------

                parsed_response[
                    "model_used"
                ] = model_name

                return parsed_response

            except errors.ServerError as exc:

                last_error = exc

                error_code = getattr(
                    exc,
                    "code",
                    None,
                )

                # -----------------------------------------------------
                # Temporary capacity error
                # -----------------------------------------------------

                if error_code == 503:

                    if attempt < max_retries_per_model:

                        wait_seconds = (
                            2 ** attempt
                        )

                        print(
                            f"{model_name} temporarily unavailable "
                            f"(503). Retrying the same model in "
                            f"{wait_seconds} seconds..."
                        )

                        time.sleep(
                            wait_seconds
                        )

                        continue

                    # -------------------------------------------------
                    # All retries for this model have been exhausted
                    # -------------------------------------------------

                    has_next_model = (
                        model_index
                        <
                        len(model_chain) - 1
                    )

                    if (
                        allow_fallback
                        and has_next_model
                    ):

                        print(
                            f"{model_name} remained unavailable "
                            f"after {max_retries_per_model} attempts. "
                            "Moving to the next configured model..."
                        )

                        break

                    raise RuntimeError(
                        f"{model_name} remained unavailable "
                        f"after {max_retries_per_model} attempts."
                    ) from exc

                # -----------------------------------------------------
                # Non-503 server errors should not be hidden
                # -----------------------------------------------------

                raise

    raise RuntimeError(
        "All configured Gemini models were unavailable."
    ) from last_error