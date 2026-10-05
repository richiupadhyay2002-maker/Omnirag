"""Plain text / markdown loader. Splits by line ranges for citation locations."""


def load_text(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    docs = []
    chunk_size = 60
    for i in range(0, len(lines), chunk_size):
        block = lines[i:i + chunk_size]
        text = "".join(block).strip()
        if text:
            docs.append({
                "text": text,
                "location": f"lines {i + 1}-{i + len(block)}",
                "page": None,
            })
    return docs
