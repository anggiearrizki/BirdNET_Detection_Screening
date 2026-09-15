"""INSPECT EXACT CELL POSITIONS IN STRUCTURALLY COMPLEX BIODIVERSITY SHEETS."""

# ============================
# DATA AND LIB PREPARATION
# ============================

from pathlib import Path
import pandas as pd


WORKBOOK_PATH = Path("data/reference/Species_List.xlsx")

COMPLEX_SHEETS = {
    "Cmpk Other Marine Fauna",
    "Nikoi Marine Fish",
    "Nikoi Marine Invertebrates",
    "Nikoi Other Marine Fauna",
    "Nikoi Marine Algae",
}


def show_nonempty_rows(sheet_name: str) -> None:
    df = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name=sheet_name,
        header=None,
    )

    print("\n" + "=" * 90)
    print(f"SHEET: {sheet_name}")
    print("=" * 90)

    for row_index, row in df.iterrows():

        values = {
            int(column): value
            for column, value in row.items()
            if pd.notna(value)
        }

        if values:
            print(f"ROW {row_index}: {values}")


def main() -> None:

    for sheet_name in COMPLEX_SHEETS:
        show_nonempty_rows(sheet_name)


if __name__ == "__main__":
    main()