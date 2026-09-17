from pathlib import Path
import json
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_baseline.csv"
)

RECONCILED_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.csv"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_baseline_iucn.csv"
)

OUTPUT_XLSX = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_baseline_iucn.xlsx"
)

AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "iucn_enrichment_audit.csv"
)

CACHE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "iucn_cache.json"
)


# ============================================================
# CONFIG
# ============================================================

BASE_URL = (
    "https://api.iucnredlist.org/api/v4/"
    "taxa/scientific_name"
)

# Keep this at 5 until we validate the synonym fallback.
# Later we will change this to None.
TEST_LIMIT = None

REQUEST_DELAY_SECONDS = 0.3


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")

IUCN_API_TOKEN = os.getenv(
    "IUCN_API_TOKEN"
)

if not IUCN_API_TOKEN:
    raise RuntimeError(
        "IUCN_API_TOKEN was not found in the .env file."
    )


# ============================================================
# HTTP SESSION
# ============================================================

def build_session():
    """
    Create a requests session with retry handling.
    """

    session = requests.Session()

    retry = Retry(
        total=4,
        backoff_factor=1.0,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(
        max_retries=retry
    )

    session.mount(
        "https://",
        adapter,
    )

    session.headers.update(
        {
            "Authorization":
                f"Bearer {IUCN_API_TOKEN}"
        }
    )

    return session


# ============================================================
# CACHE
# ============================================================

def load_cache():
    """
    Load previous IUCN results so we do not repeatedly
    query the same species.
    """

    if not CACHE_PATH.exists():
        return {}

    try:
        with open(
            CACHE_PATH,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}


def save_cache(cache):
    """
    Save IUCN results locally.
    """

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        CACHE_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            cache,
            file,
            indent=2,
            ensure_ascii=False,
        )


def cache_result_is_reusable(
    result,
):
    """
    Only reuse cache results that were successfully processed
    using the current fallback-aware structure.

    Old cached 'not_found' results will therefore be re-queried.
    """

    if not isinstance(
        result,
        dict,
    ):
        return False

    if (
        "iucn_match_method"
        not in result
    ):
        return False

    query_status = result.get(
        "query_status"
    )

    return query_status in {
        "assessment_found",
        "no_global_assessment",
        "not_queryable",
    }


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_text(value):
    """
    Safely convert a value to a stripped string.
    """

    if pd.isna(value):
        return ""

    return str(value).strip()


# ============================================================
# TAXONOMY ALIAS LOOKUP
# ============================================================

def build_alias_lookup():
    """
    Build alternate scientific-name mappings from the
    reconciled taxonomy file.

    Example:

        Species Register:
            Muscicapa latirostris

        Alternate/source name:
            Muscicapa dauurica

    The Species Register name remains unchanged.

    Alternate names are used only when querying IUCN.
    """

    if not RECONCILED_PATH.exists():
        raise FileNotFoundError(
            f"Reconciled taxonomy file not found:\n"
            f"{RECONCILED_PATH}"
        )

    reconciled = pd.read_csv(
        RECONCILED_PATH,
        dtype="string",
    )

    alias_lookup = {}

    resolved = reconciled[
        reconciled[
            "taxonomy_reconciliation_status"
        ] == "resolved"
    ].copy()

    alternate_columns = [
        "scientific_name_raw",
        "scientific_name_candidate",
        "scientific_name_normalized",
        "matched_canonical_name",
    ]

    for _, row in resolved.iterrows():

        accepted_name = clean_text(
            row.get(
                "accepted_scientific_name"
            )
        )

        if not accepted_name:
            continue

        if (
            accepted_name
            not in alias_lookup
        ):
            alias_lookup[
                accepted_name
            ] = []

        for column in alternate_columns:

            value = clean_text(
                row.get(column)
            )

            if not value:
                continue

            if value in {
                "?",
                "-",
                "NA",
                "N/A",
            }:
                continue

            if (
                value
                == accepted_name
            ):
                continue

            if (
                value
                not in alias_lookup[
                    accepted_name
                ]
            ):
                alias_lookup[
                    accepted_name
                ].append(
                    value
                )

    return alias_lookup


# ============================================================
# IUCN NAME PARSING
# ============================================================

def parse_species_name(
    scientific_name,
):
    """
    Convert a scientific name into the genus/species
    parameters expected by the IUCN API.

    Examples:

        Oriolus chinensis
        -> genus_name = Oriolus
        -> species_name = chinensis

    Names such as:
        Genus sp.
        Genus spp.

    are not queryable automatically.
    """

    scientific_name = clean_text(
        scientific_name
    )

    if not scientific_name:
        return None

    parts = scientific_name.split()

    if len(parts) < 2:
        return None

    genus_name = parts[0]
    species_name = parts[1]

    invalid_species_tokens = {
        "sp.",
        "spp.",
        "cf.",
        "aff.",
        "?",
    }

    if (
        species_name.lower()
        in invalid_species_tokens
    ):
        return None

    return {
        "genus_name":
            genus_name,
        "species_name":
            species_name,
    }


# ============================================================
# IUCN ASSESSMENT SELECTION
# ============================================================

def is_global_assessment(
    assessment,
):
    """
    Determine whether an assessment has global scope.

    IUCN scope code 1 represents Global.
    """

    scopes = assessment.get(
        "scopes",
        [],
    )

    return any(
        str(
            scope.get("code")
        ) == "1"
        for scope in scopes
    )


def select_latest_global_assessment(
    assessments,
):
    """
    Select the latest global IUCN assessment.

    Prefer the assessment explicitly marked latest=True.

    If that is unavailable, fall back to the most recently
    published global assessment.
    """

    global_assessments = [
        assessment
        for assessment
        in assessments
        if is_global_assessment(
            assessment
        )
    ]

    if not global_assessments:
        return None

    explicitly_latest = [
        assessment
        for assessment
        in global_assessments
        if assessment.get(
            "latest"
        )
        is True
    ]

    if explicitly_latest:
        return explicitly_latest[0]

    return max(
        global_assessments,
        key=lambda assessment: (
            assessment.get(
                "year_published"
            )
            or 0
        ),
    )


# ============================================================
# SINGLE IUCN QUERY
# ============================================================

def query_iucn(
    session,
    scientific_name,
):
    """
    Query IUCN for one scientific name.
    """

    parsed_name = parse_species_name(
        scientific_name
    )

    if parsed_name is None:
        return {
            "query_status":
                "not_queryable",
            "scientific_name":
                scientific_name,
            "matched_scientific_name":
                None,
            "sis_taxon_id":
                None,
            "iucn_status":
                None,
            "year_published":
                None,
            "assessment_date":
                None,
            "iucn_url":
                None,
        }

    response = session.get(
        BASE_URL,
        params=parsed_name,
        timeout=30,
    )

    if response.status_code == 404:
        return {
            "query_status":
                "not_found",
            "scientific_name":
                scientific_name,
            "matched_scientific_name":
                None,
            "sis_taxon_id":
                None,
            "iucn_status":
                None,
            "year_published":
                None,
            "assessment_date":
                None,
            "iucn_url":
                None,
        }

    response.raise_for_status()

    data = response.json()

    taxon = data.get(
        "taxon",
        {},
    )

    assessments = data.get(
        "assessments",
        [],
    )

    matched_name = taxon.get(
        "scientific_name"
    )

    sis_taxon_id = taxon.get(
        "sis_id"
    )

    assessment = (
        select_latest_global_assessment(
            assessments
        )
    )

    if assessment is None:
        return {
            "query_status":
                "no_global_assessment",
            "scientific_name":
                scientific_name,
            "matched_scientific_name":
                matched_name,
            "sis_taxon_id":
                sis_taxon_id,
            "iucn_status":
                None,
            "year_published":
                None,
            "assessment_date":
                None,
            "iucn_url":
                None,
        }

    return {
        "query_status":
            "assessment_found",
        "scientific_name":
            scientific_name,
        "matched_scientific_name":
            matched_name,
        "sis_taxon_id":
            sis_taxon_id,
        "iucn_status":
            assessment.get(
                "red_list_category_code"
            ),
        "year_published":
            assessment.get(
                "year_published"
            ),
        "assessment_date":
            assessment.get(
                "assessment_date"
            ),
        "iucn_url":
            assessment.get(
                "url"
            ),
    }


# ============================================================
# FALLBACK QUERY
# ============================================================

def query_iucn_with_fallback(
    session,
    scientific_name,
    alias_lookup,
):
    """
    Query IUCN using the Species Register scientific name first.

    If the accepted name is not found, try known alternate names
    from the taxonomy reconciliation.

    The Species Register scientific name itself is never changed.
    """

    names_to_try = [
        scientific_name
    ]

    for alternate_name in (
        alias_lookup.get(
            scientific_name,
            [],
        )
    ):
        if (
            alternate_name
            not in names_to_try
        ):
            names_to_try.append(
                alternate_name
            )

    last_result = None

    for attempt_number, query_name in enumerate(
        names_to_try,
        start=1,
    ):

        result = query_iucn(
            session,
            query_name,
        )

        last_result = result

        query_status = result.get(
            "query_status"
        )

        if query_status in {
            "assessment_found",
            "no_global_assessment",
        }:

            result[
                "register_scientific_name"
            ] = scientific_name

            result[
                "iucn_query_name"
            ] = query_name

            result[
                "iucn_match_method"
            ] = (
                "accepted_name"
                if attempt_number == 1
                else "alternate_name"
            )

            return result

    if last_result is None:
        last_result = {
            "query_status":
                "not_found",
            "scientific_name":
                scientific_name,
            "matched_scientific_name":
                None,
            "sis_taxon_id":
                None,
            "iucn_status":
                None,
            "year_published":
                None,
            "assessment_date":
                None,
            "iucn_url":
                None,
        }

    last_result[
        "register_scientific_name"
    ] = scientific_name

    last_result[
        "iucn_query_name"
    ] = (
        names_to_try[-1]
        if names_to_try
        else scientific_name
    )

    if (
        last_result.get(
            "query_status"
        )
        == "not_queryable"
    ):
        last_result[
            "iucn_match_method"
        ] = "not_queryable"

    else:
        last_result[
            "iucn_match_method"
        ] = "not_found"

    return last_result


# ============================================================
# MAIN ENRICHMENT
# ============================================================

def main():

    print("=" * 70)
    print(
        "IUCN SPECIES REGISTER ENRICHMENT"
    )
    print("=" * 70)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Species Register baseline not found:\n"
            f"{INPUT_PATH}"
        )

    register = pd.read_csv(
        INPUT_PATH,
        dtype={
            "common_name":
                "string",
            "scientific_name":
                "string",
            "group":
                "string",
            "properties":
                "string",
            "status":
                "string",
            "references":
                "string",
            "photo_url":
                "string",
            "fun_fact":
                "string",
            "iucn_status":
                "string",
        },
    )

    # Make sure enrichment column can safely receive
    # values such as LC, VU, EN, etc.
    register[
        "iucn_status"
    ] = register[
        "iucn_status"
    ].astype("string")

    alias_lookup = (
        build_alias_lookup()
    )

    cache = load_cache()

    session = build_session()

    audit_records = []

    queryable_indices = [
        index
        for index, row
        in register.iterrows()
        if parse_species_name(
            row.get(
                "scientific_name"
            )
        )
        is not None
    ]

    if TEST_LIMIT is not None:
        queryable_indices = (
            queryable_indices[
                :TEST_LIMIT
            ]
        )

    print(
        f"\nRegister records: "
        f"{len(register)}"
    )

    print(
        f"Queryable records: "
        f"{len(queryable_indices)}"
    )

    print(
        f"Taxonomy alias entries: "
        f"{len(alias_lookup)}"
    )

    for position, index in enumerate(
        queryable_indices,
        start=1,
    ):

        scientific_name = clean_text(
            register.at[
                index,
                "scientific_name",
            ]
        )

        print(
            f"\n[{position}/"
            f"{len(queryable_indices)}] "
            f"{scientific_name}"
        )

        cached_result = cache.get(
            scientific_name
        )

        if cache_result_is_reusable(
            cached_result
        ):

            print(
                "  Using cached result."
            )

            result = cached_result

        else:

            try:

                result = (
                    query_iucn_with_fallback(
                        session,
                        scientific_name,
                        alias_lookup,
                    )
                )

                cache[
                    scientific_name
                ] = result

                save_cache(
                    cache
                )

                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

            except requests.RequestException as error:

                print(
                    f"  Request error: "
                    f"{error}"
                )

                result = {
                    "query_status":
                        "request_error",
                    "scientific_name":
                        scientific_name,
                    "register_scientific_name":
                        scientific_name,
                    "iucn_query_name":
                        scientific_name,
                    "iucn_match_method":
                        "request_error",
                    "matched_scientific_name":
                        None,
                    "sis_taxon_id":
                        None,
                    "iucn_status":
                        None,
                    "year_published":
                        None,
                    "assessment_date":
                        None,
                    "iucn_url":
                        None,
                }

        iucn_status = result.get(
            "iucn_status"
        )

        if iucn_status:
            register.at[
                index,
                "iucn_status",
            ] = iucn_status

        print(
            "  Query status: "
            f"{result.get('query_status')}"
        )

        print(
            "  Query name: "
            f"{result.get('iucn_query_name')}"
        )

        print(
            "  Match method: "
            f"{result.get('iucn_match_method')}"
        )

        print(
            "  IUCN status: "
            f"{result.get('iucn_status')}"
        )

        audit_records.append(
            result
        )

    # ========================================================
    # SAVE ENRICHED REGISTER
    # ========================================================
    # Display fallback for records without an available IUCN assessment.
    # This is not an official IUCN category.
    register["iucn_status"] = (
        register["iucn_status"]
        .fillna("Status Not Available")
        .replace("", "Status Not Available")
    )

    register.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    register.to_excel(
        OUTPUT_XLSX,
        index=False,
    )

    # ========================================================
    # SAVE AUDIT
    # ========================================================

    audit = pd.DataFrame(
        audit_records
    )

    preferred_audit_columns = [
        "register_scientific_name",
        "iucn_query_name",
        "iucn_match_method",
        "query_status",
        "matched_scientific_name",
        "sis_taxon_id",
        "iucn_status",
        "year_published",
        "assessment_date",
        "iucn_url",
    ]

    for column in (
        preferred_audit_columns
    ):
        if column not in audit.columns:
            audit[column] = None

    audit = audit[
        preferred_audit_columns
    ]

    audit.to_csv(
        AUDIT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "IUCN ENRICHMENT COMPLETE"
    )

    print(
        "=" * 70
    )

    if not audit.empty:

        print(
            "\nQuery status summary:"
        )

        print(
            audit[
                "query_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        print(
            "\nMatch method summary:"
        )

        print(
            audit[
                "iucn_match_method"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        print(
            "\nIUCN categories found:"
        )

        print(
            audit[
                "iucn_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

    print(
        f"\nEnriched CSV:\n"
        f"{OUTPUT_CSV}"
    )

    print(
        f"\nEnriched XLSX:\n"
        f"{OUTPUT_XLSX}"
    )

    print(
        f"\nAudit file:\n"
        f"{AUDIT_PATH}"
    )

    print(
        f"\nCache file:\n"
        f"{CACHE_PATH}"
    )

    if TEST_LIMIT is not None:

        print(
            "\nTEST MODE IS ACTIVE:"
        )

        print(
            f"Only the first "
            f"{TEST_LIMIT} queryable "
            f"species were processed."
        )


if __name__ == "__main__":
    main()