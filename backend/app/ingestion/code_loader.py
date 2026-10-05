"""
Source code ingestion. Uses lightweight regex-based function/class boundary
detection (works across Python/Java/C/C++/JS/TS/SQL reasonably well) rather
than full tree-sitter grammars, so the project stays zero-cost and doesn't
require compiling per-language parsers. This can be swapped for tree-sitter
later (see README) for exact AST-level boundaries.
"""
import re

# Patterns that usually mark the start of a function/class/method definition
BOUNDARY_PATTERNS = [
    r"^\s*(def|class)\s+\w+",                       # Python
    r"^\s*(public|private|protected|static).*\(.*\)\s*\{?\s*$",  # Java/C#
    r"^\s*(function|const|let)\s+\w+\s*=?\s*\(",     # JS/TS
    r"^\s*\w[\w:<>,\s\*&]*\s+\w+\s*\([^;]*\)\s*\{?\s*$",  # C/C++
    r"^\s*(CREATE|SELECT|INSERT|UPDATE|DELETE)\b",   # SQL statements
]
BOUNDARY_RE = re.compile("|".join(f"({p})" for p in BOUNDARY_PATTERNS), re.IGNORECASE)


def load_code(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    docs = []
    current_block, block_start = [], 1

    def flush(end_line):
        if current_block:
            text = "".join(current_block).strip()
            if text:
                docs.append({
                    "text": text,
                    "location": f"lines {block_start}-{end_line}",
                    "page": None,
                })

    for i, line in enumerate(lines, start=1):
        if BOUNDARY_RE.match(line) and current_block and len(current_block) > 3:
            flush(i - 1)
            current_block, block_start = [], i
        current_block.append(line)

        # Hard cap so pathological files still chunk reasonably
        if len(current_block) >= 80:
            flush(i)
            current_block, block_start = [], i + 1

    flush(len(lines))
    return docs
