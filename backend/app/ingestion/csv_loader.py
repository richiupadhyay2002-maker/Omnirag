"""
CSV/XLSX ingestion. Produces:
1. A schema/summary document (columns, dtypes, stats) so the LLM can reason
   about "which category has the highest value" style questions holistically.
2. Row-range chunks of the raw data for detailed lookups.
"""
import pandas as pd
from pathlib import Path


def load_csv(path: str) -> list[dict]:
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    docs = []

    # --- Schema + statistical summary (critical for trend/aggregate questions) ---
    summary_lines = [f"Columns: {', '.join(df.columns.astype(str))}", f"Row count: {len(df)}"]
    numeric_cols = df.select_dtypes(include="number").columns
    for col in numeric_cols:
        summary_lines.append(
            f"Column '{col}': min={df[col].min()}, max={df[col].max()}, "
            f"mean={round(df[col].mean(), 2)}, sum={round(df[col].sum(), 2)}"
        )
    categorical_cols = [c for c in df.columns if c not in numeric_cols]
    for col in categorical_cols[:5]:
        top = df[col].value_counts().head(5)
        summary_lines.append(f"Column '{col}' top values: {dict(top)}")

    docs.append({
        "text": "\n".join(summary_lines),
        "location": "dataset summary",
        "page": None,
    })

    # --- Raw row chunks ---
    chunk_size = 40
    for i in range(0, len(df), chunk_size):
        block = df.iloc[i:i + chunk_size]
        docs.append({
            "text": block.to_csv(index=False),
            "location": f"rows {i + 1}-{i + len(block)}",
            "page": None,
        })

    return docs
