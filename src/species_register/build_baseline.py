from pathlib import Path
import json

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference_reconciled.csv"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_baseline.csv"
)

OUTPUT_XLSX = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "species_register_baseline.xlsx"
)


FINAL_COLUMNS = [
    "common_name",
    "scientific_name",
    "group",
    "properties",
    "status",
    "references",
    "photo_url",
    "fun_fact",
    "iucn_status",
]


GROUP_LABELS = {
    "birds": "Birds",
    "mammals": "Mammals",
    "reptiles": "Reptiles",
    "butterflies": "Butterflies",
    "dragonflies": "Dragonflies",
    "other_invertebrates": "Other Invertebrates",
    "terrestrial_plants": "Terrestrial Plants",
    "marine_fish": "Marine Fish",
    "fish": "Marine Fish",
    "marine_invertebrates": "Marine Invertebrates",
    "mixed_marine_fauna": "Other Marine Fauna",
    "marine_plants": "Marine Plants",
    "marine_algae": "Marine Algae",
}


PROPERTY_ORDER = {
    "Cempedak": 0,
    "Nikoi": 1,
}


def clean_text(value):
    """Return a clean string while safely handling missing values."""
    if pd.isna(value):
        return ""

    return " ".join(str(value).strip().split())


def clean_common_name(value):
    """
    Standardise common-name presentation.

    This only changes presentation/capitalisation.
    It does not attempt to change biological identity.
    """
    value = clean_text(value)

    if not value:
        return ""

    words = []

    for word in value.split():
        lower = word.lower()

        if lower in {"sp.", "spp."}:
            words.append(lower)
            continue

        # Capitalise hyphenated words cleanly.
        parts = word.split("-")
        parts = [
            part[:1].upper() + part[1:] if part else part
            for part in parts
        ]

        words.append("-".join(parts))

    return " ".join(words)


def get_group_label(raw_group):
    raw_group = clean_text(raw_group)

    if not raw_group:
        return ""

    return GROUP_LABELS.get(
        raw_group,
        raw_group.replace("_", " ").title(),
    )


def valid_scientific_name(value):
    value = clean_text(value)

    if not value:
        return ""

    if value in {"?", "-", "NA", "N/A"}:
        return ""

    return value


def get_identity_key(row):
    """
    Determine how records should be grouped into Species Register entries.

    Resolved taxonomy:
        accepted taxon ID is the stable identity.

    Review taxonomy:
        preserve the supplied scientific identification rather than
        automatically adopting an unapproved proposed match.

    Unresolved taxonomy:
        preserve the source identification separately.
    """

    reconciliation_status = clean_text(
        row.get("taxonomy_reconciliation_status")
    )

    group = clean_text(row.get("taxon_group")).lower()

    if reconciliation_status == "resolved":
        taxon_id = clean_text(row.get("accepted_taxon_id"))

        if taxon_id:
            return ("resolved_taxon", taxon_id)

        accepted_name = valid_scientific_name(
            row.get("accepted_scientific_name")
        )

        return (
            "resolved_name",
            accepted_name.lower(),
            group,
        )

    supplied_scientific_name = (
        valid_scientific_name(row.get("scientific_name_candidate"))
        or valid_scientific_name(row.get("scientific_name_normalized"))
        or valid_scientific_name(row.get("scientific_name_raw"))
    )

    if supplied_scientific_name:
        return (
            reconciliation_status or "unresolved",
            supplied_scientific_name.lower(),
            group,
        )

    common_name = (
        clean_text(row.get("common_name_normalized"))
        or clean_text(row.get("common_name_raw"))
    )

    return (
        reconciliation_status or "unresolved",
        common_name.lower(),
        group,
    )


def get_scientific_name(rows):
    """
    Use accepted taxonomy only where reconciliation was resolved.

    Review/unresolved records retain the supplied identification.
    """

    for _, row in rows.iterrows():
        if clean_text(
            row.get("taxonomy_reconciliation_status")
        ) == "resolved":
            accepted = valid_scientific_name(
                row.get("accepted_scientific_name")
            )

            if accepted:
                return accepted

    for _, row in rows.iterrows():
        candidate = (
            valid_scientific_name(row.get("scientific_name_candidate"))
            or valid_scientific_name(
                row.get("scientific_name_normalized")
            )
            or valid_scientific_name(row.get("scientific_name_raw"))
        )

        if candidate:
            return candidate

    return ""


def get_common_name(rows):
    """
    Preserve the supplied common name, with presentation cleaned.
    """

    for _, row in rows.iterrows():
        common_name = (
            clean_text(row.get("common_name_normalized"))
            or clean_text(row.get("common_name_raw"))
        )

        if common_name:
            return clean_common_name(common_name)

    return ""


def get_properties(rows):
    """
    Return properties in the same array-style structure used by
    the Species Register frontend.
    """

    properties = {
        clean_text(value)
        for value in rows["island"]
        if clean_text(value)
    }

    properties = sorted(
        properties,
        key=lambda x: (
            PROPERTY_ORDER.get(x, 99),
            x,
        ),
    )

    return json.dumps(properties, ensure_ascii=False)


def get_register_status(rows):
    """
    Species Register status is deliberately kept separate from
    taxonomy reconciliation status.

    Existing baseline records start as Provisional because they
    originated from the supplied species lists.

    Records without a usable scientific identification are marked
    Unresolved.
    """

    scientific_name = get_scientific_name(rows)

    if not scientific_name:
        return "Unresolved"

    return "Provisional"


def build_register():
    print("=" * 70)
    print("BUILDING SPECIES REGISTER BASELINE")
    print("=" * 70)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_PATH}"
        )

    source = pd.read_csv(INPUT_PATH)

    print(f"\nSource rows: {len(source)}")

    source["_register_identity"] = source.apply(
        get_identity_key,
        axis=1,
    )

    register_records = []

    for _, rows in source.groupby(
        "_register_identity",
        sort=False,
    ):
        raw_group = clean_text(
            rows.iloc[0].get("taxon_group")
        )

        register_records.append(
            {
                "common_name": get_common_name(rows),
                "scientific_name": get_scientific_name(rows),
                "group": get_group_label(raw_group),
                "properties": get_properties(rows),

                # Register-level status.
                "status": get_register_status(rows),

                # Baseline records do not originate from BirdNET.
                # New candidates can later carry BirdNET /
                # EarthRanger URLs here.
                "references": json.dumps([]),

                # Enrichment fields.
                "photo_url": "",
                "fun_fact": "",
                "iucn_status": "",
            }
        )

    register = pd.DataFrame(
        register_records,
        columns=FINAL_COLUMNS,
    )

    register = register.sort_values(
        by=[
            "group",
            "common_name",
            "scientific_name",
        ],
        na_position="last",
    ).reset_index(drop=True)

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
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

    print(f"Register records: {len(register)}")

    print("\nStatus:")
    print(
        register["status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nGroups:")
    print(
        register["group"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nFinal fields:")
    for column in FINAL_COLUMNS:
        print(f"  - {column}")

    print("\nEnrichment fields currently blank:")
    print("  - photo_url")
    print("  - fun_fact")
    print("  - iucn_status")

    print("\nSaved:")
    print(f"  CSV:  {OUTPUT_CSV}")
    print(f"  XLSX: {OUTPUT_XLSX}")

    print("\n" + "=" * 70)
    print("BASELINE BUILD COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    build_register()