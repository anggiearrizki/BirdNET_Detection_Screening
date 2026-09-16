"""Prepare scientific names for taxonomy reconciliation.

This script:
- preserves the original source identification;
- prepares safe taxonomy query names;
- records the taxonomic resolution of the source identification;
- keeps uncertain or ambiguous records for review;
- does not silently correct taxonomy.
"""

from pathlib import Path
import re
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REFERENCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "taxonomy_query_queue.csv"
)


# ---------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------

BINOMIAL_PATTERN = re.compile(
    r"^([A-Z][A-Za-z-]+)\s+([a-z][A-Za-z-]+)"
)

TRINOMIAL_PATTERN = re.compile(
    r"^([A-Z][A-Za-z-]+)\s+"
    r"([a-z][A-Za-z-]+)\s+"
    r"([a-z][A-Za-z-]+)"
)

UNCERTAINTY_PATTERN = re.compile(
    r"\?|"
    r"\bprob(?:ably)?\.?\b|"
    r"\bpossible\b|"
    r"\bcf\.?\b|"
    r"\baff\.?\b",
    flags=re.IGNORECASE,
)

ALTERNATIVE_ID_PATTERN = re.compile(
    r"\bcould\s+be\b|"
    r"\bpossibly\s+also\b",
    flags=re.IGNORECASE,
)

NON_TAXONOMIC_PATTERN = re.compile(
    r"^\s*at\s+least\b|"
    r"\bspecies[-\s]*unidentified\b|"
    r"\bunidentified\s+species\b",
    flags=re.IGNORECASE,
)

FAMILY_PATTERN = re.compile(
    r"^\s*family\s*:\s*([A-Z][A-Za-z-]+)\s*$",
    flags=re.IGNORECASE,
)

ORDER_PATTERN = re.compile(
    r"^\s*order\s*:\s*([A-Z][A-Za-z-]+)\s*$",
    flags=re.IGNORECASE,
)

# Standard genus-level identifications:
# Eurema sp.
# Clathria spp.
# Oxypora sp.(name may have changed)
GENUS_SP_PATTERN = re.compile(
    r"^([A-Z][A-Za-z-]+)\s+"
    r"(spp?)"
    r"(?:\.)?"
    r"(?=\s|\(|\[|\*|\?|$)"
    r"\s*(.*)$"
)

# Malformed source formatting:
# Junceellasp.
# Podabaciasp.
# Comastersp.
MALFORMED_GENUS_SP_PATTERN = re.compile(
    r"^([A-Z][A-Za-z-]+?)"
    r"(spp?)\."
    r"(?=\s|\(|\[|\*|\?|$)"
    r"\s*(.*)$"
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def clean_text(value):
    """Return stripped text or None."""

    if pd.isna(value):
        return None

    text = str(value).strip()

    return text if text else None


def unresolved_result(status, notes):
    """Return a standard unresolved query result."""

    return {
        "taxonomy_query_name": None,
        "source_identification_rank": "unresolved",
        "query_eligible": False,
        "query_preparation_status": status,
        "source_identification_uncertain": True,
        "query_notes": notes,
    }


def prepare_query(candidate):
    """Prepare one source identification for taxonomy matching."""

    candidate = clean_text(candidate)

    # --------------------------------------------------------------
    # No usable scientific-name candidate.
    # --------------------------------------------------------------

    if candidate is None:
        return unresolved_result(
            "no_candidate",
            "No scientific-name candidate available.",
        )

    if candidate == "?":
        return unresolved_result(
            "unresolved_source_identification",
            "Source contains no usable scientific identification.",
        )

    # --------------------------------------------------------------
    # Reject descriptive text that only looks like a binomial.
    # --------------------------------------------------------------

    if NON_TAXONOMIC_PATTERN.search(candidate):
        return unresolved_result(
            "manual_review",
            "Source value is descriptive text, not a taxonomic name.",
        )

    # --------------------------------------------------------------
    # Alternative identifications must stay unresolved.
    # --------------------------------------------------------------

    if ALTERNATIVE_ID_PATTERN.search(candidate):
        return unresolved_result(
            "manual_review",
            "Source contains an alternative identification.",
        )

    # --------------------------------------------------------------
    # Explicit family-level identification.
    # --------------------------------------------------------------

    family_match = FAMILY_PATTERN.match(candidate)

    if family_match:
        return {
            "taxonomy_query_name": family_match.group(1),
            "source_identification_rank": "family",
            "query_eligible": True,
            "query_preparation_status": "ready_higher_rank",
            "source_identification_uncertain": False,
            "query_notes": (
                "Source identification is resolved to family level."
            ),
        }

    # --------------------------------------------------------------
    # Explicit order-level identification.
    # --------------------------------------------------------------

    order_match = ORDER_PATTERN.match(candidate)

    if order_match:
        return {
            "taxonomy_query_name": order_match.group(1),
            "source_identification_rank": "order",
            "query_eligible": True,
            "query_preparation_status": "ready_higher_rank",
            "source_identification_uncertain": False,
            "query_notes": (
                "Source identification is resolved to order level."
            ),
        }

    # --------------------------------------------------------------
    # Genus-level records using sp. / spp.
    # --------------------------------------------------------------

    genus_match = GENUS_SP_PATTERN.match(candidate)

    if genus_match is None:
        genus_match = MALFORMED_GENUS_SP_PATTERN.match(candidate)

    if genus_match:
        genus_name = genus_match.group(1)

        annotation = (
            genus_match.group(3)
            if len(genus_match.groups()) >= 3
            else ""
        )

        annotation = clean_text(annotation)

        has_annotation = annotation is not None

        if has_annotation:
            preparation_status = (
                "ready_higher_rank_with_annotation"
            )

            notes = (
                "Genus-level identification extracted while "
                "preserving the source annotation separately."
            )
        else:
            preparation_status = "ready_higher_rank"

            notes = (
                "Source identification is resolved to genus level."
            )

        return {
            "taxonomy_query_name": genus_name,
            "source_identification_rank": "genus",
            "query_eligible": True,
            "query_preparation_status": preparation_status,
            "source_identification_uncertain": has_annotation,
            "query_notes": notes,
        }

    # --------------------------------------------------------------
    # cf. / aff. indicate tentative identification.
    # Keep these for manual review rather than forcing a match.
    # --------------------------------------------------------------

    if re.search(
        r"\bcf\.?\b|\baff\.?\b",
        candidate,
        flags=re.IGNORECASE,
    ):
        return unresolved_result(
            "manual_review",
            "Tentative cf./aff. identification requires review.",
        )

    # --------------------------------------------------------------
    # Trinomial identification.
    # Example: Anthene emolus goberus
    # --------------------------------------------------------------

    trinomial_match = TRINOMIAL_PATTERN.match(candidate)

    if trinomial_match:
        query_name = " ".join(
            trinomial_match.groups()
        )

        uncertain = bool(
            UNCERTAINTY_PATTERN.search(candidate)
        )

        if candidate == query_name:
            status = "ready"
            notes = (
                "Subspecies name ready for taxonomy matching."
            )
        else:
            status = "ready_with_annotation_removed"
            notes = (
                "A leading trinomial was extracted while "
                "preserving the complete source value separately."
            )

        return {
            "taxonomy_query_name": query_name,
            "source_identification_rank": "subspecies",
            "query_eligible": True,
            "query_preparation_status": status,
            "source_identification_uncertain": uncertain,
            "query_notes": notes,
        }

    # --------------------------------------------------------------
    # Species-level identification.
    # --------------------------------------------------------------

    binomial_match = BINOMIAL_PATTERN.match(candidate)

    if not binomial_match:
        return unresolved_result(
            "manual_review",
            "Could not safely extract a taxonomic query name.",
        )

    query_name = (
        f"{binomial_match.group(1)} "
        f"{binomial_match.group(2)}"
    )

    uncertain = bool(
        UNCERTAINTY_PATTERN.search(candidate)
    )

    if candidate == query_name:
        status = "ready"

        notes = (
            "Scientific name ready for taxonomy matching."
        )

    else:
        status = "ready_with_annotation_removed"

        notes = (
            "A leading binomial was extracted while preserving "
            "the complete source value separately."
        )

    return {
        "taxonomy_query_name": query_name,
        "source_identification_rank": "species",
        "query_eligible": True,
        "query_preparation_status": status,
        "source_identification_uncertain": uncertain,
        "query_notes": notes,
    }


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    df = pd.read_csv(REFERENCE_PATH)

    prepared = (
        df["scientific_name_candidate"]
        .apply(prepare_query)
    )

    prepared_df = pd.DataFrame(
        prepared.tolist()
    )

    result = pd.concat(
        [df, prepared_df],
        axis=1,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 70)
    print("TAXONOMY QUERY PREPARATION")
    print("=" * 70)

    print(f"\nTotal records: {len(result)}")

    print("\nQuery preparation status:")
    print(
        result["query_preparation_status"]
        .value_counts(dropna=False)
    )

    print("\nSource identification rank:")
    print(
        result["source_identification_rank"]
        .value_counts(dropna=False)
    )

    eligible = result[
        result["query_eligible"] == True
    ]

    print(
        f"\nEligible records: "
        f"{len(eligible)}"
    )

    print(
        "Unique eligible scientific names: "
        f"{eligible['taxonomy_query_name'].nunique()}"
    )

    unresolved = result[
        result["query_eligible"] == False
    ]

    print(
        f"\nUnresolved/manual-review records: "
        f"{len(unresolved)}"
    )

    if not unresolved.empty:

        print("\nUnresolved examples:")

        print(
            unresolved[
                [
                    "source_sheet",
                    "source_row",
                    "common_name_raw",
                    "scientific_name_candidate",
                    "query_preparation_status",
                    "query_notes",
                ]
            ]
            .head(30)
            .to_string(index=False)
        )

    print("\nSaved taxonomy query queue to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()