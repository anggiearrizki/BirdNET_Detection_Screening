from pathlib import Path
import os
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

IUCN_API_TOKEN = os.getenv("IUCN_API_TOKEN")

if not IUCN_API_TOKEN:
    raise RuntimeError(
        "IUCN_API_TOKEN was not found in the .env file."
    )


BASE_URL = (
    "https://api.iucnredlist.org/api/v4/"
    "taxa/scientific_name"
)


def get_iucn_species(genus_name, species_name):
    headers = {
        "Authorization": f"Bearer {IUCN_API_TOKEN}"
    }

    params = {
        "genus_name": genus_name,
        "species_name": species_name,
    }

    response = requests.get(
        BASE_URL,
        headers=headers,
        params=params,
        timeout=30,
    )

    print(f"HTTP status: {response.status_code}")

    response.raise_for_status()

    return response.json()


def main():
    # One known species from our baseline.
    genus_name = "Oriolus"
    species_name = "chinensis"

    print("=" * 60)
    print("IUCN API TEST")
    print("=" * 60)

    print(
        f"\nQuerying: {genus_name} {species_name}"
    )

    data = get_iucn_species(
        genus_name,
        species_name,
    )

    taxon = data.get("taxon", {})

    print("\nTaxon:")
    print(
        f"Scientific name: "
        f"{taxon.get('scientific_name')}"
    )
    print(
        f"IUCN SIS taxon ID: "
        f"{taxon.get('sis_id')}"
    )

    assessments = data.get(
        "assessments",
        [],
    )

    print(
        f"Assessments returned: "
        f"{len(assessments)}"
    )

    latest_global = []

    for assessment in assessments:
        is_latest = assessment.get(
            "latest"
        ) is True

        scopes = assessment.get(
            "scopes",
            [],
        )

        is_global = any(
            scope.get("code") == "1"
            for scope in scopes
        )

        if is_latest and is_global:
            latest_global.append(
                assessment
            )

    if latest_global:
        assessment = latest_global[0]

        print("\nLatest global assessment:")
        print(
            "IUCN status: "
            f"{assessment.get('red_list_category_code')}"
        )
        print(
            "Year published: "
            f"{assessment.get('year_published')}"
        )
        print(
            "Assessment date: "
            f"{assessment.get('assessment_date')}"
        )
        print(
            "IUCN URL: "
            f"{assessment.get('url')}"
        )

    else:
        print(
            "\nNo latest global assessment "
            "was found."
        )

    print("\n" + "=" * 60)
    print("IUCN API TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()