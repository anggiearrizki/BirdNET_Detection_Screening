from pathlib import Path
from urllib.parse import urlparse, unquote
import html
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

ENWIKI_API_URL = (
    "https://en.wikipedia.org/w/api.php"
)

COMMONS_API_URL = (
    "https://commons.wikimedia.org/w/api.php"
)

WIKIPEDIA_SUMMARY_URL = (
    "https://en.wikipedia.org/api/rest_v1/page/summary"
)

REQUEST_TIMEOUT = 30

REQUEST_DELAY_SECONDS = 0.5

# Keep this at 5 while validating.
# Change to None when ready for the full register.
TEST_LIMIT = None # validated

# Increment this if we significantly change enrichment logic.
CACHE_VERSION = 2

# Conservative automatic reuse policy.
ALLOWED_PHOTO_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
    "public_domain",
}


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
            "User-Agent":
                "BintanMPA-SpeciesRegister/1.0"
        }
    )

    return session


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_text(value):
    """
    Safely convert a value into a clean string.
    """

    if pd.isna(value):
        return ""

    return " ".join(
        str(value)
        .strip()
        .split()
    )


def clean_html_text(value):
    """
    Remove simple HTML formatting from Wikimedia metadata.
    """

    if not value:
        return ""

    value = re.sub(
        r"<[^>]+>",
        " ",
        str(value),
    )

    value = html.unescape(
        value
    )

    return " ".join(
        value.split()
    )


# ============================================================
# CACHE
# ============================================================

def load_cache():
    """
    Load cached enrichment results.
    """

    if not CACHE_PATH.exists():
        return {}

    try:
        with open(
            CACHE_PATH,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(
            data,
            dict,
        ):
            return {}

        return data

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}


def save_cache(cache):
    """
    Save enrichment results locally.
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


def cached_result_is_reusable(
    result,
):
    """
    Only reuse results generated with the current cache version.
    """

    if not isinstance(
        result,
        dict,
    ):
        return False

    return (
        result.get(
            "cache_version"
        )
        == CACHE_VERSION
    )


# ============================================================
# TAXONOMY ALIASES
# ============================================================

def build_alias_lookup():
    """
    Build alternate scientific-name mappings from the
    reconciled Phase 2 taxonomy.

    The accepted Species Register name remains unchanged.
    Alternate names are used only as fallback queries.
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


def names_to_try(
    scientific_name,
    alias_lookup,
):
    """
    Return accepted name first, followed by known aliases.
    """

    names = [
        scientific_name
    ]

    for alias in alias_lookup.get(
        scientific_name,
        [],
    ):
        if alias not in names:
            names.append(
                alias
            )

    return names


# ============================================================
# WIKIMEDIA LICENSE HANDLING
# ============================================================

def get_extmetadata_value(
    metadata,
    key,
):
    item = metadata.get(
        key,
        {}
    )

    return clean_html_text(
        item.get(
            "value"
        )
    )


def normalise_photo_license(
    value,
):
    """
    Convert Wikimedia license labels into our small accepted set.
    """

    value = clean_text(
        value
    ).lower()

    if not value:
        return None

    # Reject restrictive variants first.
    if (
        "by-nc" in value
        or "noncommercial" in value
        or "non-commercial" in value
        or "by-nd" in value
        or "no derivatives" in value
    ):
        return None

    if (
        "public domain" in value
        or value == "pd"
    ):
        return "public_domain"

    if "cc0" in value:
        return "cc0"

    if (
        "cc by-sa" in value
        or "attribution-share alike"
        in value
        or "attribution-sharealike"
        in value
    ):
        return "cc-by-sa"

    if (
        "cc by" in value
        or "creative commons attribution"
        in value
    ):
        return "cc-by"

    return None


# ============================================================
# WIKIMEDIA COMMONS PHOTO
# ============================================================

def get_wikimedia_photo(
    session,
    scientific_name,
):
    """
    Find the representative free image associated with the
    English Wikipedia page for a scientific name.

    Then inspect the corresponding Commons file metadata.
    """

    page_params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
        "prop": "pageimages",
        "titles": scientific_name,
        "piprop": "name|thumbnail",
        "pithumbsize": 800,
        "pilicense": "free",
    }

    response = session.get(
        ENWIKI_API_URL,
        params=page_params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    pages = (
        data
        .get("query", {})
        .get("pages", [])
    )

    if not pages:
        return {
            "photo_status":
                "wikimedia_page_not_found",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
            "wikimedia_file":
                None,
        }

    page = pages[0]

    if page.get(
        "missing"
    ) is not None:
        return {
            "photo_status":
                "wikimedia_page_not_found",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
            "wikimedia_file":
                None,
        }

    file_name = clean_text(
        page.get(
            "pageimage"
        )
    )

    if not file_name:
        return {
            "photo_status":
                "wikimedia_no_page_image",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
            "wikimedia_file":
                None,
        }

    commons_params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "imageinfo",
        "titles":
            f"File:{file_name}",
        "iiprop":
            "url|extmetadata",
        "iiurlwidth":
            800,
    }

    response = session.get(
        COMMONS_API_URL,
        params=commons_params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    commons_data = (
        response.json()
    )

    commons_pages = (
        commons_data
        .get("query", {})
        .get("pages", [])
    )

    if not commons_pages:
        return {
            "photo_status":
                "wikimedia_metadata_not_found",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
            "wikimedia_file":
                file_name,
        }

    commons_page = (
        commons_pages[0]
    )

    image_info_list = (
        commons_page.get(
            "imageinfo",
            [],
        )
    )

    if not image_info_list:
        return {
            "photo_status":
                "wikimedia_metadata_not_found",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
            "wikimedia_file":
                file_name,
        }

    image_info = (
        image_info_list[0]
    )

    metadata = image_info.get(
        "extmetadata",
        {},
    )

    raw_license = (
        get_extmetadata_value(
            metadata,
            "LicenseShortName",
        )
        or get_extmetadata_value(
            metadata,
            "UsageTerms",
        )
    )

    accepted_license = (
        normalise_photo_license(
            raw_license
        )
    )

    attribution = (
        get_extmetadata_value(
            metadata,
            "Artist",
        )
        or get_extmetadata_value(
            metadata,
            "Credit",
        )
    )

    photo_url = (
        image_info.get(
            "thumburl"
        )
        or image_info.get(
            "url"
        )
    )

    source_url = (
        image_info.get(
            "descriptionurl"
        )
    )

    if not accepted_license:
        return {
            "photo_status":
                "wikimedia_license_not_accepted",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                raw_license or None,
            "photo_attribution":
                attribution or None,
            "photo_source_url":
                source_url,
            "wikimedia_file":
                file_name,
        }

    if not photo_url:
        return {
            "photo_status":
                "wikimedia_no_photo_url",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                accepted_license,
            "photo_attribution":
                attribution or None,
            "photo_source_url":
                source_url,
            "wikimedia_file":
                file_name,
        }

    return {
        "photo_status":
            "reusable_photo_found",
        "photo_source":
            "wikimedia_commons",
        "photo_url":
            photo_url,
        "photo_license":
            accepted_license,
        "photo_attribution":
            attribution or None,
        "photo_source_url":
            source_url,
        "wikimedia_file":
            file_name,
    }


def get_wikimedia_photo_with_fallback(
    session,
    register_scientific_name,
    alias_lookup,
):
    """
    Try the accepted scientific name first, then taxonomy aliases.
    """

    tried_names = names_to_try(
        register_scientific_name,
        alias_lookup,
    )

    last_result = None

    for attempt_number, query_name in enumerate(
        tried_names,
        start=1,
    ):

        result = get_wikimedia_photo(
            session,
            query_name,
        )

        last_result = result

        if result.get(
            "photo_url"
        ):
            result[
                "wikimedia_query_name"
            ] = query_name

            result[
                "wikimedia_match_method"
            ] = (
                "accepted_name"
                if attempt_number == 1
                else "alternate_name"
            )

            return result

    if last_result is None:
        last_result = {
            "photo_status":
                "wikimedia_not_found",
            "photo_source":
                "wikimedia_commons",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
            "wikimedia_file":
                None,
        }

    last_result[
        "wikimedia_query_name"
    ] = tried_names[-1]

    last_result[
        "wikimedia_match_method"
    ] = "not_found"

    return last_result


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
    Try accepted name first, then known taxonomy aliases.
    """

    tried_names = names_to_try(
        register_scientific_name,
        alias_lookup,
    )

    for attempt_number, query_name in enumerate(
        tried_names,
        start=1,
    ):

        taxon = get_inaturalist_taxon(
            session,
            query_name,
        )

        if taxon is not None:
            return {
                "taxon":
                    taxon,
                "query_name":
                    query_name,
                "match_method":
                    (
                        "accepted_name"
                        if attempt_number == 1
                        else "alternate_name"
                    ),
            }

    return {
        "taxon":
            None,
        "query_name":
            tried_names[-1],
        "match_method":
            "not_found",
    }


# ============================================================
# INATURALIST PHOTO
# ============================================================

def extract_inaturalist_photo(
    taxon,
):
    """
    Return the iNaturalist default photo only when it uses
    one of our accepted reusable licenses.
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
    """
    Convert an English Wikipedia URL into a page title.
    """

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

    return unquote(
        title
    )


def get_wikipedia_summary_from_url(
    session,
    wikipedia_url,
):
    """
    Retrieve Wikipedia summary using an existing Wikipedia URL.
    """

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


def get_wikipedia_summary_by_name(
    session,
    scientific_name,
):
    """
    Fallback Wikipedia lookup directly from the scientific name.
    """

    title = scientific_name.replace(
        " ",
        "_",
    )

    url = (
        f"{WIKIPEDIA_SUMMARY_URL}/"
        f"{title}"
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 404:
        return {
            "summary":
                None,
            "wikipedia_url":
                None,
        }

    response.raise_for_status()

    data = response.json()

    summary = clean_text(
        data.get(
            "extract"
        )
    )

    page_url = (
        data
        .get("content_urls", {})
        .get("desktop", {})
        .get("page")
    )

    return {
        "summary":
            summary or None,
        "wikipedia_url":
            page_url,
    }


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
    "brood": 4,
    "parasite": 4,
    "parasitic": 4,
    "host": 3,
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

    # First sentence is commonly just a taxonomic introduction.
    if index == 0:
        score -= 5

    generic_phrases = [
        " is a species of ",
        " is a bird in ",
        " is a fish in ",
        " is a plant in ",
        " is a genus of ",
        " belongs to the family ",
        " is a flowering plant ",
    ]

    for phrase in generic_phrases:
        if phrase in lower:
            score -= 4

    length = len(
        sentence
    )

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
    Select a relatively distinctive source-backed sentence.

    It is treated as a candidate, not newly generated biological
    knowledge.
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
    """
    Enrich one Species Register record.

    Photo priority:
        1. Wikimedia Commons
        2. iNaturalist
        3. blank

    Fun fact source:
        Wikipedia summary associated with iNaturalist where
        possible, with direct Wikipedia-name fallback.
    """

    # --------------------------------------------------------
    # TAXON MATCH THROUGH INATURALIST
    # --------------------------------------------------------

    inat_lookup = (
        get_inaturalist_taxon_with_fallback(
            session,
            scientific_name,
            alias_lookup,
        )
    )

    taxon = inat_lookup.get(
        "taxon"
    )

    # --------------------------------------------------------
    # PHOTO SOURCE 1: WIKIMEDIA COMMONS
    # --------------------------------------------------------

    wikimedia_photo = (
        get_wikimedia_photo_with_fallback(
            session,
            scientific_name,
            alias_lookup,
        )
    )

    chosen_photo = None

    if wikimedia_photo.get(
        "photo_url"
    ):
        chosen_photo = {
            "photo_source":
                "wikimedia_commons",
            "photo_status":
                wikimedia_photo.get(
                    "photo_status"
                ),
            "photo_url":
                wikimedia_photo.get(
                    "photo_url"
                ),
            "photo_license":
                wikimedia_photo.get(
                    "photo_license"
                ),
            "photo_attribution":
                wikimedia_photo.get(
                    "photo_attribution"
                ),
            "photo_source_url":
                wikimedia_photo.get(
                    "photo_source_url"
                ),
        }

    # --------------------------------------------------------
    # PHOTO SOURCE 2: INATURALIST
    # --------------------------------------------------------

    inat_photo = {
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
    }

    if (
        chosen_photo is None
        and taxon is not None
    ):
        inat_photo = (
            extract_inaturalist_photo(
                taxon
            )
        )

        if inat_photo.get(
            "photo_url"
        ):
            photo_id = (
                inat_photo.get(
                    "photo_id"
                )
            )

            chosen_photo = {
                "photo_source":
                    "inaturalist",
                "photo_status":
                    inat_photo.get(
                        "photo_status"
                    ),
                "photo_url":
                    inat_photo.get(
                        "photo_url"
                    ),
                "photo_license":
                    inat_photo.get(
                        "photo_license"
                    ),
                "photo_attribution":
                    inat_photo.get(
                        "photo_attribution"
                    ),
                "photo_source_url":
                    (
                        f"https://www.inaturalist.org/photos/"
                        f"{photo_id}"
                        if photo_id
                        else None
                    ),
            }

    # --------------------------------------------------------
    # NO PHOTO FOUND
    # --------------------------------------------------------

    if chosen_photo is None:
        chosen_photo = {
            "photo_source":
                None,
            "photo_status":
                "no_reusable_photo_found",
            "photo_url":
                None,
            "photo_license":
                None,
            "photo_attribution":
                None,
            "photo_source_url":
                None,
        }

    # --------------------------------------------------------
    # FUN FACT
    # --------------------------------------------------------

    wikipedia_url = None
    summary = None

    if taxon is not None:

        wikipedia_url = clean_text(
            taxon.get(
                "wikipedia_url"
            )
        )

        if wikipedia_url:
            summary = (
                get_wikipedia_summary_from_url(
                    session,
                    wikipedia_url,
                )
            )

    # Direct Wikipedia fallback when iNaturalist has no
    # Wikipedia link or taxon match.
    if not summary:

        wikipedia_result = (
            get_wikipedia_summary_by_name(
                session,
                scientific_name,
            )
        )

        summary = (
            wikipedia_result.get(
                "summary"
            )
        )

        if not wikipedia_url:
            wikipedia_url = (
                wikipedia_result.get(
                    "wikipedia_url"
                )
            )

    fun_fact = (
        make_fun_fact_candidate(
            summary
        )
    )

    # --------------------------------------------------------
    # AUDIT RESULT
    # --------------------------------------------------------

    result = {
        "cache_version":
            CACHE_VERSION,

        "register_scientific_name":
            scientific_name,

        # iNaturalist taxon
        "inat_query_name":
            inat_lookup.get(
                "query_name"
            ),

        "inat_match_method":
            inat_lookup.get(
                "match_method"
            ),

        "inat_taxon_id":
            (
                taxon.get(
                    "id"
                )
                if taxon
                else None
            ),

        "inat_scientific_name":
            (
                taxon.get(
                    "name"
                )
                if taxon
                else None
            ),

        "inat_common_name":
            (
                taxon.get(
                    "preferred_common_name"
                )
                if taxon
                else None
            ),

        # Final selected photo
        "photo_source":
            chosen_photo.get(
                "photo_source"
            ),

        "photo_status":
            chosen_photo.get(
                "photo_status"
            ),

        "photo_url":
            chosen_photo.get(
                "photo_url"
            ),

        "photo_license":
            chosen_photo.get(
                "photo_license"
            ),

        "photo_attribution":
            chosen_photo.get(
                "photo_attribution"
            ),

        "photo_source_url":
            chosen_photo.get(
                "photo_source_url"
            ),

        # Wikimedia diagnostics
        "wikimedia_query_name":
            wikimedia_photo.get(
                "wikimedia_query_name"
            ),

        "wikimedia_match_method":
            wikimedia_photo.get(
                "wikimedia_match_method"
            ),

        "wikimedia_status":
            wikimedia_photo.get(
                "photo_status"
            ),

        "wikimedia_file":
            wikimedia_photo.get(
                "wikimedia_file"
            ),

        # iNaturalist photo diagnostics
        "inat_photo_status":
            inat_photo.get(
                "photo_status"
            ),

        "inat_photo_license":
            inat_photo.get(
                "photo_license"
            ),

        # Fun fact
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

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "SPECIES REGISTER PHOTO + FUN FACT ENRICHMENT"
    )
    print("=" * 70)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"IUCN-enriched Species Register not found:\n"
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

    register[
        "photo_url"
    ] = register[
        "photo_url"
    ].astype(
        "string"
    )

    register[
        "fun_fact"
    ] = register[
        "fun_fact"
    ].astype(
        "string"
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

        if cached_result_is_reusable(
            cached_result
        ):

            print(
                "  Using cached result."
            )

            result = cached_result

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
                    "cache_version":
                        CACHE_VERSION,

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

                    "photo_source":
                        None,

                    "photo_status":
                        "request_error",

                    "photo_url":
                        None,

                    "photo_license":
                        None,

                    "photo_attribution":
                        None,

                    "photo_source_url":
                        None,

                    "wikimedia_query_name":
                        scientific_name,

                    "wikimedia_match_method":
                        "request_error",

                    "wikimedia_status":
                        "request_error",

                    "wikimedia_file":
                        None,

                    "inat_photo_status":
                        "request_error",

                    "inat_photo_license":
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
            "  Photo source: "
            f"{result.get('photo_source')}"
        )

        print(
            "  Photo status: "
            f"{result.get('photo_status')}"
        )

        print(
            "  Photo license: "
            f"{result.get('photo_license')}"
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
    # SAVE FINAL 9-FIELD REGISTER
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
            "\nPhoto source summary:"
        )

        print(
            audit[
                "photo_source"
            ]
            .fillna(
                "None"
            )
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        print(
            "\nPhoto result summary:"
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

    total_photos = (
        register[
            "photo_url"
        ]
        .notna()
        .sum()
    )

    total_fun_facts = (
        register[
            "fun_fact"
        ]
        .notna()
        .sum()
    )

    print(
        f"\nRegister records: "
        f"{len(register)}"
    )

    print(
        f"Records with photo URL: "
        f"{total_photos}"
    )

    print(
        f"Records with fun fact: "
        f"{total_fun_facts}"
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