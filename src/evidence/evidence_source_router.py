"""Route biodiversity taxanomy to appropriate supporting-evidence profiles.

Phase 3.2 uses the taxonomic and ecological context established in
Phase 2 to determine which TYPES of supporting evidence may be relevant.

This module does not retrieve external evidence.

It only defines routing so that, for example:
- birds are not treated like plants;
- terrestrial taxa are not automatically routed to marine sources;
- BirdNET-specific evidence is used only where biologically appropriate.
"""


def normalize_value(value):
    """Normalize a categorical value for rule matching."""

    if value is None:
        return ""

    return str(value).strip().casefold()


def get_evidence_profile(
    taxon_group,
    environment=None,
):
    """Return the supporting-evidence profile for a taxon."""

    group = normalize_value(taxon_group)
    env = normalize_value(environment)

    profile = {
        "taxon_group": taxon_group,
        "environment": environment,
        "evidence_profile": "general_biodiversity",
        "supporting_evidence_types": [
            "local_occurrence_records",
            "external_occurrence_records",
        ],
    }

    # ---------------------------------------------------------
    # Birds
    # ---------------------------------------------------------

    if group == "birds":
        profile["evidence_profile"] = "birds"
        profile["supporting_evidence_types"] = [
            "acoustic_detection_history",
            "geographic_model_support",
            "regional_occurrence_records",
        ]

    # ---------------------------------------------------------
    # Mammals
    # ---------------------------------------------------------

    elif group == "mammals":
        profile["evidence_profile"] = "mammals"
        profile["supporting_evidence_types"] = [
            "camera_trap_records",
            "local_observation_history",
            "regional_occurrence_records",
        ]

    # ---------------------------------------------------------
    # Reptiles
    # ---------------------------------------------------------

    elif group == "reptiles":
        profile["evidence_profile"] = "reptiles"
        profile["supporting_evidence_types"] = [
            "local_observation_history",
            "photographic_records",
            "regional_occurrence_records",
        ]

    # ---------------------------------------------------------
    # Terrestrial invertebrates
    # ---------------------------------------------------------

    elif group in {
        "butterflies",
        "dragonflies",
        "other_invertebrates",
    } and env == "terrestrial":

        profile["evidence_profile"] = (
            "terrestrial_invertebrates"
        )

        profile["supporting_evidence_types"] = [
            "local_observation_history",
            "regional_occurrence_records",
        ]

    # ---------------------------------------------------------
    # Terrestrial plants
    # ---------------------------------------------------------

    elif group == "terrestrial_plants":
        profile["evidence_profile"] = "terrestrial_flora"
        profile["supporting_evidence_types"] = [
            "botanical_occurrence_records",
            "specimen_or_herbarium_records",
            "regional_occurrence_records",
        ]

    # ---------------------------------------------------------
    # Marine plants and algae
    # ---------------------------------------------------------

    elif group in {
        "marine_plants",
        "marine_algae",
    }:

        profile["evidence_profile"] = "marine_flora"
        profile["supporting_evidence_types"] = [
            "marine_occurrence_records",
            "survey_records",
        ]

    # ---------------------------------------------------------
    # Other marine biodiversity
    # ---------------------------------------------------------

    elif env == "marine":
        profile["evidence_profile"] = "marine_fauna"
        profile["supporting_evidence_types"] = [
            "marine_occurrence_records",
            "local_survey_records",
            "regional_occurrence_records",
        ]

    return profile


def main():

    examples = [
        ("birds", "terrestrial"),
        ("mammals", "terrestrial"),
        ("reptiles", "terrestrial"),
        ("butterflies", "terrestrial"),
        ("terrestrial_plants", "terrestrial"),
        ("marine_algae", "marine"),
        ("marine_plants", "marine"),
        ("mixed_marine_fauna", "marine"),
    ]

    print("=" * 70)
    print("SUPPORTING EVIDENCE ROUTING")
    print("=" * 70)

    for taxon_group, environment in examples:

        profile = get_evidence_profile(
            taxon_group=taxon_group,
            environment=environment,
        )

        print(
            f"\n{taxon_group} | {environment}"
        )

        print(
            f"Profile: "
            f"{profile['evidence_profile']}"
        )

        print(
            "Evidence types:"
        )

        for evidence_type in (
            profile["supporting_evidence_types"]
        ):
            print(f"  - {evidence_type}")


if __name__ == "__main__":
    main()