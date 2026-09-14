# Data Sources

## Purpose

This document defines the data sources used in the BirdNET-GO detection screening framework, the role of each source, the fields required from each source, and the limitations that must be considered before using the data for screening or validation.

A key principle of the framework is that different data sources answer different questions. No single source is treated as sufficient evidence to confirm or reject a species detection.

---

## 1. BirdNET-Go Detection Data

### Role

BirdNET-Go provides the primary acoustic detection event that enters the screening pipeline.

### Intended Fields

- detection ID
- common name
- scientific name
- confidence score
- timestamp
- recording station / source
- latitude and longitude, where available
- audio or recording reference
- BirdNET model version, where available

### Use in the Framework

BirdNET detection data are used to establish:

- which species BirdNET predicted;
- when and where the detection occurred;
- the acoustic-model confidence score; and
- the recording that will ultimately be reviewed by a human.

### Important Limitation

BirdNET confidence is treated as supporting model evidence rather than the probability that the species identification is biologically correct.

Raw BirdNET output should be preserved without modification.

---

## 2. Cempedak and Nikoi Fauna Species List

### Role

The fauna spreadsheet supplied by the project team is used as the current local species reference for Cempedak and Nikoi.

### Intended Fields

- island
- common name as recorded
- scientific name as recorded
- associated notes, where available

### Use in the Framework

After taxonomic reconciliation, the local reference is used to derive:

- whether a taxon is currently listed for Cempedak;
- whether a taxon is currently listed for Nikoi; and
- whether a detection may represent a potential new local record requiring further investigation.

Example derived fields:

```text
listed_cempedak
listed_nikoi
local_reference_status
```