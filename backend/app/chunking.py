"""Clause-aware chunking (PRD §8.1): split by clause/section hierarchy,
never by fixed token windows. A clause is never emitted without its
heading + document context attached.
"""
import re

HEADING_RE = re.compile(
    r"^\s*(?:(?:Clause|Section|Article|Schedule)\s+\d+(?:\.\d+)*"
    r"|(?:\d+(?:\.\d+)+)\s+[A-Z][^\n]{2,80}"
    r"|[A-Z][A-Z \-/]{4,80})\s*$"
)
NUMBERED_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+)$")


def _page_of(offset: int) -> int:
    return max(1, offset // 3000 + 1)


def chunk_document(text: str) -> list[dict]:
    """Return clause dicts: clause_no, section_path, heading, text, page_ref."""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    lines = text.split("\n")
    clauses: list[dict] = []
    current = {"clause_no": "0", "section_path": "Preamble", "heading": "Preamble", "lines": [], "offset": 0}
    offset = 0

    def flush(cur):
        body = "\n".join(l.strip() for l in cur["lines"] if l.strip())
        if body:
            clauses.append({
                "clause_no": cur["clause_no"],
                "section_path": cur["section_path"],
                "heading": cur["heading"],
                "text": body,
                "page_ref": _page_of(cur["offset"]),
            })

    for line in lines:
        stripped = line.strip()
        m = NUMBERED_RE.match(stripped)
        is_heading = bool(HEADING_RE.match(stripped)) or (
            m and len(m.group(2)) <= 90 and not stripped.endswith(".")
        )
        if is_heading and stripped:
            flush(current)
            if m:
                no, title = m.group(1), m.group(2).strip()
                current = {"clause_no": no, "section_path": title, "heading": title,
                           "lines": [stripped], "offset": offset}
            else:
                title = re.sub(r"^(Clause|Section|Article|Schedule)\s+\d+(?:\.\d+)*\s*[-:.]?\s*", "", stripped, flags=re.I)
                no_match = re.search(r"(\d+(?:\.\d+)*)", stripped)
                current = {"clause_no": no_match.group(1) if no_match else str(len(clauses) + 1),
                           "section_path": title or stripped, "heading": title or stripped,
                           "lines": [stripped], "offset": offset}
        else:
            current["lines"].append(line)
        offset += len(line) + 1
    flush(current)
    # Merge only fragments that share a clause number with the previous
    # clause (a heading repeated across a page break). Short but distinct
    # clauses stay separate — they are still citable.
    merged: list[dict] = []
    for c in clauses:
        if merged and len(c["text"]) < 120 and c["clause_no"] == merged[-1]["clause_no"]:
            merged[-1]["text"] += "\n" + c["text"]
        else:
            merged.append(c)
    return merged
