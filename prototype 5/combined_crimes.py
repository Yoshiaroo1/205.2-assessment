from pathlib import Path
import pandas as pd

# combined_crimes.py
# Read CSV, sum "Number of Victimisations" per Area unit and write results to a new CSV.


INPUT = Path("new data") / "Table ST_Full Data_data.csv"
OUTPUT = Path("new data") / "combined_by_area.csv"

def find_column(df, keywords):
    """Find first column whose name contains all keywords (case-insensitive),
    or any keyword if none match all."""
    cols = list(df.columns)
    lower_map = {c: c.lower() for c in cols}
    keywords_lower = [k.lower() for k in keywords]  # lowercase the keywords
    # match all keywords first
    for c, lc in lower_map.items():
        if all(k in lc for k in keywords_lower):
            return c
    # match any keyword
    for c, lc in lower_map.items():
        if any(k in lc for k in keywords_lower):
            return c
    return None


def main():
    df = pd.read_csv(INPUT)

    area_col = find_column(df, ["Area Unit"])
    victim_col = find_column(df, ["Number of Victimisations"])

    if area_col is None or victim_col is None:
        raise RuntimeError(f"Could not locate area or victim columns. Available columns: {list(df.columns)}")

    # Normalize victim counts to numeric (remove commas, non-numeric -> NaN -> 0)
    df[victim_col] = pd.to_numeric(df[victim_col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    grouped = (
        df.groupby(area_col, dropna=False)[victim_col]
          .sum()
          .reset_index()
          .rename(columns={victim_col: "Total Victimisations"})
    )

    grouped.to_csv(OUTPUT, index=False)
    print(f"Wrote totals for {len(grouped)} area units to: {OUTPUT}")

if __name__ == "__main__":
    main()