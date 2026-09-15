"""Source map for the Cempedak and Nikoi biodiversity reference workbook.

This module defines which workbook sheets are treated as primary local
biodiversity references and which are retained only as supporting sources.

The original Excel sheet names are preserved exactly as supplied.
"""

PRIMARY_BIODIVERSITY_SHEETS = {
    # ============================================================
    # CEMPEDAK
    # ============================================================

    "Cmpk Birds": {
        "island": "Cempedak",
        "reference_group": "fauna",
        "taxon_group": "birds",
        "environment": "terrestrial",
    },

    "Cmpk Dragonflies": {
        "island": "Cempedak",
        "reference_group": "fauna",
        "taxon_group": "dragonflies",
        "environment": "terrestrial",
    },

    "Cmpk Butterflies": {
        "island": "Cempedak",
        "reference_group": "fauna",
        "taxon_group": "butterflies",
        "environment": "terrestrial",
    },

    "Cmpk Reptiles": {
        "island": "Cempedak",
        "reference_group": "fauna",
        "taxon_group": "reptiles",
        "environment": "terrestrial",
    },

    "Cmpk Mamals": {
        "island": "Cempedak",
        "reference_group": "fauna",
        "taxon_group": "mammals",
        "environment": "terrestrial",
    },

    "Cmpk Other Marine Fauna": {
        "island": "Cempedak",
        "reference_group": "fauna",
        "taxon_group": "mixed_marine_fauna",
        "environment": "marine",
    },

    # ============================================================
    # NIKOI - FAUNA
    # ============================================================

    "Nikoi Birds": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "birds",
        "environment": "terrestrial",
    },

    "Nikoi Dragonflies": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "dragonflies",
        "environment": "terrestrial",
    },

    "Nikoi Butterflies": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "butterflies",
        "environment": "terrestrial",
    },

    "Nikoi Reptiles": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "reptiles",
        "environment": "terrestrial",
    },

    "Nikoi Mammals": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "mammals",
        "environment": "terrestrial",
    },

    "Nikoi other invertebrates": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "other_invertebrates",
        "environment": "terrestrial",
    },

    "Nikoi Marine Fish": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "fish",
        "environment": "marine",
    },

    "Nikoi Marine Invertebrates": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "marine_invertebrates",
        "environment": "marine",
    },

    "Nikoi Other Marine Fauna": {
        "island": "Nikoi",
        "reference_group": "fauna",
        "taxon_group": "mixed_marine_fauna",
        "environment": "marine",
    },

    # ============================================================
    # NIKOI - FLORA / ALGAE
    # ============================================================

    "Nikoi plantlife": {
        "island": "Nikoi",
        "reference_group": "flora",
        "taxon_group": "terrestrial_plants",
        "environment": "terrestrial",
    },

    "Nikoi Marine Flora": {
        "island": "Nikoi",
        "reference_group": "flora",
        "taxon_group": "marine_plants",
        "environment": "marine",
    },

    "Nikoi Marine Algae": {
        "island": "Nikoi",
        "reference_group": "algae",
        "taxon_group": "marine_algae",
        "environment": "marine",
    },
}


SUPPORTING_SHEETS = {
    "CI fish survey 2018": "historical_survey",
    "New additions": "update_log",
    "Form Responses 1": "raw_observations",
    "IUCN redlist": "conservation_reference",
}


EXCLUDED_SHEETS = {
    "Summary",
    "Birds total",
    "Sheet26",
}


if __name__ == "__main__":
    print(
        f"Primary biodiversity reference sheets: "
        f"{len(PRIMARY_BIODIVERSITY_SHEETS)}\n"
    )

    for sheet, metadata in PRIMARY_BIODIVERSITY_SHEETS.items():
        print(
            f"- {sheet}: "
            f"{metadata['island']} | "
            f"{metadata['reference_group']} | "
            f"{metadata['taxon_group']} | "
            f"{metadata['environment']}"
        )

    print(
        f"\nSupporting sheets: {len(SUPPORTING_SHEETS)}"
    )

    for sheet, role in SUPPORTING_SHEETS.items():
        print(f"- {sheet}: {role}")

    print(
        f"\nExcluded sheets: {len(EXCLUDED_SHEETS)}"
    )

    for sheet in sorted(EXCLUDED_SHEETS):
        print(f"- {sheet}")