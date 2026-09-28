# EarthRanger Event Mapping

## Purpose

This document maps the current BirdNET screening and Gemini interpretation workflow
to the existing EarthRanger event type:

`Bird Acoustic New Species`

The existing EarthRanger event type is retained as the starting schema.
The intention is to extend it only with fields needed for contextual interpretation
and review, rather than creating a separate event type.

## Existing EarthRanger Event

Event type:

`Bird Acoustic New Species`

Configuration observed in the EarthRanger Admin Portal:

- Event category: Wildlife Event
- Geometry type: Point
- Default state: Active
- Automatically resolve: No
- Event icon: bird_sound-event

## Existing Event Fields

### Species

- Common Name
- Scientific Name
- Confidence
- Confidence Percent

### BirdNET-Go

- BirdNET Detection ID
- BirdNET Location
- Island

### References

- BirdNET Detection URL
- Bird Image URL

### Detection Context

- Days Since First Seen
- Source System

### Audio

- Audio Filename
- Audio Content Type
- Audio Size Bytes
- Audio SHA-256

These existing fields should be preserved.

## Proposed Gemini Assessment Section

The current Gemini prototype returns a structured interpretation containing:

- AI Assessment
- Species Register Context
- Evidence Highlights
- Uncertainties
- Review Recommendation
- Suggested Priority

These fields are intended to support human review rather than establish
biological presence automatically.

### Proposed Mapping

| Gemini output | Proposed EarthRanger field |
|---|---|
| `summary` | AI Assessment |
| `register_context` | Species Register Context |
| `evidence_highlights` | Evidence Highlights |
| `uncertainties` | Uncertainties |
| `review_recommendation` | Review Recommendation |
| `suggested_priority` | Suggested Priority |
| `notification_text` | External notification text |

## Notification Design

The external notification should remain concise.

Example:

```text
Black-crowned Night Heron detected on Nikoi.

Candidate new register species.
Human acoustic review recommended.

Priority: Review