"""LOCAL BIODIVERSITY REFERENCE INDEX.
This creates a compact lookup table from the Phase 2 reconciled reference.

The index:
- uses only taxonomically resolved records;
- creates one record per island + accepted taxon;
- preserves links back to all contributing source records.
"""

# ============================
# DATA AND LIB PREPARATION
# ============================

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REFERENCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_reference_index.csv"
)


def join_unique(values):
    """Join unique non-empty source values."""

    cleaned = []

    for value in values:
        if pd.notna(value):
            text = str(value).strip()

            if text and text not in cleaned:
                cleaned.append(text)

    return " | ".join(cleaned)


def main():

    df = pd.read_csv(REFERENCE_PATH)

    resolved = df[
        df["taxonomy_reconciliation_status"] == "resolved"
    ].copy()

    print("=" * 70)
    print("PHASE 3 LOCAL REFERENCE INDEX")
    print("=" * 70)

    print(f"\nResolved Phase 2 records: {len(resolved)}")

    index = (
        resolved
        .groupby(
            [
                "island",
                "accepted_taxon_id",
                "accepted_scientific_name",
                "accepted_rank",
            ],
            dropna=False,
        )
        .agg(
            common_names=(
                "common_name_raw",
                join_unique,
            ),
            reference_groups=(
                "reference_group",
                join_unique,
            ),
            taxon_groups=(
                "taxon_group",
                join_unique,
            ),
            environments=(
                "environment",
                join_unique,
            ),
            source_sheets=(
                "source_sheet",
                join_unique,
            ),
            source_rows=(
                "source_row",
                lambda x: " | ".join(
                    str(int(v))
                    for v in x
                    if pd.notna(v)
                ),
            ),
            source_record_count=(
                "source_row",
                "count",
            ),
        )
        .reset_index()
    )

    index["listed_in_current_local_reference"] = True

    index.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Unique island-taxon entries: {len(index)}")

    print("\nEntries by island:")
    print(
        index["island"]
        .value_counts(dropna=False)
    )

    duplicates = index.duplicated(
        subset=[
            "island",
            "accepted_taxon_id",
        ]
    ).sum()

    print(
        "\nDuplicate island + accepted taxon IDs "
        f"after indexing: {duplicates}"
    )

    print("\nSaved local reference index to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()