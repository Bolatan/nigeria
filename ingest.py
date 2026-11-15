"""Splits the Constitution into passages (section by section). Optional local index build:  python ingest.py"""
import re
import sys
from pathlib import Path


def read(path):
    if path.lower().endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    return Path(path).read_text(encoding="utf-8")


def split_markdown(text):
    """data/constitution.md: '# Chapter V' headings and '#### Section 35' headings."""
    chapters = [(m.start(), f"CHAPTER {m.group(1).upper()}") for m in re.finditer(r"(?m)^# Chapter ([IVXL]+)\b", text)]
    marks = [(int(m.group(1)), m.start(), m.end()) for m in re.finditer(r"(?m)^#### Section (\d+)\s*$", text)]
    out = []
    for i, (n, start, body_start) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        body = re.sub(r"(?m)^#{1,3} .*$", "", text[body_start:stop])  # drop chapter/part headings that trail a section
        chapter = next((c for pos, c in reversed(chapters) if pos <= start), "")
        out.append((n, chapter, f"Section {n}\n" + re.sub(r"\n{3,}", "\n\n", body).strip()))
    return out


def split_sections(text):
    if re.search(r"(?m)^#### Section \d+\s*$", text):
        return split_markdown(text)
    """Return [(section_number, chapter, text)]. Picks the longest run 1,2,3... so the
    table of contents (a short run) is ignored in favour of the real body."""
    text = re.sub(r"[ \t]+", " ", text)
    chapters = [(m.start(), m.group(1)) for m in re.finditer(r"(?m)^\s*(CHAPTER [IVXL]+)\b", text)]
    runs, nxt = [], 0
    for m in re.finditer(r"(?m)^\s*(\d{1,3})\.\s+(?=\S)", text):
        n = int(m.group(1))
        if n == 1:
            runs.append([(1, m.start())]); nxt = 2
        elif runs and n == nxt:
            runs[-1].append((n, m.start())); nxt += 1
    if not runs:
        raise SystemExit("No numbered sections found. Check the text extraction.")
    run = max(runs, key=lambda r: r[-1][1] - r[0][1])
    end = text.find("FIRST SCHEDULE", run[-1][1])
    bounds = [p for _, p in run] + [end if end > 0 else len(text)]
    out = []
    for (n, start), stop in zip(run, bounds[1:]):
        chapter = next((c for pos, c in reversed(chapters) if pos <= start), "")
        out.append((n, chapter, text[start:stop].strip()))
    return out


def windows(t, size=1200, overlap=150):
    if len(t) <= size:
        return [t]
    out, i = [], 0
    while True:
        j = min(i + size, len(t))
        if j < len(t):
            k = t.rfind(" ", i + size // 2, j)
            j = k if k > 0 else j
        out.append(t[i:j])
        if j >= len(t):
            return out
        i = j - overlap


def build_chunks(text):
    ids, docs, metas = [], [], []
    for n, chapter, body in split_sections(text):
        for i, w in enumerate(windows(body)):
            ids.append(f"s{n}-{i}")
            docs.append(w)
            metas.append({"ref": f"Section {n}", "section": n, "chapter": chapter})
    return ids, docs, metas


if __name__ == "__main__":
    # Local alternative to /admin.html: writes data/index.json (needs API_KEY / EMBED_* variables)
    import json

    import rag

    total, vectors = len(rag.chunks()[0]), []
    for i in range(0, total, 48):
        vectors += rag.embed_chunks(i, 48)
        print(f"{len(vectors)}/{total}")
    with open(rag.INDEX, "w", encoding="utf-8") as f:
        json.dump({"embed_model": rag.EMBED_MODEL, "hash": rag.fingerprint(), "vectors": vectors}, f)
    print("Wrote", rag.INDEX)
