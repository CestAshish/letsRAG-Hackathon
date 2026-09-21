import json
from pathlib import Path
import fitz
import re

SOURCES = Path("data/sources")
MIN_CHARS = 50


def clean(text):
    # basic cleanup to fix weird pdf line breaks
    lines = text.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    cleaned = " ".join(lines)
    # remove double spaces that show up randomly
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def extract_pdf(path):
    doc = fitz.open(path)
    for i in range(len(doc)):
        page = doc[i]
        yield i + 1, clean(page.get_text())


def main():
    entries = []
    near_empty = 0

    for path in SOURCES.glob('*.pdf'):
        for page_num, text in extract_pdf(path):
            if len(text) < MIN_CHARS:
                near_empty += 1
            entries.append({
                "source": path.name,
                "page": page_num,
                "char_count": len(text),
                "text": text
            })

    out = Path("data")

    with open(out / "corpus.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    with open(out / "sample.json", "w", encoding="utf-8") as f:
        json.dump(entries[:10], f, ensure_ascii=False, indent=2)

    total_chars = sum(e["char_count"] for e in entries)

    print("source files: 1")
    print("total entries:", len(entries))
    print("total characters:", total_chars)
    if len(entries) > 0:
        print("avg characters/entry:", total_chars // len(entries))
    else:
        print("avg characters/entry: 0")
    print(f"near-empty entries (<{MIN_CHARS} chars):", near_empty)


if __name__ == "__main__":
    main()
