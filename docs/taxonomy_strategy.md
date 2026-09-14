# Taxonomy and Name-Reconciliation Strategy

## 1. Purpose

Species names may differ across BirdNET-GO, the supplied Cempedak and Nikoi fauna reference, BirdNET GeoModel, eBird, and other data sources.

These differences may arise from:

- scientific-name synonyms;
- historical names;
- taxonomic splits or lumps;
- spelling or formatting differences;
- different common names for the same taxon; or
- different taxonomy versions used by different systems.

Without reconciliation, a simple text match may incorrectly classify an already documented species as a potential new local record.

The purpose of this component is therefore to establish a consistent taxonomic identity before evidence from different sources is compared.

---

## 2. Core Principle

Raw names from every source should be preserved.

Taxonomic reconciliation creates additional standardised fields rather than overwriting the original data.

For example:

```text
scientific_name_raw
scientific_name_canonical
common_name_raw
common_name_canonical
taxon_id
mapping_type
mapping_status
taxonomy_version
```