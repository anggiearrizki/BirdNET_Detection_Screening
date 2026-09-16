"""Finalize the Phase 2 local biodiversity reference.

This script:
- merges taxonomy query preparation with COL XR match results;
- accepts only candidate-resolved taxonomy mappings;
- keeps review and unresolved cases clearly flagged;
- never overwrites the original source names;
- creates a reconciled biodiversity reference;
- creates a separate taxonomy review queue.
"""

from pathlib import Path

import pandas as pd

from taxonomy_config import TAXONOMY_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[2]

QUERY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "taxonomy_query_queue.csv"
)

MATCH_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "taxonomy_match_results.csv"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.csv"
)

OUTPUT_XLSX = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.xlsx"
)

REVIEW_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "taxonomy_review_queue.csv"
)


def is_true(value):
    """Safely interpret boolean-like values."""

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() == "true"


def first_nonempty(*values):
    """Return the first non-empty, non-NaN value."""

    for value in values:
        if pd.notna(value):
            text = str(value).strip()

            if text:
                return text

    return None


def derive_final_status(row):
    """Derive the final taxonomy reconciliation status."""

    # Record was not safe to send to the taxonomy matcher.
    if not is_true(row["query_eligible"]):

        if row["query_preparation_status"] == "manual_review":
            return "review"

        return "unresolved"

    api_status = row.get("reconciliation_status")

    if api_status == "candidate_resolved":
        return "resolved"

    if api_status == "review":
        return "review"

    if api_status == "request_error":
        return "request_error"

    return "unresolved"


def derive_mapping_type(row):
    """Describe how a resolved source name maps to accepted taxonomy."""

    if row["taxonomy_reconciliation_status"] != "resolved":
        return None

    if is_true(row.get("synonym")):
        return "synonym"

    return "exact"


def derive_mapping_notes(row):
    """Create a compact explanation of the reconciliation result."""

    status = row["taxonomy_reconciliation_status"]

    if status == "resolved":

        if is_true(row.get("synonym")):
            return (
                "Source name matched a recognised synonym; "
                "accepted taxonomy retained separately."
            )

        return (
            "Source identification matched accepted taxonomy "
            "at the expected rank."
        )

    if status == "review":
        return (
            first_nonempty(
                row.get("reconciliation_reason"),
                row.get("query_notes"),
            )
            or "Taxonomic mapping requires review."
        )

    if status == "request_error":
        return "Taxonomy service request failed."

    return (
        first_nonempty(
            row.get("reconciliation_reason"),
            row.get("query_notes"),
        )
        or "Taxonomic identification remains unresolved."
    )

def main():

    query_df = pd.read_csv(QUERY_PATH)
    match_df = pd.read_csv(MATCH_PATH)

    # Keep one API result per unique query + source rank.
    match_df = (
        match_df
        .drop_duplicates(
            subset=[
                "taxonomy_query_name",
                "source_identification_rank",
            ]
        )
    )

    # Rename API accepted fields so they are clearly proposals
    # until the reconciliation status has been evaluated.
    match_df = match_df.rename(
        columns={
            "accepted_taxon_id":
                "proposed_accepted_taxon_id",

            "accepted_scientific_name":
                "proposed_accepted_scientific_name",

            "accepted_rank":
                "proposed_accepted_rank",

            "taxonomy_source":
                "proposed_taxonomy_source",
        }
    )

    match_columns = [
        "taxonomy_query_name",
        "source_identification_rank",

        "match_type",
        "confidence",

        "matched_taxon_id",
        "matched_name",
        "matched_canonical_name",
        "matched_rank",
        "matched_status",

        "proposed_accepted_taxon_id",
        "proposed_accepted_scientific_name",
        "proposed_accepted_rank",

        "taxonomic_status",
        "synonym",

        "proposed_taxonomy_source",
        "match_issues",

        "reconciliation_status",
        "reconciliation_reason",
    ]

    match_df = match_df[match_columns]

    reference = query_df.merge(
        match_df,
        how="left",
        on=[
            "taxonomy_query_name",
            "source_identification_rank",
        ],
    )

    # --------------------------------------------------------------
    # Final reconciliation status
    # --------------------------------------------------------------

    reference["taxonomy_reconciliation_status"] = (
        reference.apply(
            derive_final_status,
            axis=1,
        )
    )

    # --------------------------------------------------------------
    # Only accepted mappings populate the final taxonomy fields.
    # --------------------------------------------------------------

    resolved = (
        reference["taxonomy_reconciliation_status"]
        == "resolved"
    )

    reference["taxonomy_match_status"] = (
        reference["taxonomy_reconciliation_status"]
    )

    reference["accepted_scientific_name"] = None
    reference["accepted_taxon_id"] = None
    reference["accepted_rank"] = None
    reference["taxonomy_source"] = None
    reference["taxonomy_version"] = None

    reference.loc[
        resolved,
        "accepted_scientific_name",
    ] = reference.loc[
        resolved,
        "proposed_accepted_scientific_name",
    ]

    reference.loc[
        resolved,
        "accepted_taxon_id",
    ] = reference.loc[
        resolved,
        "proposed_accepted_taxon_id",
    ]

    reference.loc[
        resolved,
        "accepted_rank",
    ] = reference.loc[
        resolved,
        "proposed_accepted_rank",
    ]

    reference.loc[
        resolved,
        "taxonomy_source",
    ] = reference.loc[
        resolved,
        "proposed_taxonomy_source",
    ]

    reference.loc[
        resolved,
        "taxonomy_version",
    ] = TAXONOMY_VERSION

    # --------------------------------------------------------------
    # Mapping metadata
    # --------------------------------------------------------------

    reference["mapping_type"] = reference.apply(
        derive_mapping_type,
        axis=1,
    )

    reference["mapping_notes"] = reference.apply(
        derive_mapping_notes,
        axis=1,
    )

    # --------------------------------------------------------------
    # Review queue
    # --------------------------------------------------------------

    review = reference[
        reference["taxonomy_reconciliation_status"]
        != "resolved"
    ].copy()

    review_columns = [
        "source_sheet",
        "source_row",
        "island",
        "reference_group",
        "taxon_group",

        "common_name_raw",
        "scientific_name_raw",
        "scientific_name_candidate",

        "taxonomy_query_name",
        "source_identification_rank",

        "query_preparation_status",
        "source_identification_uncertain",
        "query_notes",

        "match_type",
        "confidence",

        "matched_canonical_name",
        "matched_rank",

        "proposed_accepted_scientific_name",
        "proposed_accepted_rank",

        "taxonomy_reconciliation_status",
        "reconciliation_reason",
        "mapping_notes",
    ]

    review = review[review_columns]

    # --------------------------------------------------------------
    # Save outputs
    # --------------------------------------------------------------

    reference.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    reference.to_excel(
        OUTPUT_XLSX,
        index=False,
    )

    review.to_csv(
        REVIEW_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------

    print("=" * 70)
    print("PHASE 2 TAXONOMY RECONCILIATION COMPLETE")
    print("=" * 70)

    print(f"\nTotal biodiversity records: {len(reference)}")

    print("\nTaxonomy reconciliation status:")
    print(
        reference[
            "taxonomy_reconciliation_status"
        ]
        .value_counts(dropna=False)
    )

    print("\nResolved mapping types:")
    print(
        reference.loc[
            resolved,
            "mapping_type",
        ]
        .value_counts(dropna=False)
    )

    print(
        f"\nRecords requiring review/unresolved: "
        f"{len(review)}"
    )

    print("\nSaved reconciled reference:")
    print(OUTPUT_CSV)
    print(OUTPUT_XLSX)

    print("\nSaved taxonomy review queue:")
    print(REVIEW_PATH)


if __name__ == "__main__":
    main()