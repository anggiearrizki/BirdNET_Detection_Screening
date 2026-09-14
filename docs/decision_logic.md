# Decision Logic

## 1. Purpose

This document explains how the screening framework decides whether a BirdNET-Go detection should be:

- **Routine**
- **Review**
- **Priority Review**
- **Data Issue**

The system does **not** determine whether a species is definitively present or absent.

Its main question is:

> **Given the available evidence, does this detection deserve human attention?**

Final biological validation remains with a human reviewer.

---

## 2. Decision Process

BirdNET-Go first produces a detection.

Example:

```text
Species: Red-naped Trogon
Confidence: 0.87
Station: South Station
Time: 03:21
```

```

The screening system then asks:

```text
1. Is the taxonomic identity clear?
        ↓
2. Is the taxon already listed in the local fauna reference?
        ↓
3. Has BirdNET-Go detected it before?
        ↓
4. Does the geographic and seasonal evidence support the detection?
        ↓
5. Is there supplementary occurrence evidence?
        ↓
6. Do the evidence sources agree or conflict?
        ↓
7. Does the detection warrant human review?
```

No single piece of evidence automatically confirms or rejects a detection.

---

## 3. Evidence Used

The framework combines several types of evidence.

| Evidence | Question it answers |
|---|---|
| BirdNET-Go detection | What species did the acoustic model predict? |
| Taxonomy | Are the different data sources referring to the same taxon? |
| Local fauna reference | Is the taxon currently listed for Cempedak or Nikoi? |
| Detection history | Has BirdNET-Go detected it before, and how consistently? |
| GeoModel | Is the taxon geographically and seasonally supported? |
| eBird | Are there supplementary nearby or recent occurrence records? |
| Previous human review | Has this taxon previously been confirmed or rejected locally? |

Each source provides evidence for a different part of the decision.

---

## 4. Step 1 — Resolve the Taxon

Before comparing databases, the system must establish which taxon is being evaluated.

Names may differ because of:

- synonyms;
- historical scientific names;
- spelling differences;
- different common names;
- taxonomic revisions; or
- different taxonomy versions.

The process is:

```text
BirdNET-Go species name
        ↓
Taxonomic reconciliation
        ↓
Resolved taxon / taxon ID
        ↓
Cross-source matching
```

Possible outcomes include:

```text
resolved
caution
unresolved
```

If the mapping is unresolved, the detection should be treated as a **Data Issue** rather than being incorrectly labelled as a new local species.

Detailed reconciliation rules are documented in `taxonomy_strategy.md`.

---

## 5. Step 2 — Check the Local Reference

Once the taxon has been resolved, it is compared with the supplied Cempedak and Nikoi fauna reference.

Possible outputs include:

```text
listed_both
listed_cempedak_only
listed_nikoi_only
not_listed
```

`not_listed` means:

> **The taxon is not listed in the current supplied local reference.**

It does not mean that the species is absent from the island.

A resolved taxon that is not listed may therefore generate:

```text
potential_new_local_record = true
```

This is a review flag, not confirmation of a new record.

---

## 6. Step 3 — Examine Detection History

The system then examines how BirdNET-Go has detected the taxon over time.

Potential features include:

```text
detection_count_24h
detection_count_7d
detection_count_30d

unique_hours
unique_days
unique_stations

first_detection
last_detection

mean_confidence
max_confidence
```

Raw detection count alone should not determine the strength of evidence.

For example:

```text
20 detections within one minute
```

may represent one recurring sound event.

Whereas:

```text
4 detections across 3 days and 2 stations
```

may provide stronger independent evidence.

Machine detections should also remain separate from human-confirmed records.

---

## 7. Step 4 — Consider BirdNET Confidence

BirdNET confidence is retained as supporting model evidence.

Example:

```text
birdnet_confidence = 0.87
```

It should not be interpreted as:

```text
87% probability that the species is biologically present
```

The framework therefore retains the raw confidence score and considers it together with the other evidence.

A universal confirmation threshold should not be assumed without validation.

---

## 8. Step 5 — Consider GeoModel Evidence

BirdNET GeoModel provides geographic and seasonal context.

The system should retain the raw value:

```text
geomodel_score = 0.014
```

and may also derive an operational category such as:

```text
very_low_support
low_support
supported
```

A low score should increase the need for investigation.

It should not automatically reject a detection.

Any threshold used to create these categories should be documented and later evaluated against human-reviewed data.

---

## 9. Step 6 — Consider eBird Evidence

eBird is used as supplementary occurrence evidence.

A query may use:

```text
resolved taxon
location
search radius
lookback period
```

Potential derived information includes:

```text
nearby_record_found
nearby_record_count
nearest_record_distance
most_recent_record_date
```

For example:

```text
nearby_record_found = false
```

means only:

> No matching observation was found within the configured search parameters.

It does not mean that the species is absent from the region.

---

## 10. Build the Structured Evidence Packet

The evidence from the previous steps is combined into one structured record.

Example:

```text
DETECTION
Species: Red-naped Trogon
Confidence: 0.87
Station: South Station

TAXONOMY
Status: Resolved

LOCAL REFERENCE
Cempedak: Not listed
Nikoi: Not listed

DETECTION HISTORY
Detections last 7 days: 1
Unique days: 1
Unique stations: 1
Previous human confirmation: 0

GEOGRAPHIC EVIDENCE
GeoModel support: Very low

EXTERNAL EVIDENCE
No nearby eBird records found within configured parameters
```

This evidence packet becomes the input to the screening process.

---

## 11. Deterministic Screening

Facts that can be calculated directly should be handled by reproducible rules rather than by AI.

Examples include:

```text
taxonomy_status == unresolved
local_reference_status == not_listed
unique_days == 1
previous_confirmed > 0
```

These rules create evidence flags.

For example:

```text
local_reference_status == not_listed
```

may create:

```text
potential_new_local_record = true
```

It should not create:

```text
species_confirmed_new = true
```

The deterministic layer therefore establishes facts and operational signals, not biological conclusions.

---

## 12. Relationship to the Initial Tier System

The original validation workflow used:

```text
Tier 1 = geographic concern / taxonomic uncertainty
Tier 2 = geographically supported + sparse detections
Tier 3 = geographically supported + repeated detections
```

These tiers remain useful as the initial rule-based baseline.

However, the operational framework will use richer evidence such as:

- unique detection days;
- unique stations;
- previous validated records;
- local-reference status;
- taxonomy status; and
- external occurrence evidence.

The original tiers are therefore treated as a starting point rather than permanent biological rules.

---

## 13. AI Contextual Assessment

AI is introduced only after the factual evidence has been collected.

Its role is to answer:

> **Given these pieces of evidence together, does the detection warrant further investigation, and why?**

AI is most useful when the evidence is mixed or conflicting.

For example:

```text
GeoModel support: Very low

BUT

Previous human confirmation: Yes
Repeated detections: Yes
Multiple stations: Yes
```

A simple rule may overreact to the low GeoModel score.

The AI layer can instead identify that the geographic evidence conflicts with strong local evidence and recommend appropriate review.

AI should interpret supplied evidence rather than independently inventing biological facts.

---

## 14. AI Guardrails

The AI should:

- use the supplied evidence;
- identify conflicting signals;
- identify missing information;
- state uncertainty clearly;
- recommend predefined review actions.

The AI should not:

- confirm or reject a species;
- invent taxonomy or range information;
- treat BirdNET confidence as probability of correctness;
- treat absence of eBird records as biological absence.

---

## 15. Review Categories

### Routine

No major anomaly currently requires additional investigation.

```text
Action:
Store normally
No additional alert
```

### Review

The detection contains uncertainty or evidence that warrants human investigation.

```text
Action:
Add to review queue
```

### Priority Review

The detection is unusual, potentially significant, or contains conflicting evidence.

```text
Action:
Add to review queue
Notify reviewers
```

Priority Review means:

> The detection deserves attention.

It does **not** mean:

> The species is probably correct.

### Data Issue

Reliable screening cannot continue because important information is unresolved.

Examples include:

```text
unresolved taxonomy
missing location
missing audio
ambiguous name mapping
```

```text
Action:
Resolve the data issue before further biological assessment
```

---

## 16. Recommended Actions

The system should use a controlled set of review actions.

Possible actions include:

```text
no_immediate_review
sample_audio_review
full_audio_review
seek_repeat_detection
seek_visual_confirmation
taxonomy_review
data_quality_review
```

The final action list can be refined with the project team.

---

## 17. Example Decision

Suppose the evidence is:

```text
Species:
Red-naped Trogon

Taxonomy:
Resolved

Local reference:
Not listed on Cempedak
Not listed on Nikoi

Detection history:
1 detection
1 day
1 station

GeoModel:
Very low support

eBird:
No nearby records found within configured parameters

Previous human confirmation:
None
```

The framework should **not** conclude:

> Definitive false positive.

Instead:

```text
Review Category:
Priority Review

Reasons:
- potential new local record
- sparse detection evidence
- very low geographic support

Recommended Action:
Manual acoustic review

Biological Status:
Unresolved
```

---

## 18. Threshold Policy

Some decisions will eventually require operational thresholds.

Examples include:

- BirdNET confidence;
- GeoModel support;
- detection-frequency criteria;
- eBird search radius;
- eBird lookback period.

Initial thresholds should be treated as **provisional operational values** unless supported by validation data.

Each threshold should eventually record:

```text
value
purpose
rationale
source
version
validation_status
```

The goal is to replace initial assumptions with locally validated decision rules over time.

---

## 19. Human Validation and Feedback

Human review remains the final biological validation step.

Possible outcomes are:

```text
confirmed
rejected
unresolved
```

The outcome should be stored alongside:

```text
original BirdNET detection
structured evidence
screening category
AI assessment
recommended action
```

These records can later be used to determine:

- which thresholds work well;
- which species frequently generate false positives;
- which evidence sources are most useful;
- which alerts were unnecessary; and
- whether AI improves screening beyond deterministic rules.

---

## 20. Summary

The decision process follows this sequence:

```text
Taxonomy establishes identity
        ↓
Local and external data establish context
        ↓
Rules create reproducible evidence signals
        ↓
AI interprets combined evidence and conflicts
        ↓
The system assigns review priority
        ↓
Humans perform final validation
```

The framework is not intended to automate biological confirmation.

Its purpose is to help reviewers focus their attention on the detections that are most useful to investigate.