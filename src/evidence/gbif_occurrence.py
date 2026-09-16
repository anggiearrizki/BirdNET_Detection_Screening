"""Retrieve generic biodiversity occurrence evidence from GBIF.

This module provides supporting occurrence context for resolved taxa
across fauna, flora, and other biodiversity groups.

Important:
- GBIF occurrence records are supporting evidence only;
- occurrence counts do not confirm a local Nikoi/Cempedak record;
- zero GBIF records do not imply biological absence;
- taxonomic rank is preserved so evidence can be interpreted at the
  correct identification level.
"""

import requests


GBIF_OCCURRENCE_API = (
    "https://api.gbif.org/v1/occurrence/search"
)

COL_XR_CHECKLIST_KEY = (
    "7ddf754f-d193-4cc9-b351-99906754a03b"
)

REQUEST_TIMEOUT_SECONDS = 30


def get_gbif_occurrence_evidence(
    scientific_name,
    taxon_rank=None,
    country_code="ID",
):
    """Retrieve GBIF occurrence evidence for one accepted taxon."""

    params = {
        "scientificName": scientific_name,
        "checklistKey": COL_XR_CHECKLIST_KEY,
        "country": country_code,
        "occurrenceStatus": "PRESENT",
        "hasCoordinate": "true",
        "limit": 5,
    }

    try:
        response = requests.get(
            GBIF_OCCURRENCE_API,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

    except requests.RequestException as exc:

        return {
            "source": "GBIF",

            "evidence_type":
                "regional_occurrence_records",

            "scientific_name":
                scientific_name,

            "taxon_rank":
                taxon_rank,

            "geographic_scope":
                country_code,

            "evidence_status":
                "request_error",

            "occurrence_count":
                None,

            "sample_records":
                [],

            "error":
                str(exc),

            "interpretation_note":
                (
                    "GBIF occurrence evidence could not be "
                    "retrieved because the request failed."
                ),
        }

    data = response.json()

    total = data.get("count", 0)

    sample_records = []

    for record in data.get("results", []):

        sample_records.append(
            {
                "gbif_id":
                    record.get("key"),

                "scientific_name":
                    record.get(
                        "scientificName"
                    ),

                "event_date":
                    record.get(
                        "eventDate"
                    ),

                "latitude":
                    record.get(
                        "decimalLatitude"
                    ),

                "longitude":
                    record.get(
                        "decimalLongitude"
                    ),

                "basis_of_record":
                    record.get(
                        "basisOfRecord"
                    ),

                "dataset_title":
                    record.get(
                        "datasetTitle"
                    ),
            }
        )

    if total > 0:
        evidence_status = "records_found"
    else:
        evidence_status = "no_records_found"

    return {
        "source":
            "GBIF",

        "taxonomy_context":
            "Catalogue of Life Extended Release",

        "checklist_key":
            COL_XR_CHECKLIST_KEY,

        "evidence_type":
            "regional_occurrence_records",

        "scientific_name":
            scientific_name,

        "taxon_rank":
            taxon_rank,

        "geographic_scope":
            country_code,

        "evidence_status":
            evidence_status,

        "occurrence_count":
            total,

        "sample_records":
            sample_records,

        "interpretation_note":
            (
                "GBIF records provide supporting occurrence "
                "context only. Absence of records does not "
                "demonstrate biological absence."
            ),
    }


def main():

    # Initial real test case:
    # Black-crowned Night Heron.
    result = get_gbif_occurrence_evidence(
        scientific_name="Nycticorax nycticorax",
        taxon_rank="species",
    )

    print("=" * 70)
    print("GBIF OCCURRENCE EVIDENCE")
    print("=" * 70)

    print(
        f"\nScientific name: "
        f"{result['scientific_name']}"
    )

    print(
        f"Taxon rank: "
        f"{result['taxon_rank']}"
    )

    print(
        f"Evidence status: "
        f"{result['evidence_status']}"
    )

    print(
        f"Occurrence count: "
        f"{result['occurrence_count']}"
    )

    print(
        f"Geographic scope: "
        f"{result['geographic_scope']}"
    )

    print("\nSample records:")

    for record in result["sample_records"]:
        print(record)

    print("\nInterpretation:")

    print(
        result["interpretation_note"]
    )


if __name__ == "__main__":
    main()