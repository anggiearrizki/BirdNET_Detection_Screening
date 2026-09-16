"""Configuration for biodiversity taxonomy reconciliation.

Primary taxonomy:
Catalogue of Life Extended Release (COL XR)

Matching service:
GBIF Species Match API v2

The taxonomy source is kept separate from the original local-reference
workbook. Raw source names are never overwritten.
"""

GBIF_MATCH_API = "https://api.gbif.org/v2/species/match"

# Catalogue of Life Extended Release taxonomy in GBIF.
COL_XR_CHECKLIST_KEY = "7ddf754f-d193-4cc9-b351-99906754a03b"

TAXONOMY_SOURCE = "Catalogue of Life Extended Release"
TAXONOMY_VERSION = "2026-08-26 XR"
TAXONOMY_DOI = "10.48580/dgyy9"

REQUEST_TIMEOUT_SECONDS = 30