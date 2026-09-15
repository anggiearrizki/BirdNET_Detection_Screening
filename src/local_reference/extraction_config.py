"""EXTRACTION CONFIGURATION FOR THE LOCAL BIODIVERSITY REFERENCE WORKBOOK.

This configuration describes where biodiversity records are stored in each
primary worksheet.

Important:
- Column numbers are zero-based.
- Raw workbook values are preserved during ingestion.
- Taxonomic corrections are not performed here.
"""

SHEET_EXTRACTION_CONFIG = {
    # ============================================================
    # CEMPEDAK - SIMPLE TABLES
    # ============================================================

    "Cmpk Birds": {
        "parser": "simple",
        "start_row": 8,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Cmpk Dragonflies": {
        "parser": "simple",
        "start_row": 7,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Cmpk Butterflies": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Cmpk Reptiles": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Cmpk Mamals": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
        "status_col": 6,
    },

    # ============================================================
    # CEMPEDAK - SPECIAL MARINE TABLE
    # ============================================================

    "Cmpk Other Marine Fauna": {
        "parser": "embedded_scientific_name",
        "start_row": 8,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
        "status_col": 5,
    },

    # ============================================================
    # NIKOI - SIMPLE TABLES
    # ============================================================

    "Nikoi Birds": {
        "parser": "simple",
        "start_row": 7,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Nikoi Dragonflies": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Nikoi Butterflies": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Nikoi Reptiles": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Nikoi Mammals": {
        "parser": "simple",
        "start_row": 7,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
        "status_col": 3,
    },

    "Nikoi other invertebrates": {
        "parser": "simple",
        "start_row": 6,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    # ============================================================
    # NIKOI - MARINE FISH
    # ============================================================

    "Nikoi Marine Fish": {
        "parser": "site_matrix",
        "start_row": 16,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 3,

        "site_columns": {
            5: "A",
            6: "B",
            7: "C",
            8: "D",
            9: "E",
        },
    },

    # ============================================================
    # NIKOI - MARINE INVERTEBRATES
    # ============================================================

    "Nikoi Marine Invertebrates": {
        "parser": "sectioned_site_matrix",
        "start_row": 17,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 4,

        "section_heading_columns": [0, 1],

        "site_columns": {
            6: "A",
            7: "B",
            8: "C",
            9: "D",
            10: "E",
        },
    },

    # ============================================================
    # NIKOI - OTHER MARINE FAUNA
    # ============================================================

    "Nikoi Other Marine Fauna": {
        "parser": "embedded_name_only",
        "start_row": 8,
        "common_name_col": 0,
        "status_col": 5,
    },

    # ============================================================
    # NIKOI - FLORA
    # ============================================================

    "Nikoi plantlife": {
        "parser": "simple",
        "start_row": 9,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    "Nikoi Marine Flora": {
        "parser": "simple",
        "start_row": 13,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
    },

    # ============================================================
    # NIKOI - ALGAE
    # ============================================================

    "Nikoi Marine Algae": {
        "parser": "sectioned_simple",
        "start_row": 12,
        "record_id_col": 0,
        "common_name_col": 1,
        "scientific_name_col": 2,
        "section_heading_col": 0,
    },
}


if __name__ == "__main__":
    print(
        f"Configured sheets: "
        f"{len(SHEET_EXTRACTION_CONFIG)}\n"
    )

    for sheet, config in SHEET_EXTRACTION_CONFIG.items():
        print(
            f"- {sheet}: "
            f"{config['parser']} | "
            f"start row {config['start_row']}"
        )