"""Load and standardise the Cempedak and Nikoi biodiversity reference.

The ingestion layer:
- reads only approved primary biodiversity sheets;
- preserves raw source names and provenance;
- handles different worksheet structures;
- derives only safe formatting-normalised fields;
- does NOT perform taxonomic correction.

Taxonomic reconciliation will be implemented later.
"""

from pathlib import Path
import re

import pandas as pd

from source_map import PRIMARY_BIODIVERSITY_SHEETS
from extraction_config import SHEET_EXTRACTION_CONFIG


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WORKBOOK_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "Species_List.xlsx"
)

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference.csv"
)

OUTPUT_XLSX = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "local_biodiversity_reference.xlsx"
)


# ---------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------

def get_cell(df: pd.DataFrame, row: int, column: int | None):
    """Safely retrieve a worksheet cell."""

    if column is None:
        return None

    if column >= df.shape[1]:
        return None

    value = df.iat[row, column]

    if pd.isna(value):
        return None

    return value


def raw_text(value):
    """Preserve a source value as text without correcting its meaning."""

    if value is None:
        return None

    return str(value)


def normalize_text(value):
    """Perform safe whitespace normalization only."""

    if value is None:
        return None

    text = str(value)

    # Replace repeated whitespace with one space.
    text = re.sub(r"\s+", " ", text)

    text = text.strip()

    return text if text else None


def normalize_scientific_candidate(value):
    """Normalize formatting without correcting taxonomy."""

    text = normalize_text(value)

    if text is None:
        return None

    # Remove enclosing parentheses only when the entire value is wrapped.
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()

    return text or None


def is_record_number(value) -> bool:
    """Return True when a cell looks like a numbered inventory record."""

    if value is None or pd.isna(value):
        return False

    if isinstance(value, bool):
        return False

    if isinstance(value, (int, float)):
        try:
            return float(value).is_integer()
        except (TypeError, ValueError):
            return False

    text = str(value).strip()

    return text.isdigit()


def extract_parenthetical_scientific_name(text):
    """Extract a likely binomial from parentheses without correcting it.

    Example:
        Hawksbill Turtle (Eretmochelys imbricata)
        -> Eretmochelys imbricata

    This is only a candidate extraction, not taxonomic validation.
    """

    if text is None:
        return None

    text = str(text)

    pattern = r"\(([A-Z][A-Za-z.-]+\s+[a-z][A-Za-z.-]+)\)"

    match = re.search(pattern, text)

    if match:
        return normalize_text(match.group(1))

    return None


def get_scientific_candidate(
    common_name_raw,
    scientific_name_raw,
):
    """Choose a scientific-name candidate while preserving original fields."""

    if scientific_name_raw:
        return (
            normalize_scientific_candidate(scientific_name_raw),
            "explicit_column",
        )

    embedded = extract_parenthetical_scientific_name(common_name_raw)

    if embedded:
        return embedded, "parenthetical_extraction"

    return None, "missing"


def is_heading_candidate(value) -> bool:
    """Identify likely source section headings in complex worksheets."""

    text = normalize_text(value)

    if not text:
        return False

    if len(text) > 150:
        return False

    ignored_prefixes = (
        "Total Number",
        "NB:",
        "N.B.",
        "PULAU ",
        "DIVE SITE KEY",
        "*",
        "**",
    )

    if text.startswith(ignored_prefixes):
        return False

    if text in {"A:", "B:", "C:", "D:", "E:"}:
        return False

    return True


# ---------------------------------------------------------------------
# Common record construction
# ---------------------------------------------------------------------

def build_record(
    *,
    sheet_name,
    source_row,
    parser_type,
    record_id=None,
    common_name_raw=None,
    scientific_name_raw=None,
    status_raw=None,
    source_section=None,
    site_presence=None,
):
    """Create one standard biodiversity-reference record."""

    metadata = PRIMARY_BIODIVERSITY_SHEETS[sheet_name]

    common_name_raw = raw_text(common_name_raw)
    scientific_name_raw = raw_text(scientific_name_raw)
    status_raw = raw_text(status_raw)

    scientific_candidate, extraction_method = (
        get_scientific_candidate(
            common_name_raw,
            scientific_name_raw,
        )
    )

    record = {
        "source_file": WORKBOOK_PATH.name,
        "source_sheet": sheet_name,
        "source_row": source_row,
        "source_record_id": record_id,
        "parser_type": parser_type,

        "island": metadata["island"],
        "reference_group": metadata["reference_group"],
        "taxon_group": metadata["taxon_group"],
        "environment": metadata["environment"],

        "source_section": source_section,

        # Raw source names are never overwritten.
        "common_name_raw": common_name_raw,
        "scientific_name_raw": scientific_name_raw,

        # Formatting-only derivatives.
        "common_name_normalized": normalize_text(common_name_raw),
        "scientific_name_candidate": scientific_candidate,
        "scientific_name_normalized": (
            normalize_scientific_candidate(scientific_candidate)
        ),

        # How the candidate name was obtained.
        "name_extraction_method": extraction_method,

        # Any source status, e.g. CR / EN / VU.
        "status_raw": status_raw,

        # Taxonomy fields intentionally blank at ingestion.
        "taxonomy_match_status": None,
        "accepted_scientific_name": None,
        "accepted_common_name": None,
        "accepted_taxon_id": None,
        "accepted_rank": None,
        "taxonomy_source": None,
        "taxonomy_version": None,
        "mapping_type": None,
        "mapping_notes": None,
    }

    site_presence = site_presence or {}

    for site in ("A", "B", "C", "D", "E"):
        record[f"site_{site}"] = bool(site_presence.get(site, False))

    return record


# ---------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------

def parse_simple(
    df: pd.DataFrame,
    sheet_name: str,
    config: dict,
):
    """Parse a standard numbered reference sheet."""

    records = []

    for row in range(config["start_row"], len(df)):

        record_id = get_cell(
            df,
            row,
            config["record_id_col"],
        )

        if not is_record_number(record_id):
            continue

        common_name_raw = get_cell(
            df,
            row,
            config["common_name_col"],
        )

        scientific_name_raw = get_cell(
            df,
            row,
            config["scientific_name_col"],
        )

        # Skip numbered source rows that contain no biodiversity identification.
        if (
            normalize_text(common_name_raw) is None
            and normalize_text(scientific_name_raw) is None
        ):
            continue

        records.append(
            build_record(
                sheet_name=sheet_name,
                source_row=row + 1,
                parser_type=config["parser"],
                record_id=record_id,
                common_name_raw=common_name_raw,
                scientific_name_raw=scientific_name_raw,
                status_raw=get_cell(
                    df,
                    row,
                    config.get("status_col"),
                ),
            )
        )

    return records


def parse_site_matrix(
    df: pd.DataFrame,
    sheet_name: str,
    config: dict,
):
    """Parse species records with dive-site presence columns."""

    records = []

    for row in range(config["start_row"], len(df)):

        record_id = get_cell(
            df,
            row,
            config["record_id_col"],
        )

        if not is_record_number(record_id):
            continue

        site_presence = {}

        for column, site in config["site_columns"].items():

            value = get_cell(df, row, column)

            site_presence[site] = (
                normalize_text(value) == "X"
            )

        records.append(
            build_record(
                sheet_name=sheet_name,
                source_row=row + 1,
                parser_type=config["parser"],
                record_id=record_id,
                common_name_raw=get_cell(
                    df,
                    row,
                    config["common_name_col"],
                ),
                scientific_name_raw=get_cell(
                    df,
                    row,
                    config["scientific_name_col"],
                ),
                site_presence=site_presence,
            )
        )

    return records


def parse_sectioned_site_matrix(
    df: pd.DataFrame,
    sheet_name: str,
    config: dict,
):
    """Parse a site matrix containing section headings between records."""

    records = []

    current_section = None

    for row in range(len(df)):

        record_id = get_cell(
            df,
            row,
            config["record_id_col"],
        )

        if not is_record_number(record_id):

            heading_values = []

            for column in config["section_heading_columns"]:
                value = get_cell(df, row, column)

                if is_heading_candidate(value):
                    heading_values.append(
                        normalize_text(value)
                    )

            if heading_values:
                current_section = " | ".join(heading_values)

            continue

        if row < config["start_row"]:
            continue

        site_presence = {}

        for column, site in config["site_columns"].items():

            value = get_cell(df, row, column)

            site_presence[site] = (
                normalize_text(value) == "X"
            )

        records.append(
            build_record(
                sheet_name=sheet_name,
                source_row=row + 1,
                parser_type=config["parser"],
                record_id=record_id,
                common_name_raw=get_cell(
                    df,
                    row,
                    config["common_name_col"],
                ),
                scientific_name_raw=get_cell(
                    df,
                    row,
                    config["scientific_name_col"],
                ),
                source_section=current_section,
                site_presence=site_presence,
            )
        )

    return records


def parse_sectioned_simple(
    df: pd.DataFrame,
    sheet_name: str,
    config: dict,
):
    """Parse a simple sheet divided into named taxonomic/source sections."""

    records = []

    current_section = None

    for row in range(len(df)):

        record_id = get_cell(
            df,
            row,
            config["record_id_col"],
        )

        if not is_record_number(record_id):

            heading = get_cell(
                df,
                row,
                config["section_heading_col"],
            )

            if is_heading_candidate(heading):
                current_section = normalize_text(heading)

            continue

        if row < config["start_row"]:
            continue

        records.append(
            build_record(
                sheet_name=sheet_name,
                source_row=row + 1,
                parser_type=config["parser"],
                record_id=record_id,
                common_name_raw=get_cell(
                    df,
                    row,
                    config["common_name_col"],
                ),
                scientific_name_raw=get_cell(
                    df,
                    row,
                    config["scientific_name_col"],
                ),
                source_section=current_section,
            )
        )

    return records


def parse_embedded_scientific_name(
    df: pd.DataFrame,
    sheet_name: str,
    config: dict,
):
    """Parse rows where scientific names may be separate or embedded."""

    records = []

    for row in range(config["start_row"], len(df)):

        record_id = get_cell(
            df,
            row,
            config["record_id_col"],
        )

        if not is_record_number(record_id):
            continue

        records.append(
            build_record(
                sheet_name=sheet_name,
                source_row=row + 1,
                parser_type=config["parser"],
                record_id=record_id,
                common_name_raw=get_cell(
                    df,
                    row,
                    config["common_name_col"],
                ),
                scientific_name_raw=get_cell(
                    df,
                    row,
                    config.get("scientific_name_col"),
                ),
                status_raw=get_cell(
                    df,
                    row,
                    config.get("status_col"),
                ),
            )
        )

    return records


def parse_embedded_name_only(
    df: pd.DataFrame,
    sheet_name: str,
    config: dict,
):
    """Parse rows where the full species label is stored in one cell."""

    records = []

    for row in range(config["start_row"], len(df)):

        common_value = get_cell(
            df,
            row,
            config["common_name_col"],
        )

        if common_value is None:
            continue

        records.append(
            build_record(
                sheet_name=sheet_name,
                source_row=row + 1,
                parser_type=config["parser"],
                common_name_raw=common_value,
                scientific_name_raw=None,
                status_raw=get_cell(
                    df,
                    row,
                    config.get("status_col"),
                ),
            )
        )

    return records


# ---------------------------------------------------------------------
# Parser dispatch
# ---------------------------------------------------------------------

PARSERS = {
    "simple": parse_simple,
    "site_matrix": parse_site_matrix,
    "sectioned_site_matrix": parse_sectioned_site_matrix,
    "sectioned_simple": parse_sectioned_simple,
    "embedded_scientific_name": parse_embedded_scientific_name,
    "embedded_name_only": parse_embedded_name_only,
}


# ---------------------------------------------------------------------
# Full workbook ingestion
# ---------------------------------------------------------------------

def load_biodiversity_reference():
    """Load all configured primary biodiversity sheets."""

    all_records = []

    for sheet_name, config in SHEET_EXTRACTION_CONFIG.items():

        print(f"Reading: {sheet_name}")

        df = pd.read_excel(
            WORKBOOK_PATH,
            sheet_name=sheet_name,
            header=None,
        )

        parser_name = config["parser"]

        parser = PARSERS.get(parser_name)

        if parser is None:
            raise ValueError(
                f"Unknown parser '{parser_name}' "
                f"for sheet '{sheet_name}'."
            )

        sheet_records = parser(
            df,
            sheet_name,
            config,
        )

        print(
            f"  -> extracted {len(sheet_records)} records"
        )

        all_records.extend(sheet_records)

    result = pd.DataFrame(all_records)

    return result


def main():
    """Run biodiversity-reference ingestion."""

    if not WORKBOOK_PATH.exists():
        raise FileNotFoundError(
            f"Workbook not found: {WORKBOOK_PATH}"
        )

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    reference = load_biodiversity_reference()

    reference.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    reference.to_excel(
        OUTPUT_XLSX,
        index=False,
    )

    print("\n" + "=" * 70)
    print("BIODIVERSITY REFERENCE INGESTION COMPLETE")
    print("=" * 70)

    print(f"\nTotal records: {len(reference)}")

    print("\nRecords by sheet:")

    counts = (
        reference
        .groupby("source_sheet")
        .size()
        .sort_index()
    )

    for sheet, count in counts.items():
        print(f"- {sheet}: {count}")

    print(f"\nCSV saved to:")
    print(OUTPUT_CSV)

    print(f"\nExcel saved to:")
    print(OUTPUT_XLSX)


if __name__ == "__main__":
    main()