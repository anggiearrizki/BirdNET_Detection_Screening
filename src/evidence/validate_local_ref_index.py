"""VALIDATE THE BIODIVERSITY-WIDE LOCAL REFERENCE INDEX.

Checks that the Phase 3 local-reference index represents all resolved
Phase 2 biodiversity records across fauna, flora, and algae.

The index should contain one row per:
    island + accepted taxon

Records still under taxonomy review or unresolved are intentionally
excluded from the automated lookup index.
"""

# ============================
# DATA AND LIB PREPARATION
# ============================

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASTER_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.csv"
)

INDEX_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_reference_index.csv"
)


def main():

    master = pd.read_csv(MASTER_PATH)
    index = pd.read_csv(INDEX_PATH)

    print("=" * 70)
    print("LOCAL REFERENCE INDEX VALIDATION")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Use only taxonomically resolved Phase 2 records
    # ---------------------------------------------------------

    resolved = master[
        master["taxonomy_reconciliation_status"]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq("resolved")
    ].copy()

    print(f"\nResolved Phase 2 records: {len(resolved)}")
    print(f"Indexed island-taxon entries: {len(index)}")

    # ---------------------------------------------------------
    # 2. Build expected unique island + taxon combinations
    # ---------------------------------------------------------

    expected = (
        resolved[
            [
                "island",
                "accepted_taxon_id",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    print(
        "Expected unique island-taxon entries: "
        f"{len(expected)}"
    )

    # ---------------------------------------------------------
    # 3. Check duplicate index keys
    # ---------------------------------------------------------

    duplicate_keys = index.duplicated(
        subset=[
            "island",
            "accepted_taxon_id",
        ],
        keep=False,
    )

    print(
        "Duplicate island + accepted_taxon_id entries: "
        f"{duplicate_keys.sum()}"
    )

    # ---------------------------------------------------------
    # 4. Compare expected records with index
    # ---------------------------------------------------------

    comparison = expected.merge(
        index[
            [
                "island",
                "accepted_taxon_id",
            ]
        ],
        on=[
            "island",
            "accepted_taxon_id",
        ],
        how="outer",
        indicator=True,
    )

    missing_from_index = comparison[
        comparison["_merge"] == "left_only"
    ]

    unexpected_in_index = comparison[
        comparison["_merge"] == "right_only"
    ]

    print(
        "Resolved taxa missing from index: "
        f"{len(missing_from_index)}"
    )

    print(
        "Unexpected taxa in index: "
        f"{len(unexpected_in_index)}"
    )

    # ---------------------------------------------------------
    # 5. Biodiversity coverage
    # ---------------------------------------------------------

    print("\nREFERENCE GROUP COVERAGE")
    print("-" * 70)

    print(
        resolved["reference_group"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nTAXON GROUP COVERAGE")
    print("-" * 70)

    print(
        resolved["taxon_group"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nENVIRONMENT COVERAGE")
    print("-" * 70)

    print(
        resolved["environment"]
        .value_counts(dropna=False)
        .to_string()
    )

    # ---------------------------------------------------------
    # 6. Island coverage
    # ---------------------------------------------------------

    print("\nISLAND COVERAGE")
    print("-" * 70)

    print(
        index["island"]
        .value_counts(dropna=False)
        .to_string()
    )

    # ---------------------------------------------------------
    # 7. Final validation result
    # ---------------------------------------------------------

    passed = (
        duplicate_keys.sum() == 0
        and len(missing_from_index) == 0
        and len(unexpected_in_index) == 0
        and len(expected) == len(index)
    )

    print("\n" + "=" * 70)

    if passed:
        print(
            "PASS: local reference index covers all "
            "resolved biodiversity taxa."
        )
    else:
        print(
            "FAIL: local reference index needs review."
        )

    print("=" * 70)


if __name__ == "__main__":
    main()