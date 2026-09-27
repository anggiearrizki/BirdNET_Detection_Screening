# BirdNET-Go Detection Screening Framework

## 1. Background

This project develops a biodiversity detection screening workflow that connects
automated monitoring outputs with supporting evidence, AI-assisted contextual
interpretation, EarthRanger operational review, and human validation.

The initial implementation focuses on BirdNET-Go detections while keeping the
broader framework suitable for additional biodiversity monitoring sources.

## 2. Problem Definition

Automated species detections can contain false positives, uncertain detections,
or genuinely new local records.

A high model confidence score alone does not establish biological presence.
Likewise, absence from a local species list or external biodiversity database
does not establish biological absence.

The system therefore supports review rather than automatically confirming or
rejecting species records.

## 3. Project Objective

Build a reproducible workflow that:

1. receives candidate detections from monitoring systems
2. resolves the candidate taxonomically
3. checks the local Species Register
4. assembles relevant supporting evidence
5. produces a structured evidence packet
6. supports AI-assisted contextual interpretation
7. creates or enriches an EarthRanger review event
8. supports human validation
9. records the final outcome for future monitoring and evaluation

## 4. Framework Principles

- Taxonomy establishes identity.
- Data establish evidence.
- Rules establish reproducible signals.
- AI interprets context.
- Humans establish biological truth.

Additional safeguards:

- BirdNET confidence is a model output, not a probability of biological presence.
- Missing external records do not demonstrate biological absence.
- Automated evidence must not independently confirm or reject a new species record.
- Human review remains the final validation step.

## 5. Overall System Architecture

Current intended architecture:

```text
BirdNET-Go
    |
    | webhook
    v
Detection / Integration Layer
    |
    v
Taxonomy Resolution
    |
    v
Species Register Check
    |
    v
Evidence Construction
    |
    v
Structured Candidate Evidence Packet
    |
    v
Gemini Contextual Interpretation
    |
    v
Existing EarthRanger
"BirdNET new species" Event
    |
    v
Concise Notification
    |
    v
Human Validation
    |
    v
Outcome/Species Register Update
