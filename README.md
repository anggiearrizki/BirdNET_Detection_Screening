# BirdNET Detection Screening

An evidence-based, human-in-the-loop framework for screening and prioritising unusual BirdNET detections using taxonomic reconciliation, local species references, detection history, spatiotemporal evidence, and AI-assisted contextual assessment.

## Background

BirdNET provides automated acoustic species detections, but individual detections may include false positives, particularly when evaluating unusual or potentially new local species records.

A BirdNET confidence score alone is not sufficient to determine whether a detection is biologically valid or whether it warrants further investigation.

This project develops a reproducible screening framework that combines multiple sources of evidence before detections are prioritised for human validation.

The initial work builds on a validation workflow developed for BirdNET detections from Cempedak Island and extends it toward an operational screening layer that could sit between BirdNET-Go and EarthRanger.

## Objective

The project aims to develop a screening pipeline that can:

- identify detections that may warrant further investigation;
- distinguish potential new local records from already documented species;
- minimise false "new species" flags caused by naming or taxonomy mismatches;
- combine geographic, temporal, historical, and external occurrence evidence;
- use AI to interpret combined evidence without treating AI as the final species validator;
- route relevant detections for human acoustic review; and
- retain validation outcomes for future evaluation and calibration.

## Core Principle

> **Taxonomy establishes identity.**  
> **Data establish evidence.**  
> **Rules establish reproducible signals.**  
> **AI interprets context.**  
> **Humans establish biological truth.**

## Proposed Workflow

```text
BirdNET-Go Detection
        ↓
Taxonomic Reconciliation
        ↓
Local Species Reference Check
        ↓
Detection History Analysis
        ↓
Spatiotemporal Evidence
   ├── BirdNET GeoModel
   └── eBird supplementary evidence
        ↓
Structured Evidence Packet
        ↓
Deterministic Screening
        ↓
AI Contextual Assessment
        ↓
Review Priority
        ↓
EarthRanger / Notification Routing
        ↓
Human Acoustic Validation
        ↓
Outcome Storage & Calibration