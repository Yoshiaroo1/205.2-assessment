from pathlib import Path
import shutil
import pandas as pd

# safetyscoring.py
# Use pandas to remove a trailing full stop from area/unit columns in:
# "new data/combined_by_area_with_severity.csv"


SRC = Path("new data") / "combined_by_area_with_severity.csv"
if not SRC.exists():
    raise FileNotFoundError(f"Source file not found: {SRC}")

# Backup original
BACKUP = SRC.with_name(SRC.name + ".bak")
if not BACKUP.exists():
    shutil.copy2(SRC, BACKUP)

df = pd.read_csv(SRC)

# Candidate columns: those whose name mentions "area" or "unit" (case-insensitive).
candidates = [c for c in df.columns if any(k in c.lower() for k in ("area", "unit"))]

# If none found, fall back to any object column that has values ending with a dot.
if not candidates:
    candidates = [
        c for c in df.select_dtypes(include=["object"]).columns
        if df[c].astype(str).str.endswith(".").any()
    ]

# Remove trailing full stop from candidate columns (only where present).
for c in candidates:
    df[c] = df[c].astype(str).str.rstrip().str.replace(r"\.$", "", regex=True)

# Write back (overwrite).
df.to_csv(SRC, index=False)

print(f"Processed columns: {candidates}")