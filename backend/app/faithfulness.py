"""Faithfulness: every claim must be supported by its cited clause.

Implemented as a real lexical-support check (content-word overlap between
the claim and the cited clause text), not a hardcoded pass. Claims below
the threshold are dropped; if no claim survives, the answer abstains.
"""
import re

from .config import settings
from .retrieval import STOPWORDS

CONTENT_MIN_LEN = 3


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if w not in STOPWORDS and len(w) >= CONTENT_MIN_LEN}


def claim_support(claim: str, clause_text: str) -> float:
    cw = content_words(claim)
    if not cw:
        return 0.0
    ct = content_words(clause_text)
    return len(cw & ct) / len(cw)


def split_claims(answer: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.;])\s+", (answer or "").strip()) if p.strip()]
    return [p for p in parts if len(p) > 10]


def check_answer(claims_with_citations: list[dict], clause_text_by_id: dict[str, str]) -> dict:
    """claims_with_citations: [{claim, clause_id}]. Returns per-claim
    support scores, overall faithfulness, and the surviving claims."""
    results = []
    for item in claims_with_citations:
        text = clause_text_by_id.get(item.get("clause_id", ""), "")
        score = claim_support(item.get("claim", ""), text) if text else 0.0
        results.append({**item, "support": round(score, 3),
                        "supported": score >= settings.faithfulness_threshold})
    supported = [r for r in results if r["supported"]]
    faithfulness = (len(supported) / len(results)) if results else 0.0
    return {"claims": results, "faithfulness": round(faithfulness, 3),
            "supported_claims": supported, "passed": faithfulness >= 0.8 and bool(supported)}
