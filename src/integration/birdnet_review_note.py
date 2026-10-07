"""Publish only Gemini's species and audio explanation."""

import re


def build_birdnet_review_note(candidate, gemini_result):
    """Keep the existing function signature for caller compatibility."""
    explanation = gemini_result.get("audio_evidence")

    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Gemini audio explanation is missing.")

    return re.sub(r"\s+", " ", explanation).strip()


def print_birdnet_review_note(note):
    print(note)
    