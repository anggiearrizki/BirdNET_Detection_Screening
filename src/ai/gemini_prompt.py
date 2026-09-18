import json


SYSTEM_INSTRUCTION = """
You are an AI interpretation layer in a biodiversity monitoring workflow.

Your role is to interpret an automated species detection using only the
evidence supplied to you.

You may:
- summarise the detection and its context
- state whether the taxon is already present in the Species Register
- highlight supporting or conflicting evidence
- identify uncertainty or missing evidence
- recommend whether human review is warranted
- suggest an operational review priority
- generate a concise message suitable for an EarthRanger notification

You must not:
- independently confirm or reject a species
- invent evidence, observations, locations, sounds, or probabilities
- treat BirdNET confidence as the probability that a species is truly present
- assign unsupported likelihood percentages
- treat missing occurrence records as proof of biological absence
- identify the source of a sound unless the supplied evidence supports it
- describe a detection as definitively false solely because geographic
  or occurrence evidence is weak

Human validation remains the final authority for confirming a new species record.

The EarthRanger notification must remain concise.
Detailed evidence and audio should remain within the EarthRanger event.

Return valid JSON only.
""".strip()


OUTPUT_SCHEMA = {
    "summary": "Brief interpretation of the detection.",
    "register_context": (
        "Explain whether the taxon is already registered for the relevant property."
    ),
    "evidence_highlights": [
        "Important supporting or conflicting evidence."
    ],
    "uncertainties": [
        "Important limitation, missing evidence, or uncertainty."
    ],
    "review_recommendation": "Recommended human review action.",
    "suggested_priority": "routine | review | priority_review",
    "notification_text": (
        "A short interpretation suitable for an EarthRanger notification."
    ),
}


def build_gemini_prompt(candidate_packet):
    """
    Build a controlled prompt from the candidate evidence packet.

    Future workflow:
    BirdNET-Go webhook
        -> candidate evidence packet
        -> Gemini prompt
        -> Gemini interpretation
        -> existing EarthRanger event
    """

    task = """
Analyse the candidate detection represented by the evidence packet.

Focus on:
1. Species Register context.
2. Relevant supporting or conflicting evidence.
3. Important uncertainty or missing information.
4. Whether human review is warranted.
5. The appropriate operational review priority.
6. A concise EarthRanger notification.

The notification should contain only the key interpretation and recommended
action. Detailed evidence and audio will remain available within the
EarthRanger event.
""".strip()

    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"TASK\n{task}\n\n"
        f"REQUIRED OUTPUT SCHEMA\n"
        f"{json.dumps(OUTPUT_SCHEMA, indent=2)}\n\n"
        f"CANDIDATE EVIDENCE PACKET\n"
        f"{json.dumps(candidate_packet, indent=2, default=str)}"
    )


def print_prompt_preview(candidate_packet):
    """Print the generated Gemini prompt during prototyping."""

    prompt = build_gemini_prompt(candidate_packet)

    print("=" * 70)
    print("GEMINI PROMPT PREVIEW")
    print("=" * 70)
    print()
    print(prompt)
    print()
    print("=" * 70)