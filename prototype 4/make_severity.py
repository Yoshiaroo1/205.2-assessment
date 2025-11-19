import pandas as pd
from pathlib import Path

# make_severity.py
# Reads "new data/combined_by_area.csv", computes total crimes and assigns a severity rating.


INPUT = Path("new data") / "combined_by_area.csv"
OUTPUT = INPUT.with_name(INPUT.stem + "_with_severity.csv")

df = pd.read_csv(INPUT)

# Determine total crimes column: prefer existing total-like column, otherwise sum numeric columns
cols_lower = [c.lower() for c in df.columns]
total_col = None
for candidate in ("total", "total_crimes", "num_crimes", "crime_total"):
    if candidate in cols_lower:
        total_col = df.columns[cols_lower.index(candidate)]
        break

if total_col:
    df["total_crimes"] = df[total_col]
else:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        raise SystemExit("No numeric columns available to compute total crimes.")
    df["total_crimes"] = df[numeric_cols].sum(axis=1)

# Assign severity using quartiles (Low, Medium, High, Very High). Fallbacks for uniform data.
labels = ["Low", "Medium", "High", "Very High"]
if df["total_crimes"].nunique() == 1:
    df["severity"] = "Low"
else:
    try:
        df["severity"] = pd.qcut(df["total_crimes"], q=4, labels=labels)
    except ValueError:
        q = df["total_crimes"].quantile([0.25, 0.5, 0.75]).tolist()
        bins = [df["total_crimes"].min() - 1] + q + [df["total_crimes"].max() + 1]
        df["severity"] = pd.cut(df["total_crimes"], bins=bins, labels=labels)

df.to_csv(OUTPUT, index=False)
print(f"Wrote {len(df)} rows with severity to: {OUTPUT}")