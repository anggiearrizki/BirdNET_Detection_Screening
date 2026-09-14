# Validation Plan

## 1. Purpose

This document defines how the BirdNET Detection Screening framework will be evaluated and improved using human-reviewed detections.

The framework needs to answer two different questions:

1. **Was the BirdNET species identification correct?**
2. **Was the system correct to send the detection for human review?**

These questions must be evaluated separately.

For example:

```text
Screening decision: Priority Review
Human species outcome: Rejected
Review warranted: Yes
```

This can still represent a successful screening decision because the system correctly identified an unusual false positive that deserved investigation.

---

## 2. Validation Objectives

The evaluation should determine whether the framework can:

- identify detections that deserve human investigation;
- avoid overlooking unusual or potentially important records;
- reduce unnecessary manual review;
- reduce false "new local species" flags caused by naming mismatches;
- provide understandable reasons for escalation;
- improve on BirdNET confidence alone; and
- determine whether AI adds useful information beyond deterministic rules.

---

## 3. Human Reference Outcome

Human acoustic review remains the reference for final species validation.

Each reviewed detection should receive one of:

```text
confirmed
rejected
unresolved
```

A second operational label should also be recorded:

```text
review_warranted = yes / no
```

This separates **species correctness** from **triage usefulness**.

---

## 4. Validation Dataset

Each reviewed case should preserve the evidence available when the screening decision was made.

A validation record may contain:

```text
detection_id

BirdNET species
BirdNET confidence

taxonomy status
local reference status

detection history
GeoModel evidence
eBird evidence

deterministic screening result
AI assessment
review category

human species outcome
review_warranted
review date
review notes
```

This creates the dataset used to evaluate and later calibrate the system.

---

## 5. Human Review Process

Where possible, human review should follow a consistent process.

Potential evidence includes:

- original recording;
- spectrogram;
- repeated recordings;
- reference vocalisations;
- visual evidence;
- local context; and
- expert opinion where required.

The human reviewer records:

```text
confirmed
rejected
unresolved
```

along with relevant notes.

---

## 6. Systems to Compare

The proposed framework should be compared against simpler approaches.

### Baseline A — BirdNET Confidence Only

Uses BirdNET confidence as the main screening signal.

Purpose:

> Establish how useful BirdNET confidence is by itself.

### Baseline B — Deterministic Evidence Screening

Uses structured evidence such as:

- taxonomy;
- local-reference status;
- detection history;
- GeoModel support; and
- eBird evidence.

Purpose:

> Measure how well transparent rule-based screening works without AI.

### System C — Deterministic Evidence + AI Assessment

Uses the same structured evidence as Baseline B, with AI used to interpret evidence conflicts and recommend review priority.

Purpose:

> Determine whether AI provides measurable value beyond deterministic screening.

---

## 7. Triage Evaluation

The main operational question is:

> **Did the system correctly determine whether a detection deserved human review?**

This can be represented as:

```text
                          Human judgement
                       Review      No review

System: Review            TP          FP
System: No review         FN          TN
```

Where:

```text
TP = correctly escalated
FP = unnecessary escalation
FN = important case missed
TN = correctly treated as routine
```

---

## 8. Key Metrics

### Recall

Of all cases that warranted review:

> How many did the system successfully identify?

High recall is important when missing an unusual detection would be costly.

### Precision

Of all cases escalated:

> How many actually warranted review?

Higher precision reduces unnecessary reviewer workload.

### False-Negative Rate

How often did the system fail to escalate a case that should have been reviewed?

### False-Positive Rate

How often did the system unnecessarily escalate a routine case?

### Review Reduction

Compare:

```text
total detections
vs
detections sent for review
```

This measures how much manual screening workload may be reduced.

---

## 9. BirdNET Confidence Evaluation

Human-reviewed records can be used to examine:

```text
BirdNET confidence
vs
confirmed / rejected outcome
```

The goal is not to assume one universal threshold.

Instead, the project can investigate whether different species require different operational thresholds.

Until sufficient validation data exist, BirdNET confidence remains a continuous supporting variable.

---

## 10. Detection-History Evaluation

The initial validation workflow used:

```text
1–2 detections = sparse
3+ detections = repeated
```

This was useful as an initial operational rule.

The validation dataset should later test whether other variables are more informative, including:

```text
unique hours
unique days
unique stations
detection span
raw detection count
```

This may allow the original rule to be refined or replaced.

---

## 11. GeoModel Evaluation

GeoModel scores should be compared with human-reviewed outcomes.

Questions include:

- Do confirmed records usually receive stronger GeoModel support?
- How often are confirmed local species assigned low support?
- Does GeoModel add useful information beyond local history?
- Do proposed GeoModel thresholds cause important cases to be missed?

This analysis may support local calibration.

---

## 12. eBird Evaluation

The value of eBird evidence should also be tested rather than assumed.

Questions include:

- Does nearby eBird evidence differ between confirmed and rejected detections?
- Does eBird provide information beyond GeoModel?
- How sensitive are results to search radius?
- How sensitive are results to the temporal lookback period?

---

## 13. Sensitivity Analysis

Parameters that are not biologically fixed should be tested across reasonable alternatives.

Examples include:

```text
eBird radius
eBird lookback period
GeoModel operational threshold
notification threshold
detection-frequency rule
```

For example, eBird could be compared across several candidate settings:

```text
Radius:
10 km
25 km
50 km

Lookback:
7 days
14 days
30 days
```

The purpose is to understand whether screening conclusions change substantially when operational assumptions change.

---

## 14. AI Evaluation

AI should not be assumed to improve the framework simply because it is available.

The evaluation should ask:

- Does AI improve recall?
- Does AI improve precision?
- Does AI reduce unnecessary alerts?
- Does AI correctly identify conflicting evidence?
- Does AI recommend appropriate next actions?
- Does AI introduce unsupported biological claims?
- Does it produce consistent assessments from the same structured evidence?

System C should therefore be compared directly with deterministic Baseline B.

---

## 15. AI Error Analysis

Where AI produces an unsuitable recommendation, the failure should be classified.

Possible categories include:

```text
unsupported ecological claim
incorrect interpretation of missing evidence
over-reliance on BirdNET confidence
over-reliance on GeoModel
failure to recognise conflicting evidence
incorrect review priority
unsupported species conclusion
```

These errors can guide improvements to prompts, guardrails, and system design.

---

## 16. Taxonomy Evaluation

The taxonomic reconciliation layer should also be evaluated.

Potential measures include:

```text
exact match rate
synonym resolution rate
unresolved mapping rate
manual review rate
incorrect mapping rate
```

An additional useful measure is:

> How many potential false "new local species" flags were prevented because two different names were correctly mapped to the same taxon?

---

## 17. Pilot Phase

The first implementation should be treated as a pilot.

The pilot should focus on:

- confirming that the pipeline operates correctly;
- identifying missing or unreliable data;
- testing the usefulness of each evidence source;
- identifying common failure modes;
- understanding reviewer workload; and
- collecting enough validated examples for future calibration.

Initial results should therefore be interpreted cautiously if the validation sample is small.

---

## 18. Prospective Evaluation

Once the prototype is stable, evaluation should move to new detections that have not yet been reviewed.

The process would be:

```text
New BirdNET detection
        ↓
Screening recommendation generated
        ↓
Recommendation stored
        ↓
Human review
        ↓
Compare recommendation with outcome
```

This provides a stronger evaluation than testing only on detections already known to be unusual.

---

## 19. Versioning

Evaluation results should always be linked to the specific system configuration that produced them.

Relevant information may include:

```text
screening_rule_version
taxonomy_version
local_reference_version
GeoModel_version
AI_model_version
AI_prompt_version
assessment_date
```

This allows performance changes to be traced when the framework evolves.

---

## 20. Success Criteria

Exact numerical targets should not be fixed before baseline performance and reviewer requirements are understood.

Initial success should instead mean that the framework:

- reliably surfaces unusual detections;
- avoids excessive unnecessary alerts;
- preserves important evidence and provenance;
- reduces avoidable name-mismatch errors;
- provides understandable reasons for review;
- supports rather than replaces human validation; and
- generates enough labelled data for future calibration.

---

## 21. Overall Evaluation Goal

The objective is not to maximise AI accuracy.

The objective is to determine whether the complete screening framework:

> **directs human attention toward the right detections while remaining transparent, reproducible, and scientifically cautious.**