"""QUALITY ASSURANCE CHECKS FOR THE INGESTED BIODIVERSITY REFERENCE."""

# ========================================================
# DATA AND LIB PREPARATION
# ========================================================

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REFERENCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference.csv"
)


def main():

    df = pd.read_csv(REFERENCE_PATH)

    print("=" * 70)
    print("LOCAL BIODIVERSITY REFERENCE QA")
    print("=" * 70)

    print(f"\nTotal records: {len(df)}")

    print("\nRecords by island:")
    print(df["island"].value_counts(dropna=False))

    print("\nRecords by reference group:")
    print(df["reference_group"].value_counts(dropna=False))

    print("\nRecords by taxon group:")
    print(df["taxon_group"].value_counts(dropna=False))

    print("\nRecords by source sheet:")
    print(df["source_sheet"].value_counts().sort_index())

    # ========================================================
    # HANDLING MISSING NAMES
    # ========================================================

    missing_common = df["common_name_raw"].isna().sum()
    missing_scientific = df["scientific_name_raw"].isna().sum()
    missing_candidate = df["scientific_name_candidate"].isna().sum()

    print("\nMissing-name checks:")
    print(f"- Missing common name: {missing_common}")
    print(f"- Missing scientific name raw: {missing_scientific}")
    print(f"- Missing scientific candidate: {missing_candidate}")

    # ========================================================
    # POTENTIALLY UNCERTAIN SCIENTIFIC NAMES
    # ========================================================

    uncertainty_pattern = (
        r"\?|"
        r"\bsp\.\b|"
        r"\bspp\.\b|"
        r"\bprob\b|"
        r"\bpossible\b|"
        r"\bformerly\b|"
        r"\bcf\.\b"
    )

    uncertain = df[
        df["scientific_name_candidate"]
        .fillna("")
        .str.contains(
            uncertainty_pattern,
            case=False,
            regex=True,
        )
    ]

    print(
        f"\nPotentially uncertain scientific names: "
        f"{len(uncertain)}"
    )

    if not uncertain.empty:
        print(
            uncertain[
                [
                    "source_sheet",
                    "source_row",
                    "common_name_raw",
                    "scientific_name_candidate",
                ]
            ]
            .head(25)
            .to_string(index=False)
        )

    # ========================================================
    # DUPLICATE SOURCE RECORDS
    # ========================================================

    duplicates = df[
        df.duplicated(
            subset=[
                "source_sheet",
                "source_row",
            ],
            keep=False,
        )
    ]

    print(
        f"\nDuplicate source-sheet/source-row records: "
        f"{len(duplicates)}"
    )

    # ========================================================
    # MISSING PROVENANCE
    # ========================================================

    provenance_fields = [
        "source_file",
        "source_sheet",
        "source_row",
        "island",
        "reference_group",
        "taxon_group",
        "environment",
    ]

    print("\nMissing provenance values:")

    for column in provenance_fields:
        print(
            f"- {column}: "
            f"{df[column].isna().sum()}"
        )

    print("\nQA complete.")


if __name__ == "__main__":
    main()
    