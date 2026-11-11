"""Unit: clause chunking boundaries, extraction schema, citation map,
access filter, graph edges."""
from app.chunking import chunk_document
from app.extraction import extract_from_clause, obligation_type_of
from app.faithfulness import check_answer, claim_support


def test_chunking_never_splits_clause_without_heading():
    text = """1. Payment Terms
Acme Corp shall pay ₹8,00,000 within 30 days of invoice.

2. Termination
Either party may terminate by giving 90 days prior written notice. The termination penalty is ₹5,00,000.
"""
    clauses = chunk_document(text)
    assert len(clauses) == 2
    for c in clauses:
        assert c["heading"], "every clause carries its heading"
        assert c["clause_no"]
        assert c["text"]
    assert "Termination" in clauses[1]["heading"]
    assert "₹5,00,000" in clauses[1]["text"]


def test_chunking_merges_tiny_fragments():
    text = "1. Definitions\n\"Services\" means the services.\n\n2. Term\nThis runs for one year."
    clauses = chunk_document(text)
    assert all(len(c["text"]) >= 20 for c in clauses)


def test_extraction_parties_dates_penalty():
    text = ("Acme Corp shall pay Nimbus Technologies a termination penalty of "
            "₹5,00,000. Effective Date: 1 January 2024. Termination requires "
            "90 days prior written notice. See Clause 6.")
    recs = extract_from_clause(text)
    types = {r.field_type for r in recs}
    assert {"party", "date", "penalty", "notice", "reference", "obligation"} <= types
    assert any("2024-01-01" in r.value for r in recs if r.field_type == "date")
    assert obligation_type_of(text) == "termination"


def test_faithfulness_real_check_not_hardcoded_pass():
    assert claim_support("termination penalty is ₹5,00,000", "The termination penalty is ₹5,00,000.") > 0.5
    assert claim_support("the moon is made of cheese", "The termination penalty is ₹5,00,000.") < 0.2
    res = check_answer(
        [{"claim": "termination penalty ₹5,00,000", "clause_id": "c1"},
         {"claim": "the moon is cheese", "clause_id": "c1"}],
        {"c1": "The termination penalty is ₹5,00,000."})
    assert res["faithfulness"] == 0.5
    assert not res["passed"]
