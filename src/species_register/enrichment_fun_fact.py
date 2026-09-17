from pathlib import Path
from urllib.parse import urlparse, unquote
import json
import re
import time

import pandas as pd
import requests
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
    / "species_register_baseline_iucn.csv"
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
    / "species_register_baseline_enriched.csv"
)

OUTPUT_XLSX = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_baseline_enriched.xlsx"
)

AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_media_funfact_audit.csv"
)

CACHE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_media_funfact_cache.json"
)


# ============================================================
# CONFIG
# ============================================================

INAT_TAXA_URL = (
    "https://api.inaturalist.org/v1/taxa"
)

WIKIPEDIA_SUMMARY_URL = (
    "https://en.wikipedia.org/api/rest_v1/page/summary"
)

REQUEST_TIMEOUT = 30

REQUEST_DELAY_SECONDS = 0.5

# Keep this at 5 until we validate the output.
TEST_LIMIT = None # validated

# Conservative automatic photo reuse rule.
ALLOWED_PHOTO_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
}


# ============================================================
# HTTP SESSION
# ============================================================

def build_session():
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
            "User-Agent":
                "BintanMPA-SpeciesRegister/1.0"
        }
    )

    return session


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_text(value):
    if pd.isna(value):
        return ""

    return " ".join(
        str(value)
        .strip()
        .split()
    )


# ============================================================
# CACHE
# ============================================================

def load_cache():
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


# ============================================================
# TAXONOMY ALIASES
# ============================================================

def build_alias_lookup():
    """
    Use the Phase 2 taxonomy reconciliation only to provide
    alternate names when an accepted name is not found.

    The Species Register scientific name itself is never changed.
    """

    reconciled = pd.read_csv(
        RECONCILED_PATH,
        dtype="string",
    )

    resolved = reconciled[
        reconciled[
            "taxonomy_reconciliation_status"
        ] == "resolved"
    ].copy()

    alias_lookup = {}

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

        if accepted_name not in alias_lookup:
            alias_lookup[
                accepted_name
            ] = []

        for column in alternate_columns:

            alternate_name = clean_text(
                row.get(column)
            )

            if not alternate_name:
                continue

            if alternate_name in {
                "?",
                "-",
                "NA",
                "N/A",
            }:
                continue

            if (
                alternate_name
                == accepted_name
            ):
                continue

            if (
                alternate_name
                not in alias_lookup[
                    accepted_name
                ]
            ):
                alias_lookup[
                    accepted_name
                ].append(
                    alternate_name
                )

    return alias_lookup


# ============================================================
# INATURALIST TAXON LOOKUP
# ============================================================

def get_inaturalist_taxon(
    session,
    scientific_name,
):
    """
    Search iNaturalist and require an exact scientific-name match.
    """

    params = {
        "q": scientific_name,
        "is_active": "true",
        "per_page": 30,
    }

    response = session.get(
        INAT_TAXA_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    results = data.get(
        "results",
        [],
    )

    for taxon in results:

        returned_name = clean_text(
            taxon.get(
                "name"
            )
        )

        if (
            returned_name.casefold()
            == scientific_name.casefold()
        ):
            return taxon

    return None


def get_inaturalist_taxon_with_fallback(
    session,
    register_scientific_name,
    alias_lookup,
):
    """
    Try the accepted Species Register name first.

    If there is no exact iNaturalist match, try known aliases.
    """

    names_to_try = [
        register_scientific_name
    ]

    for alias in alias_lookup.get(
        register_scientific_name,
        [],
    ):
        if alias not in names_to_try:
            names_to_try.append(
                alias
            )

    for attempt_number, query_name in enumerate(
        names_to_try,
        start=1,
    ):

        taxon = get_inaturalist_taxon(
            session,
            query_name,
        )

        if taxon is not None:

            return {
                "taxon": taxon,
                "query_name": query_name,
                "match_method": (
                    "accepted_name"
                    if attempt_number == 1
                    else "alternate_name"
                ),
            }

    return {
        "taxon": None,
        "query_name": names_to_try[-1],
        "match_method": "not_found",
    }


# ============================================================
# PHOTO
# ============================================================

def extract_photo_data(
    taxon,
):
    """
    Return the iNaturalist default photo only when its license
    is included in our conservative automatic reuse list.
    """

    default_photo = taxon.get(
        "default_photo"
    )

    if not default_photo:
        return {
            "photo_status":
                "no_photo",
            "photo_url":
                None,
            "photo_id":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
        }

    license_code = clean_text(
        default_photo.get(
            "license_code"
        )
    ).lower()

    medium_url = clean_text(
        default_photo.get(
            "medium_url"
        )
    )

    attribution = clean_text(
        default_photo.get(
            "attribution"
        )
    )

    photo_id = default_photo.get(
        "id"
    )

    if (
        license_code
        not in ALLOWED_PHOTO_LICENSES
    ):
        return {
            "photo_status":
                "license_not_accepted",
            "photo_url":
                None,
            "photo_id":
                photo_id,
            "photo_license":
                license_code or None,
            "photo_attribution":
                attribution or None,
        }

    if not medium_url:
        return {
            "photo_status":
                "no_photo_url",
            "photo_url":
                None,
            "photo_id":
                photo_id,
            "photo_license":
                license_code,
            "photo_attribution":
                attribution or None,
        }

    return {
        "photo_status":
            "reusable_photo_found",
        "photo_url":
            medium_url,
        "photo_id":
            photo_id,
        "photo_license":
            license_code,
        "photo_attribution":
            attribution or None,
    }


# ============================================================
# WIKIPEDIA
# ============================================================

def get_wikipedia_title(
    wikipedia_url,
):
    if not wikipedia_url:
        return None

    parsed = urlparse(
        wikipedia_url
    )

    if (
        "wikipedia.org"
        not in parsed.netloc
    ):
        return None

    prefix = "/wiki/"

    if prefix not in parsed.path:
        return None

    title = parsed.path.split(
        prefix,
        1,
    )[1]

    return unquote(title)


def get_wikipedia_summary(
    session,
    wikipedia_url,
):
    title = get_wikipedia_title(
        wikipedia_url
    )

    if not title:
        return None

    url = (
        f"{WIKIPEDIA_SUMMARY_URL}/"
        f"{title}"
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    data = response.json()

    return clean_text(
        data.get(
            "extract"
        )
    )


# ============================================================
# FUN FACT SELECTION
# ============================================================

FUN_FACT_KEYWORDS = {
    "known": 4,
    "unlike": 5,
    "distinctive": 3,
    "feeds": 3,
    "feeding": 3,
    "diet": 2,
    "breeds": 3,
    "breeding": 3,
    "nest": 3,
    "nests": 3,
    "migrates": 3,
    "migration": 3,
    "migratory": 3,
    "calls": 2,
    "call": 2,
    "plumage": 2,
    "male": 2,
    "female": 2,
    "males": 2,
    "females": 2,
    "nocturnal": 4,
    "diurnal": 4,
    "endemic": 4,
    "forages": 3,
    "foraging": 3,
    "flight": 2,
    "tail": 1,
    "bill": 1,
    "colour": 1,
    "color": 1,
}


def split_sentences(
    summary,
):
    if not summary:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        summary,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def score_fun_fact_sentence(
    sentence,
    index,
):
    lower = sentence.lower()

    score = 0

    for keyword, weight in (
        FUN_FACT_KEYWORDS.items()
    ):
        if keyword in lower:
            score += weight

    # The first sentence is usually just a taxonomic definition.
    if index == 0:
        score -= 5

    generic_phrases = [
        " is a species of ",
        " is a bird in ",
        " is a fish in ",
        " is a plant in ",
        " is a genus of ",
        " belongs to the family ",
    ]

    for phrase in generic_phrases:
        if phrase in lower:
            score -= 4

    length = len(sentence)

    if 60 <= length <= 220:
        score += 3

    elif length > 300:
        score -= 3

    elif length < 40:
        score -= 2

    return score


def make_fun_fact_candidate(
    summary,
):
    """
    Select a more distinctive sentence from the source summary.

    This is still treated as a candidate for review rather than
    an independent biological claim generated by the pipeline.
    """

    sentences = split_sentences(
        summary
    )

    if not sentences:
        return None

    scored = []

    for index, sentence in enumerate(
        sentences
    ):
        scored.append(
            (
                score_fun_fact_sentence(
                    sentence,
                    index,
                ),
                index,
                sentence,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            -item[1],
        ),
        reverse=True,
    )

    best_score, _, best_sentence = (
        scored[0]
    )

    if best_score <= 0:
        return None

    if not best_sentence.endswith(
        (
            ".",
            "!",
            "?",
        )
    ):
        best_sentence += "."

    return best_sentence


# ============================================================
# ENRICH ONE SPECIES
# ============================================================

def enrich_species(
    session,
    scientific_name,
    alias_lookup,
):
    lookup = (
        get_inaturalist_taxon_with_fallback(
            session,
            scientific_name,
            alias_lookup,
        )
    )

    taxon = lookup.get(
        "taxon"
    )

    if taxon is None:
        return {
            "register_scientific_name":
                scientific_name,
            "inat_query_name":
                lookup.get(
                    "query_name"
                ),
            "inat_match_method":
                lookup.get(
                    "match_method"
                ),
            "inat_taxon_id":
                None,
            "inat_scientific_name":
                None,
            "inat_common_name":
                None,
            "photo_status":
                "not_run",
            "photo_url":
                None,
            "photo_id":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "wikipedia_url":
                None,
            "fun_fact":
                None,
            "fun_fact_status":
                "no_taxon_match",
        }

    photo = extract_photo_data(
        taxon
    )

    wikipedia_url = clean_text(
        taxon.get(
            "wikipedia_url"
        )
    )

    summary = (
        get_wikipedia_summary(
            session,
            wikipedia_url,
        )
    )

    fun_fact = (
        make_fun_fact_candidate(
            summary
        )
    )

    return {
        "register_scientific_name":
            scientific_name,
        "inat_query_name":
            lookup.get(
                "query_name"
            ),
        "inat_match_method":
            lookup.get(
                "match_method"
            ),
        "inat_taxon_id":
            taxon.get(
                "id"
            ),
        "inat_scientific_name":
            taxon.get(
                "name"
            ),
        "inat_common_name":
            taxon.get(
                "preferred_common_name"
            ),
        "photo_status":
            photo.get(
                "photo_status"
            ),
        "photo_url":
            photo.get(
                "photo_url"
            ),
        "photo_id":
            photo.get(
                "photo_id"
            ),
        "photo_license":
            photo.get(
                "photo_license"
            ),
        "photo_attribution":
            photo.get(
                "photo_attribution"
            ),
        "wikipedia_url":
            wikipedia_url or None,
        "fun_fact":
            fun_fact,
        "fun_fact_status":
            (
                "candidate_found"
                if fun_fact
                else "no_candidate"
            ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "SPECIES REGISTER PHOTO + FUN FACT ENRICHMENT"
    )
    print("=" * 70)

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
        if clean_text(
            row.get(
                "scientific_name"
            )
        )
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
        f"Records in this run: "
        f"{len(queryable_indices)}"
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

        if scientific_name in cache:

            print(
                "  Using cached result."
            )

            result = cache[
                scientific_name
            ]

        else:

            try:

                result = enrich_species(
                    session,
                    scientific_name,
                    alias_lookup,
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
                    "register_scientific_name":
                        scientific_name,
                    "inat_query_name":
                        scientific_name,
                    "inat_match_method":
                        "request_error",
                    "inat_taxon_id":
                        None,
                    "inat_scientific_name":
                        None,
                    "inat_common_name":
                        None,
                    "photo_status":
                        "request_error",
                    "photo_url":
                        None,
                    "photo_id":
                        None,
                    "photo_license":
                        None,
                    "photo_attribution":
                        None,
                    "wikipedia_url":
                        None,
                    "fun_fact":
                        None,
                    "fun_fact_status":
                        "request_error",
                }

        photo_url = result.get(
            "photo_url"
        )

        fun_fact = result.get(
            "fun_fact"
        )

        if photo_url:
            register.at[
                index,
                "photo_url",
            ] = photo_url

        if fun_fact:
            register.at[
                index,
                "fun_fact",
            ] = fun_fact

        print(
            "  iNaturalist match: "
            f"{result.get('inat_match_method')}"
        )

        print(
            "  Photo: "
            f"{result.get('photo_status')}"
        )

        print(
            "  Fun fact: "
            f"{result.get('fun_fact_status')}"
        )

        if fun_fact:
            print(
                f"  Candidate: "
                f"{fun_fact}"
            )

        audit_records.append(
            result
        )

    # ========================================================
    # SAVE REGISTER
    # ========================================================

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
        "PHOTO + FUN FACT ENRICHMENT COMPLETE"
    )

    print(
        "=" * 70
    )

    if not audit.empty:

        print(
            "\niNaturalist matches:"
        )

        print(
            audit[
                "inat_match_method"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        print(
            "\nPhoto results:"
        )

        print(
            audit[
                "photo_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        print(
            "\nFun fact results:"
        )

        print(
            audit[
                "fun_fact_status"
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
            f"{TEST_LIMIT} records "
            f"were processed."
        )


if __name__ == "__main__":
    main()