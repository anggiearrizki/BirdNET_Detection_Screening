"""INSPECT THE STRUCTURE OF PRIMARY BIODIVERSITY REFERENCE SHEETS.
IT DOES NOT MODIFY THE WORKBOOK BUT CREATES A PLAIN-TEXT REPORT SHOWING
THE DIMENSIONS AND FIRST FEW NON-EMPTY ROWS OF EACH SELECTED SHEET.
"""

# ============================
# DATA AND LIB PREPARATION
# ============================

from pathlib import Path
import pandas as pd
from source_map import PRIMARY_BIODIVERSITY_SHEETS

WORKBOOK_PATH = Path("data/reference/Species_List.xlsx")
OUTPUT_PATH = Path("outputs/reference_workbook_inspection.txt")

PREVIEW_ROWS = 15


def inspect_sheet(sheet_name: str) -> str:
    """Return a readable structural preview of one worksheet."""

    df = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name=sheet_name,
        header=None,
    )

    original_rows, original_columns = df.shape

    # Remove completely empty rows/columns only for the preview.
    preview = df.dropna(how="all").dropna(axis=1, how="all").head(PREVIEW_ROWS)

    lines = [
        "=" * 80,
        f"SHEET: {sheet_name}",
        f"Original dimensions: {original_rows} rows x {original_columns} columns",
        "-" * 80,
        preview.to_string(index=True, header=False),
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    reports = []

    for sheet_name in PRIMARY_BIODIVERSITY_SHEETS:
        reports.append(inspect_sheet(sheet_name))

    OUTPUT_PATH.write_text(
        "\n".join(reports),
        encoding="utf-8",
    )

    print(
        f"Inspection complete for "
        f"{len(PRIMARY_BIODIVERSITY_SHEETS)} primary sheets."
    )
    print(f"Report saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()