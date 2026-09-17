"""Construct evidence packets for candidate Species Register additions.

The reconciled Phase 2 biodiversity reference is the baseline Species Register.

A candidate may arrive from BirdNET, EarthRanger, a camera trap, field survey,
manual observation, or another monitoring workflow.

Workflow:

    candidate
        ↓
    taxonomy resolution
        ↓
    Species Register check
        ↓
    supporting evidence
        ↓
    specialist evidence
        ↓
    conservation context
        ↓
    human review

Important:
- taxonomy establishes identity, not biological presence;
- the Species Register is not a sightings database;
- external evidence provides supporting context only;
- absence from a database does not demonstrate biological absence;
- confirmed additions occur only after later human review.
"""

from datetime import datetime, timezone

from candidate_taxonomy import resolve_candidate_taxonomy
from local_ref_lookup import lookup_local_reference
from evidence_source_router import get_evidence_profile
from gbif_occurrence import get_gbif_occurrence_evidence


CANDIDATE_PACKET_VERSION = "0.2"


def initialise_specialist_evidence(
    evidence_profile,
):
    """Create empty slots for taxon-specific evidence adapters."""

    if evidence_profile == "birds":
        return {
            "birdnet_history": None,
            "birdnet_geomodel": None,
            "ebird": None,
        }

    if evidence_profile == "mammals":
        return {
            "camera_trap_history": None,
            "local_observation_history": None,
        }

    if evidence_profile == "reptiles":
        return {
            "local_observation_history": None,
            "photographic_records": None,
        }

    if evidence_profile == "terrestrial_invertebrates":
        return {
            "local_observation_history": None,
        }

    if evidence_profile == "terrestrial_flora":
        return {
            "herbarium_records": None,
            "botanical_occurrence_records": None,
        }

    if evidence_profile == "marine_flora":
        return {
            "obis": None,
            "local_survey_records": None,
        }

    if evidence_profile == "marine_fauna":
        return {
            "obis": None,
            "local_survey_records": None,
        }

    return {}


def build_candidate_evidence_packet(
    scientific_name,
    island,
    taxon_group,
    environment,
    expected_rank=None,
    common_name=None,
    candidate_source=None,
    source_record_id=None,
    source_reference=None,
    country_code="ID",
):
    """Build an evidence packet for a potential Species Register addition."""

    # ---------------------------------------------------------------------
    # 1. Resolve candidate taxonomy
    # ---------------------------------------------------------------------

    taxonomy = resolve_candidate_taxonomy(
        scientific_name=scientific_name,
        expected_rank=expected_rank,
    )

    taxonomy_status = taxonomy[
        "taxonomy_resolution_status"
    ]

    # ---------------------------------------------------------------------
    # 2. Stop automatic processing if taxonomy is not resolved
    # ---------------------------------------------------------------------

    if taxonomy_status != "resolved":

        return {
            "packet_metadata": {
                "packet_version":
                    CANDIDATE_PACKET_VERSION,

                "generated_at_utc":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

                "packet_type":
                    "species_register_candidate",
            },

            "candidate_source": {
                "source_type":
                    candidate_source,

                "source_record_id":
                    source_record_id,

                "source_reference":
                    source_reference,
            },

            "input_taxon": {
                "common_name":
                    common_name,

                "scientific_name":
                    scientific_name,

                "expected_rank":
                    expected_rank,

                "taxon_group":
                    taxon_group,
            },

            "taxonomy":
                taxonomy,

            "property": {
                "island":
                    island,

                "environment":
                    environment,
            },

            "register_check": {
                "status":
                    "not_run",

                "already_in_register":
                    None,

                "candidate_status":
                    "taxonomy_review_required",

                "proposed_register_action":
                    "resolve_taxonomy_before_register_check",

                "species_register_review_required":
                    False,
            },

            "local_reference_evidence":
                None,

            "evidence_profile":
                None,

            "evidence_collection_status":
                "blocked_by_taxonomy",

            "supporting_evidence": {},

            "specialist_evidence": {},

            "conservation_context": {
                "iucn":
                    None,
            },

            "review": {
                "review_priority":
                    None,

                "validation_outcome":
                    None,

                "review_notes":
                    None,
            },
        }

    # ---------------------------------------------------------------------
    # 3. Use accepted taxonomy for every downstream step
    # ---------------------------------------------------------------------

    accepted_scientific_name = taxonomy[
        "accepted_scientific_name"
    ]

    accepted_taxon_id = taxonomy[
        "accepted_taxon_id"
    ]

    accepted_rank = taxonomy[
        "accepted_rank"
    ]

    # ---------------------------------------------------------------------
    # 4. Check current Species Register
    # ---------------------------------------------------------------------

    local_reference = lookup_local_reference(
        scientific_name=accepted_scientific_name,
        island=island,
    )

    already_in_register = bool(
        local_reference[
            "local_reference_match"
        ]
    )

    # ---------------------------------------------------------------------
    # 5. Determine evidence profile
    # ---------------------------------------------------------------------

    evidence_profile = get_evidence_profile(
        taxon_group=taxon_group,
        environment=environment,
    )

    profile_name = evidence_profile[
        "evidence_profile"
    ]

    # ---------------------------------------------------------------------
    # 6. Determine candidate workflow
    # ---------------------------------------------------------------------

    if already_in_register:

        candidate_status = (
            "existing_register_taxon"
        )

        proposed_register_action = (
            "no_new_species_entry"
        )

        species_register_review_required = False

        evidence_collection_status = (
            "not_required_for_new_species_entry"
        )

    else:

        candidate_status = (
            "candidate_new_register_taxon"
        )

        proposed_register_action = (
            "review_for_possible_addition"
        )

        species_register_review_required = True

        evidence_collection_status = (
            "in_progress"
        )

    # ---------------------------------------------------------------------
    # 7. Generic supporting evidence
    #
    # Only needed automatically for candidate-new taxa.
    # ---------------------------------------------------------------------

    if already_in_register:

        gbif_evidence = None

    else:

        gbif_evidence = (
            get_gbif_occurrence_evidence(
                scientific_name=(
                    accepted_scientific_name
                ),

                taxon_rank=(
                    accepted_rank
                ),

                country_code=(
                    country_code
                ),
            )
        )

    # ---------------------------------------------------------------------
    # 8. Prepare specialist evidence slots
    # ---------------------------------------------------------------------

    if already_in_register:

        specialist_evidence = {}

    else:

        specialist_evidence = (
            initialise_specialist_evidence(
                evidence_profile=profile_name,
            )
        )

    # ---------------------------------------------------------------------
    # 9. Build candidate evidence packet
    # ---------------------------------------------------------------------

    packet = {
        "packet_metadata": {
            "packet_version":
                CANDIDATE_PACKET_VERSION,

            "generated_at_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "packet_type":
                "species_register_candidate",
        },

        # -----------------------------------------------------------------
        # Original candidate source
        # -----------------------------------------------------------------

        "candidate_source": {
            "source_type":
                candidate_source,

            "source_record_id":
                source_record_id,

            "source_reference":
                source_reference,
        },

        # -----------------------------------------------------------------
        # Name supplied by the source system
        # -----------------------------------------------------------------

        "input_taxon": {
            "common_name":
                common_name,

            "scientific_name":
                scientific_name,

            "expected_rank":
                expected_rank,

            "taxon_group":
                taxon_group,
        },

        # -----------------------------------------------------------------
        # Resolved accepted taxonomy
        # -----------------------------------------------------------------

        "taxonomy":
            taxonomy,

        "accepted_taxon": {
            "scientific_name":
                accepted_scientific_name,

            "accepted_taxon_id":
                accepted_taxon_id,

            "accepted_rank":
                accepted_rank,

            "taxon_group":
                taxon_group,
        },

        # -----------------------------------------------------------------
        # Property context
        # -----------------------------------------------------------------

        "property": {
            "island":
                island,

            "environment":
                environment,
        },

        # -----------------------------------------------------------------
        # Species Register check
        # -----------------------------------------------------------------

        "register_check": {
            "status":
                "completed",

            "already_in_register":
                already_in_register,

            "candidate_status":
                candidate_status,

            "proposed_register_action":
                proposed_register_action,

            "species_register_review_required":
                species_register_review_required,
        },

        "local_reference_evidence":
            local_reference,

        # -----------------------------------------------------------------
        # Supporting evidence routing
        # -----------------------------------------------------------------

        "evidence_profile":
            evidence_profile,

        "evidence_collection_status":
            evidence_collection_status,

        # -----------------------------------------------------------------
        # Generic supporting evidence
        # -----------------------------------------------------------------

        "supporting_evidence": {
            "gbif_occurrence":
                gbif_evidence,
        },

        # -----------------------------------------------------------------
        # Taxon-specific evidence
        # -----------------------------------------------------------------

        "specialist_evidence":
            specialist_evidence,

        # -----------------------------------------------------------------
        # Conservation context
        # -----------------------------------------------------------------

        "conservation_context": {
            "iucn":
                None,
        },

        # -----------------------------------------------------------------
        # Phase 4 review fields
        # -----------------------------------------------------------------

        "review": {
            "review_priority":
                None,

            "validation_outcome":
                None,

            "review_notes":
                None,
        },

        # -----------------------------------------------------------------
        # Scientific safeguards
        # -----------------------------------------------------------------

        "interpretation": {
            "taxonomy_note":
                (
                    "Taxonomy establishes the candidate's "
                    "accepted identity but does not establish "
                    "biological presence."
                ),

            "register_note":
                (
                    "The Species Register represents the "
                    "current property species list and is not "
                    "a sightings database."
                ),

            "local_reference_note":
                (
                    "Not being listed in the current Species "
                    "Register means the taxon may require review "
                    "as a candidate addition. It does not imply "
                    "biological absence."
                ),

            "supporting_evidence_note":
                (
                    "External occurrence evidence provides "
                    "supporting context only and does not "
                    "independently confirm a local record."
                ),

            "negative_evidence_note":
                (
                    "Absence from an external database does "
                    "not demonstrate biological absence."
                ),
        },
    }

    return packet


def print_candidate_packet(packet):
    """Print a readable candidate Species Register assessment."""

    print("=" * 75)
    print("SPECIES REGISTER CANDIDATE EVIDENCE PACKET")
    print("=" * 75)

    # ---------------------------------------------------------------------
    # Candidate source
    # ---------------------------------------------------------------------

    print("\nSOURCE")

    source = packet[
        "candidate_source"
    ]

    print(
        f"Source type: "
        f"{source['source_type']}"
    )

    print(
        f"Source record ID: "
        f"{source['source_record_id']}"
    )

    # ---------------------------------------------------------------------
    # Input taxon
    # ---------------------------------------------------------------------

    print("\nINPUT TAXON")

    input_taxon = packet[
        "input_taxon"
    ]

    print(
        f"Common name: "
        f"{input_taxon['common_name']}"
    )

    print(
        f"Scientific name supplied: "
        f"{input_taxon['scientific_name']}"
    )

    print(
        f"Expected rank: "
        f"{input_taxon['expected_rank']}"
    )

    # ---------------------------------------------------------------------
    # Taxonomy
    # ---------------------------------------------------------------------

    print("\nTAXONOMY RESOLUTION")

    taxonomy = packet["taxonomy"]

    print(
        f"Status: "
        f"{taxonomy['taxonomy_resolution_status']}"
    )

    print(
        f"Recommended action: "
        f"{taxonomy['recommended_action']}"
    )

    if (
        taxonomy[
            "taxonomy_resolution_status"
        ]
        != "resolved"
    ):

        print(
            "\nAutomatic candidate processing stopped "
            "because taxonomy requires review."
        )

        print("=" * 75)

        return

    accepted_taxon = packet[
        "accepted_taxon"
    ]

    print(
        f"Accepted scientific name: "
        f"{accepted_taxon['scientific_name']}"
    )

    print(
        f"Accepted taxon ID: "
        f"{accepted_taxon['accepted_taxon_id']}"
    )

    print(
        f"Accepted rank: "
        f"{accepted_taxon['accepted_rank']}"
    )

    print(
        f"Mapping type: "
        f"{taxonomy['mapping_type']}"
    )

    print(
        f"Match confidence: "
        f"{taxonomy['confidence']}"
    )

    # ---------------------------------------------------------------------
    # Property
    # ---------------------------------------------------------------------

    print("\nPROPERTY")

    property_info = packet[
        "property"
    ]

    print(
        f"Island: "
        f"{property_info['island']}"
    )

    print(
        f"Environment: "
        f"{property_info['environment']}"
    )

    # ---------------------------------------------------------------------
    # Register check
    # ---------------------------------------------------------------------

    print("\nSPECIES REGISTER CHECK")

    register = packet[
        "register_check"
    ]

    print(
        f"Already registered: "
        f"{register['already_in_register']}"
    )

    print(
        f"Candidate status: "
        f"{register['candidate_status']}"
    )

    print(
        f"Proposed action: "
        f"{register['proposed_register_action']}"
    )

    print(
        f"Register review required: "
        f"{register['species_register_review_required']}"
    )

    # ---------------------------------------------------------------------
    # Evidence routing
    # ---------------------------------------------------------------------

    print("\nEVIDENCE PROFILE")

    profile = packet[
        "evidence_profile"
    ]

    print(
        f"Profile: "
        f"{profile['evidence_profile']}"
    )

    print(
        "Relevant evidence types:"
    )

    for evidence_type in (
        profile[
            "supporting_evidence_types"
        ]
    ):

        print(
            f"  - {evidence_type}"
        )

    # ---------------------------------------------------------------------
    # Generic evidence
    # ---------------------------------------------------------------------

    print("\nSUPPORTING EVIDENCE")

    gbif = packet[
        "supporting_evidence"
    ]["gbif_occurrence"]

    if gbif is None:

        print(
            "GBIF occurrence: not requested "
            "(taxon already registered)"
        )

    else:

        print(
            f"GBIF status: "
            f"{gbif['evidence_status']}"
        )

        print(
            f"GBIF occurrence count: "
            f"{gbif['occurrence_count']}"
        )

        print(
            f"GBIF geographic scope: "
            f"{gbif['geographic_scope']}"
        )

    # ---------------------------------------------------------------------
    # Specialist evidence
    # ---------------------------------------------------------------------

    print("\nSPECIALIST EVIDENCE")

    specialist = packet[
        "specialist_evidence"
    ]

    if specialist:

        for source_name, value in (
            specialist.items()
        ):

            status = (
                "pending"
                if value is None
                else "available"
            )

            print(
                f"{source_name}: "
                f"{status}"
            )

    else:

        print(
            "Not required for a new "
            "Species Register entry."
        )

    # ---------------------------------------------------------------------
    # Conservation
    # ---------------------------------------------------------------------

    print("\nCONSERVATION CONTEXT")

    iucn = packet[
        "conservation_context"
    ]["iucn"]

    print(
        "IUCN: "
        + (
            "pending"
            if iucn is None
            else "available"
        )
    )

    print("=" * 75)


def main():

    # Real candidate-new-species example.
    #
    # Notice that accepted taxonomy is NOT supplied manually.
    # The candidate taxonomy resolver now provides it.

    packet = build_candidate_evidence_packet(
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

        source_record_id=(
            "f46bc890-bb7a-4fd9-81e7-0ea7d4f75aaa"
        ),

        source_reference=(
            "https://bintan.pamdas.org/events/"
            "f46bc890-bb7a-4fd9-81e7-0ea7d4f75aaa"
        ),
    )

    print_candidate_packet(
        packet
    )


if __name__ == "__main__":
    main()