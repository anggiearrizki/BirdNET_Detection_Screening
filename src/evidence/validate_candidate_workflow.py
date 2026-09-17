"""Validate both branches of the Species Register candidate workflow.

The workflow must distinguish between:

1. an existing registered taxon:
   no new-species evidence workflow is required;

2. a candidate taxon not currently in the register:
   supporting evidence and review are required.
"""

from pathlib import Path

import pandas as pd

from candidate_evidence_packet import (
    build_candidate_evidence_packet,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INDEX_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_reference_index.csv"
)


def main():

    index = pd.read_csv(INDEX_PATH)

    # ---------------------------------------------------------
    # EXISTING REGISTER TAXON
    #
    # Select one real resolved taxon directly from the
    # Phase 2-derived Species Register index.
    # ---------------------------------------------------------

    existing = index.iloc[0]

    existing_scientific_name = (
        existing["accepted_scientific_name"]
    )

    existing_rank = (
        existing["accepted_rank"]
    )

    existing_island = (
        existing["island"]
    )

    print("=" * 75)
    print("TEST 1: EXISTING REGISTER TAXON")
    print("=" * 75)

    existing_packet = (
        build_candidate_evidence_packet(
            scientific_name=(
                existing_scientific_name
            ),
            expected_rank=(
                existing_rank
            ),
            island=(
                existing_island
            ),
            taxon_group=None,
            environment=None,
            candidate_source="workflow_test",
        )
    )

    existing_register = (
        existing_packet[
            "register_check"
        ]
    )

    print(
        "Scientific name: "
        f"{existing_scientific_name}"
    )

    print(
        "Island: "
        f"{existing_island}"
    )

    print(
        "Already registered: "
        f"{existing_register['already_in_register']}"
    )

    print(
        "Candidate status: "
        f"{existing_register['candidate_status']}"
    )

    print(
        "Proposed action: "
        f"{existing_register['proposed_register_action']}"
    )

    print(
        "Evidence collection status: "
        f"{existing_packet['evidence_collection_status']}"
    )

    # ---------------------------------------------------------
    # CANDIDATE NEW TAXON
    #
    # Real Night Heron example.
    # ---------------------------------------------------------

    print("\n" + "=" * 75)
    print("TEST 2: CANDIDATE NEW REGISTER TAXON")
    print("=" * 75)

    candidate_packet = (
        build_candidate_evidence_packet(
            common_name=(
                "Black-crowned Night Heron"
            ),
            scientific_name=(
                "Nycticorax nycticorax"
            ),
            expected_rank="species",
            island="Nikoi",
            taxon_group="birds",
            environment="terrestrial",
            candidate_source="EarthRanger",
        )
    )

    candidate_register = (
        candidate_packet[
            "register_check"
        ]
    )

    print(
        "Scientific name: "
        "Nycticorax nycticorax"
    )

    print(
        "Island: Nikoi"
    )

    print(
        "Already registered: "
        f"{candidate_register['already_in_register']}"
    )

    print(
        "Candidate status: "
        f"{candidate_register['candidate_status']}"
    )

    print(
        "Proposed action: "
        f"{candidate_register['proposed_register_action']}"
    )

    print(
        "Evidence collection status: "
        f"{candidate_packet['evidence_collection_status']}"
    )

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    existing_pass = (
        existing_register[
            "already_in_register"
        ]
        is True
        and
        existing_register[
            "proposed_register_action"
        ]
        == "no_new_species_entry"
    )

    candidate_pass = (
        candidate_register[
            "already_in_register"
        ]
        is False
        and
        candidate_register[
            "proposed_register_action"
        ]
        == "review_for_possible_addition"
    )

    print("\n" + "=" * 75)

    if existing_pass and candidate_pass:

        print(
            "PASS: Species Register workflow correctly "
            "separates existing taxa from candidate additions."
        )

    else:

        print(
            "FAIL: Candidate workflow requires review."
        )

    print("=" * 75)


if __name__ == "__main__":
    main()