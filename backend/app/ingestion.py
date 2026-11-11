"""Ingestion: parse PDF/DOCX/TXT -> clause chunking -> extraction ->
obligations -> graph edges -> indexing. Synchronous in-process for v1
(local dev); the worker service in docker-compose runs the same function
via the /api/documents/{id}/reprocess path and a queue stub is documented
in README (Celery is the scale path, not a v1 dependency).
"""
import hashlib
import io
import json
import re

from sqlalchemy.orm import Session

from . import models
from .chunking import chunk_document
from .extraction import extract_from_clause, obligation_type_of
from .retrieval import hash_embedding


def parse_bytes(filename: str, data: bytes) -> tuple[str, float, str]:
    """Returns (text, parse_quality 0..1, notes)."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for p in reader.pages:
            pages.append(p.extract_text() or "")
        text = "\n".join(pages)
        chars = len(text.strip())
        quality = 1.0 if chars > 500 else (0.5 if chars > 100 else 0.2)
        notes = "" if quality >= 0.9 else "Low extracted text — possibly scanned; flagged, not silently trusted."
        return text, quality, notes
    if name.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in d.paragraphs)
        return text, 1.0 if len(text.strip()) > 100 else 0.5, ""
    # .txt / .md fallback
    return data.decode("utf-8", errors="replace"), 1.0, ""


def _add_edge(db, src_type, src_id, src_label, dst_type, dst_id, dst_label, rel, doc_id, conf=0.9):
    db.add(models.GraphEdge(src_type=src_type, src_id=src_id, src_label=src_label,
                            dst_type=dst_type, dst_id=dst_id, dst_label=dst_label,
                            rel_type=rel, confidence=conf, document_id=doc_id))


def ingest_document(db: Session, document: models.Document, text: str, filename: str = "") -> dict:
    """Run the full pipeline for one document version. Returns stats."""
    document.status = "processing"
    db.commit()
    version = db.query(models.DocVersion).filter_by(document_id=document.id).order_by(
        models.DocVersion.version_no.desc()).first()
    if version is None:
        version = models.DocVersion(document_id=document.id, version_no=document.current_version,
                                    storage_key=filename, text=text)
        db.add(version)
    else:
        version.text = text
        version.storage_key = filename
    db.commit()

    document.status = "extracting"
    db.commit()
    clauses = chunk_document(text)
    # Clear previous clauses/extractions/obligations/edges for this doc.
    old_clause_ids = [c.id for c in db.query(models.Clause).filter_by(document_id=document.id).all()]
    if old_clause_ids:
        db.query(models.Extraction).filter(models.Extraction.clause_id.in_(old_clause_ids)).delete(synchronize_session=False)
        db.query(models.Obligation).filter(models.Obligation.document_id == document.id).delete(synchronize_session=False)
        db.query(models.Clause).filter_by(document_id=document.id).delete(synchronize_session=False)
    db.query(models.GraphEdge).filter_by(document_id=document.id).delete(synchronize_session=False)
    db.commit()

    doc_label = document.title
    _add_edge(db, "Document", document.id, doc_label, "Document", document.id, doc_label, "CONTAINS", document.id, 1.0)
    created_clauses = []
    parties_seen: dict[str, str] = {}
    for ch in clauses:
        clause = models.Clause(document_id=document.id, version_id=version.id,
                               clause_no=ch["clause_no"], section_path=ch["section_path"],
                               heading=ch["heading"], text=ch["text"], page_ref=ch["page_ref"],
                               embedding_json=json.dumps(hash_embedding(ch["heading"] + " " + ch["text"])))
        db.add(clause)
        db.flush()
        created_clauses.append(clause)
        _add_edge(db, "Document", document.id, doc_label, "Clause", clause.id,
                  f"{ch['clause_no']} {ch['heading']}", "CONTAINS", document.id, 1.0)
        for rec in extract_from_clause(ch["text"], ch["heading"]):
            db.add(models.Extraction(clause_id=clause.id, field_type=rec.field_type,
                                     value=rec.value, confidence=rec.confidence))
            if rec.field_type == "party" and rec.value not in parties_seen:
                parties_seen[rec.value] = clause.id
                _add_edge(db, "Clause", clause.id, ch["heading"], "Party", rec.value, rec.value,
                          "BINDS", document.id, rec.confidence)
        # Obligation record per obligation-bearing clause.
        obl_texts = [r.value for r in extract_from_clause(ch["text"], ch["heading"]) if r.field_type == "obligation"]
        pens = [r.value for r in extract_from_clause(ch["text"], ch["heading"]) if r.field_type == "penalty"]
        dates = [r.value for r in extract_from_clause(ch["text"], ch["heading"]) if r.field_type == "date"]
        if obl_texts:
            db.add(models.Obligation(document_id=document.id, clause_id=clause.id,
                                     party=", ".join(sorted(parties_seen.keys()))[:200],
                                     obligation_text=obl_texts[0],
                                     obligation_type=obligation_type_of(ch["text"]),
                                     effective_date=dates[0] if dates else "",
                                     due_date=dates[-1] if len(dates) > 1 else "",
                                     penalty="; ".join(pens)[:300],
                                     source_clause_no=ch["clause_no"]))
            _add_edge(db, "Clause", clause.id, ch["heading"], "Obligation", obl_texts[0][:80],
                      obl_texts[0][:80], "IMPOSES", document.id, 0.8)
    db.commit()

    # Amendment / supersedes edges: "amends Clause X of <Doc>" / "supersedes".
    _link_amendments(db, document, created_clauses)
    # Conflict candidates: same party + termination topic, different penalty amounts.
    _detect_conflicts(db, document, created_clauses)
    document.status = "indexing"
    db.commit()
    document.status = "ready"
    db.commit()
    return {"clauses": len(created_clauses), "parties": len(parties_seen)}


def _link_amendments(db: Session, document: models.Document, clauses: list[models.Clause]):
    text_all = " ".join(c.text for c in clauses)
    if "amend" not in text_all.lower() and "supersede" not in text_all.lower():
        return
    for clause in clauses:
        m = re.search(r"(?:amends?|supersedes?)\s+(?:Clause|Section)\s+(\d+(?:\.\d+)*)\s+of\s+(.{0,80}?)(?:\.|,|\n|$)",
                      clause.text, re.I)
        if not m:
            continue
        target_no, target_hint = m.group(1), m.group(2).strip()
        # Find the target document by title words in the hint.
        for other in db.query(models.Document).filter(models.Document.id != document.id).all():
            title_words = [w for w in re.findall(r"[A-Za-z]+", other.title) if len(w) > 3]
            if any(w.lower() in target_hint.lower() for w in title_words):
                target = db.query(models.Clause).filter_by(document_id=other.id, clause_no=target_no).first()
                if target:
                    rel = "SUPERSEDES" if "supersede" in clause.text.lower() else "AMENDS"
                    _add_edge(db, "Clause", clause.id, clause.heading, "Clause", target.id,
                              target.heading, rel, document.id, 0.95)
                    target.is_current = False
                    target.superseded_by_clause_id = clause.id
                    db.commit()
                break


def _detect_conflicts(db: Session, document: models.Document, clauses: list[models.Clause]):
    """Same party + termination-penalty topic, different amounts across docs
    -> candidate conflict (human confirmation required, never a verdict)."""
    for clause in clauses:
        if "terminat" not in clause.text.lower() or "penalt" not in clause.text.lower():
            continue
        pens = re.findall(r"₹\s*([\d,]+)", clause.text)
        if not pens:
            continue
        parties = set(re.findall(r"([A-Z][A-Za-z&.'-]{2,40}?\s+(?:Ltd\.?|Limited|LLP|Inc\.?|Corp\.?|Technologies|Logistics|Foods))", clause.text))
        for other_clause in db.query(models.Clause).filter(
                models.Clause.document_id != document.id,
                models.Clause.is_current.is_(True)).all():
            if "terminat" not in other_clause.text.lower():
                continue
            other_pens = re.findall(r"₹\s*([\d,]+)", other_clause.text)
            if not other_pens or set(pens) == set(other_pens):
                continue
            other_parties = set(re.findall(r"([A-Z][A-Za-z&.'-]{2,40}?\s+(?:Ltd\.?|Limited|LLP|Inc\.?|Corp\.?|Technologies|Logistics|Foods))", other_clause.text))
            if parties & other_parties:
                shared = sorted(parties & other_parties)[0]
                exists = db.query(models.Conflict).filter(
                    ((models.Conflict.clause_a_id == clause.id) & (models.Conflict.clause_b_id == other_clause.id)) |
                    ((models.Conflict.clause_a_id == other_clause.id) & (models.Conflict.clause_b_id == clause.id))).first()
                if not exists:
                    db.add(models.Conflict(
                        clause_a_id=clause.id, clause_b_id=other_clause.id,
                        topic="Termination penalty", party=shared,
                        explanation=(f"Both clauses impose a termination penalty on {shared} "
                                     f"but state different amounts (₹{pens[0]} vs ₹{other_pens[0]}). "
                                     "Candidate conflict — requires human confirmation; RegLens does not decide which governs.")))
                    _add_edge(db, "Clause", clause.id, clause.heading, "Clause", other_clause.id,
                              other_clause.heading, "CONFLICTS_WITH", document.id, 0.7)
    db.commit()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
