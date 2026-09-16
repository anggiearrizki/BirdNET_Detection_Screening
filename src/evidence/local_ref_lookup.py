"""CHECK IF A TAXON IS LISTED IN THE CURRECT LOCAL REFERENCE.
LOCAL REFERENCE INDEX IS UTILIZED.

Important:
- "not listed" means only that the taxon is not present in the
  current local reference;
- it does NOT mean the species is biologically absent;
- incoming names should ideally already be taxonomically reconciled.
"""

# ============================
# DATA AND LIB PREPARATION
# ============================

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INDEX_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_reference_index.csv"
)


def normalize_name(value):
    """Normalize a scientific name for safe comparison."""

    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    return " ".join(text.split()).casefold()


def lookup_local_reference(
    scientific_name,
    island,
):
    """Check whether a reconciled taxon is listed for an island."""

    index = pd.read_csv(INDEX_PATH)

    query_name = normalize_name(scientific_name)
    query_island = str(island).strip().casefold()

    index["_name_key"] = (
        index["accepted_scientific_name"]
        .apply(normalize_name)
    )

    index["_island_key"] = (
        index["island"]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    matches = index[
        (index["_name_key"] == query_name)
        & (index["_island_key"] == query_island)
    ].copy()

    if matches.empty:
        return {
            "scientific_name": scientific_name,
            "island": island,
            "local_reference_match": False,
            "local_reference_status":
                "not_listed_in_current_local_reference",
            "accepted_taxon_id": None,
            "reference_common_names": None,
            "reference_taxon_groups": None,
            "reference_source_sheets": None,
        }

    match = matches.iloc[0]

    return {
        "scientific_name":
            match["accepted_scientific_name"],

        "island":
            match["island"],

        "local_reference_match":
            True,

        "local_reference_status":
            "listed_in_current_local_reference",

        "accepted_taxon_id":
            match["accepted_taxon_id"],

        "reference_common_names":
            match["common_names"],

        "reference_taxon_groups":
            match["taxon_groups"],

        "reference_source_sheets":
            match["source_sheets"],
    }


def main():

    # Temporary test case.
    scientific_name = "Nycticorax nycticorax"
    island = "Nikoi"

    result = lookup_local_reference(
        scientific_name,
        island,
    )

    print("=" * 70)
    print("LOCAL REFERENCE LOOKUP")
    print("=" * 70)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()