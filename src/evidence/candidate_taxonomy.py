"""Resolve taxonomy for a candidate Species Register record.

Candidate detections may arrive from BirdNET, EarthRanger, camera traps,
field surveys, manual observations, or other monitoring systems.

Before checking whether a taxon is already present in the Species Register,
the candidate scientific name should be reconciled against the same taxonomy
used to construct the Phase 2 baseline register.

This module therefore uses the same Catalogue of Life Extended Release
taxonomy configuration as Phase 2.

Important:
- taxonomy resolution establishes identity, not biological presence;
- non-exact or rank-conflicting matches require review;
- unresolved taxonomy should not proceed automatically to register matching.
"""

from pathlib import Path
import sys

import requests


# -------------------------------------------------------------------------
# Import the same taxonomy configuration used in Phase 2
# -------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from taxonomy.taxonomy_config import (  # noqa: E402
    GBIF_MATCH_API,
    COL_XR_CHECKLIST_KEY,
    TAXONOMY_SOURCE,
    TAXONOMY_VERSION,
    REQUEST_TIMEOUT_SECONDS,
)


def normalize_rank(value):
    """Normalize a taxonomic rank for comparison."""

    if value is None:
        return None

    text = str(value).strip().casefold()

    if not text:
        return None

    return text


def resolve_candidate_taxonomy(
    scientific_name,
    expected_rank=None,
):
    """Resolve one candidate scientific name against Phase 2 taxonomy."""

    if not scientific_name:
        return {
            "input_scientific_name":
                scientific_name,

            "expected_rank":
                expected_rank,

            "taxonomy_resolution_status":
                "unresolved",

            "recommended_action":
                "manual_taxonomy_review",

            "accepted_scientific_name":
                None,

            "accepted_taxon_id":
                None,

            "accepted_rank":
                None,

            "reason":
                "No scientific name was supplied.",
        }

    params = {
        "scientificName":
            scientific_name,

        "checklistKey":
            COL_XR_CHECKLIST_KEY,
    }

    if expected_rank:
        params["taxonRank"] = (
            normalize_rank(expected_rank)
        )

    # ---------------------------------------------------------------------
    # Request taxonomic match
    # ---------------------------------------------------------------------

    try:

        response = requests.get(
            GBIF_MATCH_API,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

    except requests.RequestException as exc:

        return {
            "input_scientific_name":
                scientific_name,

            "expected_rank":
                expected_rank,

            "taxonomy_resolution_status":
                "request_error",

            "recommended_action":
                "retry_taxonomy_resolution",

            "accepted_scientific_name":
                None,

            "accepted_taxon_id":
                None,

            "accepted_rank":
                None,

            "taxonomy_source":
                TAXONOMY_SOURCE,

            "taxonomy_version":
                TAXONOMY_VERSION,

            "error":
                str(exc),
        }

    data = response.json()

    usage = data.get("usage") or {}

    accepted_usage = (
        data.get("acceptedUsage")
        or usage
    )

    diagnostics = (
        data.get("diagnostics")
        or {}
    )

    # ---------------------------------------------------------------------
    # No usable taxonomic concept
    # ---------------------------------------------------------------------

    if not usage or not accepted_usage:

        return {
            "input_scientific_name":
                scientific_name,

            "expected_rank":
                expected_rank,

            "taxonomy_resolution_status":
                "unresolved",

            "recommended_action":
                "manual_taxonomy_review",

            "accepted_scientific_name":
                None,

            "accepted_taxon_id":
                None,

            "accepted_rank":
                None,

            "taxonomy_source":
                TAXONOMY_SOURCE,

            "taxonomy_version":
                TAXONOMY_VERSION,

            "match_type":
                diagnostics.get(
                    "matchType"
                ),

            "confidence":
                diagnostics.get(
                    "confidence"
                ),

            "reason":
                (
                    "No accepted taxonomic concept "
                    "was returned."
                ),
        }

    # ---------------------------------------------------------------------
    # Extract matched and accepted concepts
    # ---------------------------------------------------------------------

    matched_name = (
        usage.get("canonicalName")
        or usage.get("name")
    )

    matched_taxon_id = (
        usage.get("key")
    )

    matched_rank = (
        usage.get("rank")
    )

    accepted_name = (
        accepted_usage.get(
            "canonicalName"
        )
        or accepted_usage.get(
            "name"
        )
    )

    accepted_taxon_id = (
        accepted_usage.get("key")
    )

    accepted_rank = (
        accepted_usage.get("rank")
    )

    match_type = (
        diagnostics.get("matchType")
    )

    confidence = (
        diagnostics.get("confidence")
    )

    synonym = bool(
        data.get("synonym", False)
    )

    # ---------------------------------------------------------------------
    # Apply the same cautious reconciliation principle as Phase 2
    # ---------------------------------------------------------------------

    exact_match = (
        str(match_type)
        .strip()
        .upper()
        == "EXACT"
    )

    expected_rank_normalized = (
        normalize_rank(expected_rank)
    )

    accepted_rank_normalized = (
        normalize_rank(accepted_rank)
    )

    rank_matches = (
        expected_rank_normalized is None
        or
        expected_rank_normalized
        == accepted_rank_normalized
    )

    if exact_match and rank_matches:

        taxonomy_resolution_status = (
            "resolved"
        )

        recommended_action = (
            "continue_to_register_check"
        )

        if synonym:
            mapping_type = "synonym"
        else:
            mapping_type = "exact"

        reason = (
            "Exact taxonomy match at the "
            "expected taxonomic rank."
        )

    else:

        taxonomy_resolution_status = (
            "review"
        )

        recommended_action = (
            "manual_taxonomy_review"
        )

        mapping_type = (
            "candidate_match"
        )

        if not exact_match:

            reason = (
                "Taxonomic match was not exact."
            )

        elif not rank_matches:

            reason = (
                "Matched taxonomic rank differs "
                "from the expected rank."
            )

        else:

            reason = (
                "Taxonomic match requires review."
            )

    # ---------------------------------------------------------------------
    # Final taxonomy evidence object
    # ---------------------------------------------------------------------

    return {
        "input_scientific_name":
            scientific_name,

        "expected_rank":
            expected_rank,

        "taxonomy_resolution_status":
            taxonomy_resolution_status,

        "recommended_action":
            recommended_action,

        "mapping_type":
            mapping_type,

        "matched_scientific_name":
            matched_name,

        "matched_taxon_id":
            matched_taxon_id,

        "matched_rank":
            matched_rank,

        "accepted_scientific_name":
            accepted_name,

        "accepted_taxon_id":
            accepted_taxon_id,

        "accepted_rank":
            accepted_rank,

        "match_type":
            match_type,

        "confidence":
            confidence,

        "synonym":
            synonym,

        "taxonomy_source":
            TAXONOMY_SOURCE,

        "taxonomy_version":
            TAXONOMY_VERSION,

        "reason":
            reason,

        "interpretation_note":
            (
                "Taxonomy resolution establishes the "
                "candidate's taxonomic identity only. "
                "It does not confirm biological presence "
                "at Nikoi or Cempedak."
            ),
    }


def main():

    # Real candidate test case.
    result = resolve_candidate_taxonomy(
        scientific_name=(
            "Nycticorax nycticorax"
        ),
        expected_rank="species",
    )

    print("=" * 75)
    print("CANDIDATE TAXONOMY RESOLUTION")
    print("=" * 75)

    for key, value in result.items():
        print(
            f"{key}: {value}"
        )

    print("=" * 75)


if __name__ == "__main__":
    main()