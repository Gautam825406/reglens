"""Deterministic structured extraction (rules-v1) with Pydantic validation.

Parties, dates, obligations, penalties, notice periods, cross-references.
An optional LLM assist is NOT used in v1: rules are measurable and the
README says so honestly. Extraction F1 is measured against the golden set.
"""
import re
from datetime import datetime

from pydantic import BaseModel, Field

DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b", re.I)
MONEY_RE = re.compile(r"(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.\d{2})?)\s*(?:lakh|crore)?", re.I)
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:per\s+(month|annum|year|day))?", re.I)
PARTY_RE = re.compile(r"\b([A-Z][A-Za-z0-9&.'-]{1,40}?\s+(?:Ltd\.?|Limited|LLP|Inc\.?|Corp\.?|Corporation|Pvt\.?\s*Ltd\.?|Technologies|Logistics|Foods|Bank|Insurance))\b")
REF_RE = re.compile(r"\b(?:Clause|Section|Article)\s+(\d+(?:\.\d+)*)\b", re.I)
NOTICE_RE = re.compile(r"(\d+)\s*[- ]?days?\s+(?:prior\s+)?(?:written\s+)?notice", re.I)
OBLIGATION_VERBS = re.compile(r"\b(shall|must|agrees?\s+to|is\s+required\s+to|will\s+provide|shall\s+pay|shall\s+deliver)\b", re.I)

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def normalise_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%d %B %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return raw


class ExtractionRecord(BaseModel):
    field_type: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


def extract_from_clause(clause_text: str, heading: str = "") -> list[ExtractionRecord]:
    text = clause_text or ""
    out: list[ExtractionRecord] = []
    for party in sorted(set(PARTY_RE.findall(text))):
        out.append(ExtractionRecord(field_type="party", value=party.strip(), confidence=0.85))
    for d in DATE_RE.findall(text):
        out.append(ExtractionRecord(field_type="date", value=normalise_date(d), confidence=0.9))
    low = text.lower()
    if "penalt" in low or "liquidated damages" in low or "termination" in low:
        for amt in MONEY_RE.findall(text):
            out.append(ExtractionRecord(field_type="penalty", value=f"₹{amt}", confidence=0.85))
        for pct in PERCENT_RE.findall(text):
            out.append(ExtractionRecord(field_type="penalty", value=f"{pct[0]}% per {pct[1] or 'month'}", confidence=0.8))
    for n in NOTICE_RE.findall(text):
        out.append(ExtractionRecord(field_type="notice", value=f"{n} days", confidence=0.9))
    for ref in REF_RE.findall(text):
        out.append(ExtractionRecord(field_type="reference", value=f"Clause {ref}", confidence=0.9))
    if OBLIGATION_VERBS.search(text):
        # First obligation sentence as the obligation record.
        for sent in re.split(r"(?<=[.;])\s+", text):
            if OBLIGATION_VERBS.search(sent):
                out.append(ExtractionRecord(field_type="obligation", value=sent.strip()[:500], confidence=0.75))
                break
    return out


def obligation_type_of(text: str) -> str:
    low = (text or "").lower()
    if "terminat" in low:
        return "termination"
    if "pay" in low or "fee" in low or "invoice" in low or "₹" in text:
        return "payment"
    if "deliver" in low or "supply" in low:
        return "delivery"
    if "notice" in low:
        return "notice"
    if "comply" in low or "audit" in low or "regulat" in low or "rbi" in low:
        return "compliance"
    return "other"
