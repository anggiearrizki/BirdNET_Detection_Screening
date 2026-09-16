"""Validate evidence-source routing against the Phase 2 biodiversity reference.

Every resolved taxon group present in the reconciled biodiversity dataset
should receive an explicit supporting-evidence profile.

The generic fallback is useful for genuinely unknown future groups, but an
existing Phase 2 group should not silently fall through to it.
"""

# ============================
# DATA AND LIB PREPARATION
# ============================

from pathlib import Path
import pandas as pd
from evidence_source_router import get_evidence_profile

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

    combinations = (
        resolved[
            [
                "taxon_group",
                "environment",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "environment",
                "taxon_group",
            ]
        )
    )

    print("=" * 75)
    print("EVIDENCE ROUTER VALIDATION")
    print("=" * 75)

    fallback_groups = []

    for _, row in combinations.iterrows():

        taxon_group = row["taxon_group"]
        environment = row["environment"]

        profile = get_evidence_profile(
            taxon_group=taxon_group,
            environment=environment,
        )

        profile_name = profile["evidence_profile"]

        print(
            f"\n{taxon_group} | {environment}"
            f"\n  -> {profile_name}"
        )

        for evidence_type in (
            profile["supporting_evidence_types"]
        ):
            print(f"     - {evidence_type}")

        if profile_name == "general_biodiversity":
            fallback_groups.append(
                (
                    taxon_group,
                    environment,
                )
            )

    print("\n" + "=" * 75)

    print(
        "Unique Phase 2 taxon/environment combinations: "
        f"{len(combinations)}"
    )

    print(
        "Groups using generic fallback: "
        f"{len(fallback_groups)}"
    )

    if fallback_groups:

        print("\nREVIEW REQUIRED")

        for taxon_group, environment in fallback_groups:
            print(
                f"- {taxon_group} | {environment}"
            )

        print(
            "\nFAIL: Existing Phase 2 groups are still "
            "using the generic evidence profile."
        )

    else:

        print(
            "\nPASS: Every existing Phase 2 biodiversity "
            "group has an explicit evidence profile."
        )

    print("=" * 75)


if __name__ == "__main__":
    main()