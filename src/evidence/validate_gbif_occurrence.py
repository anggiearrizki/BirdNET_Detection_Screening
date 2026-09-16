"""Validate GBIF occurrence evidence across Phase 2 biodiversity groups.

This script selects one resolved taxon from every taxon-group/environment
combination represented in the reconciled Phase 2 biodiversity reference.

The purpose is to confirm that the GBIF occurrence adapter can accept
the range of taxonomic groups present in the project.

A successful request does not require occurrence records to exist.
Zero records are a valid evidence result and do not imply absence.
"""

from pathlib import Path
import pandas as pd
from gbif_occurrence import (
    get_gbif_occurrence_evidence,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASTER_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.csv"
)


def main():

    df = pd.read_csv(MASTER_PATH)

    resolved = df[
        df["taxonomy_reconciliation_status"]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq("resolved")
    ].copy()

    # ---------------------------------------------------------
    # Choose one real resolved taxon from every Phase 2
    # taxon-group/environment combination.
    # ---------------------------------------------------------

    examples = (
        resolved[
            [
                "taxon_group",
                "environment",
                "accepted_scientific_name",
                "accepted_rank",
            ]
        ]
        .dropna(
            subset=[
                "accepted_scientific_name",
                "accepted_rank",
            ]
        )
        .drop_duplicates()
        .sort_values(
            [
                "environment",
                "taxon_group",
                "accepted_scientific_name",
            ]
        )
        .groupby(
            [
                "taxon_group",
                "environment",
            ],
            as_index=False,
        )
        .first()
    )

    print("=" * 80)
    print("GBIF OCCURRENCE ADAPTER VALIDATION")
    print("=" * 80)

    request_errors = []

    for _, row in examples.iterrows():

        taxon_group = row["taxon_group"]
        environment = row["environment"]
        scientific_name = (
            row["accepted_scientific_name"]
        )
        taxon_rank = row["accepted_rank"]

        print(
            f"\n{taxon_group} | {environment}"
        )

        print(
            f"Taxon: {scientific_name}"
        )

        print(
            f"Rank: {taxon_rank}"
        )

        result = get_gbif_occurrence_evidence(
            scientific_name=scientific_name,
            taxon_rank=taxon_rank,
        )

        print(
            f"Status: "
            f"{result['evidence_status']}"
        )

        print(
            f"Occurrence count: "
            f"{result['occurrence_count']}"
        )

        if (
            result["evidence_status"]
            == "request_error"
        ):
            request_errors.append(
                {
                    "taxon_group":
                        taxon_group,

                    "environment":
                        environment,

                    "scientific_name":
                        scientific_name,
                }
            )

    print("\n" + "=" * 80)

    print(
        "Phase 2 group/environment combinations tested: "
        f"{len(examples)}"
    )

    print(
        "GBIF request errors: "
        f"{len(request_errors)}"
    )

    if request_errors:

        print("\nREVIEW REQUIRED")

        for error in request_errors:
            print(error)

        print(
            "\nFAIL: Some GBIF requests "
            "could not be completed."
        )

    else:

        print(
            "\nPASS: GBIF adapter successfully handled "
            "representative taxa across the Phase 2 "
            "biodiversity groups."
        )

    print("=" * 80)


if __name__ == "__main__":
    main()