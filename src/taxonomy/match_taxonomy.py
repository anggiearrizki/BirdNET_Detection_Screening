"""Match prepared biodiversity names against Catalogue of Life XR.

This script:
- reads only taxonomy-query-eligible records;
- matches each unique taxonomic query once;
- supplies the source identification rank to the matcher;
- preserves key API match fields for later review;
- classifies matches as candidate-resolved, review, unresolved, or request error;
- does not automatically overwrite the local reference.
"""

from pathlib import Path
import time

import pandas as pd
import requests

from taxonomy_config import (
    GBIF_MATCH_API,
    COL_XR_CHECKLIST_KEY,
    TAXONOMY_SOURCE,
    REQUEST_TIMEOUT_SECONDS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

QUERY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "taxonomy_query_queue.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "taxonomy_match_results.csv"
)


def match_name(session, query_name, identification_rank):
    """Match one taxonomic query against COL XR."""

    params = {
        "scientificName": query_name,
        "taxonRank": identification_rank,
        "checklistKey": COL_XR_CHECKLIST_KEY,
    }

    response = session.get(
        GBIF_MATCH_API,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    return response.json()


def extract_match_result(query_name, identification_rank, response):
    """Extract a compact set of fields from the API response."""

    usage = response.get("usage") or {}
    accepted_usage = response.get("acceptedUsage") or {}
    diagnostics = response.get("diagnostics") or {}

    issues = response.get("issues") or []

    if not isinstance(issues, list):
        issues = [str(issues)]

    accepted_taxon_id = (
        accepted_usage.get("key")
        or usage.get("key")
    )

    accepted_scientific_name = (
        accepted_usage.get("canonicalName")
        or accepted_usage.get("name")
        or usage.get("canonicalName")
        or usage.get("name")
    )

    accepted_rank = (
        accepted_usage.get("rank")
        or usage.get("rank")
    )

    return {
        "taxonomy_query_name": query_name,
        "source_identification_rank": identification_rank,

        # GBIF v2 matching diagnostics.
        "match_type": diagnostics.get("matchType"),
        "confidence": diagnostics.get("confidence"),

        # Name actually matched by the service.
        "matched_taxon_id": usage.get("key"),
        "matched_name": usage.get("name"),
        "matched_canonical_name": usage.get("canonicalName"),
        "matched_rank": usage.get("rank"),
        "matched_status": usage.get("status"),

        # Accepted taxonomic concept.
        "accepted_taxon_id": accepted_taxon_id,
        "accepted_scientific_name": accepted_scientific_name,
        "accepted_rank": accepted_rank,

        "taxonomic_status": (
            response.get("taxonomicStatus")
            or usage.get("status")
        ),

        "synonym": response.get("synonym"),

        "taxonomy_source": TAXONOMY_SOURCE,

        "match_issues": " | ".join(issues),
    }


def classify_reconciliation(result):
    """Classify whether a taxonomy match is safe to use or needs review."""

    match_type = str(
        result.get("match_type") or ""
    ).upper()

    source_rank = str(
        result.get("source_identification_rank") or ""
    ).lower()

    accepted_rank = str(
        result.get("accepted_rank")
        or result.get("matched_rank")
        or ""
    ).lower()

    # API/network failure.
    if match_type == "REQUEST_ERROR":
        return {
            "reconciliation_status": "request_error",
            "reconciliation_reason": (
                "Taxonomy service request failed."
            ),
        }

    # No accepted concept returned.
    if not result.get("accepted_taxon_id"):
        return {
            "reconciliation_status": "unresolved",
            "reconciliation_reason": (
                "No accepted taxonomic concept was returned."
            ),
        }

    # Do not silently accept rank fallback.
    if source_rank != accepted_rank:
        return {
            "reconciliation_status": "review",
            "reconciliation_reason": (
                f"Taxonomic rank mismatch: "
                f"source={source_rank}, matched={accepted_rank}."
            ),
        }

    # Fuzzy or non-exact matching requires review.
    if match_type != "EXACT":
        return {
            "reconciliation_status": "review",
            "reconciliation_reason": (
                f"Non-exact taxonomy match: "
                f"{match_type or 'unknown'}."
            ),
        }

    return {
        "reconciliation_status": "candidate_resolved",
        "reconciliation_reason": (
            "Exact taxonomy match at the expected identification rank."
        ),
    }


def main():
    df = pd.read_csv(QUERY_PATH)

    eligible = df[
        df["query_eligible"] == True
    ].copy()

    unique_queries = (
        eligible[
            [
                "taxonomy_query_name",
                "source_identification_rank",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "source_identification_rank",
                "taxonomy_query_name",
            ]
        )
        .reset_index(drop=True)
    )

    print("=" * 70)
    print("COL XR TAXONOMY MATCHING")
    print("=" * 70)

    print(f"\nEligible source records: {len(eligible)}")
    print(f"Unique taxonomic queries: {len(unique_queries)}")

    session = requests.Session()

    results = []

    for index, row in unique_queries.iterrows():

        query_name = row["taxonomy_query_name"]
        identification_rank = row[
            "source_identification_rank"
        ]

        print(
            f"[{index + 1}/{len(unique_queries)}] "
            f"{query_name} ({identification_rank})"
        )

        try:
            response = match_name(
                session,
                query_name,
                identification_rank,
            )

            result = extract_match_result(
                query_name,
                identification_rank,
                response,
            )

            result.update(
                classify_reconciliation(result)
            )

        except requests.RequestException as exc:

            result = {
                "taxonomy_query_name": query_name,
                "source_identification_rank": identification_rank,

                "match_type": "REQUEST_ERROR",
                "confidence": None,

                "matched_taxon_id": None,
                "matched_name": None,
                "matched_canonical_name": None,
                "matched_rank": None,
                "matched_status": None,

                "accepted_taxon_id": None,
                "accepted_scientific_name": None,
                "accepted_rank": None,

                "taxonomic_status": None,
                "synonym": None,

                "taxonomy_source": TAXONOMY_SOURCE,

                "match_issues": str(exc),

                "reconciliation_status": "request_error",
                "reconciliation_reason": (
                    "Taxonomy service request failed."
                ),
            }

        results.append(result)

        # Be polite to the public API.
        time.sleep(0.1)

    result_df = pd.DataFrame(results)

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 70)
    print("MATCHING COMPLETE")
    print("=" * 70)

    print("\nMatch types:")
    print(
        result_df["match_type"]
        .value_counts(dropna=False)
    )

    print("\nMatched ranks:")
    print(
        result_df["matched_rank"]
        .value_counts(dropna=False)
    )

    print("\nReconciliation status:")
    print(
        result_df["reconciliation_status"]
        .value_counts(dropna=False)
    )

    print(f"\nSaved to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()