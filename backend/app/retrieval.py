"""Hybrid retrieval: BM25 + TF-hash vector (cosine) + graph expansion,
merged, de-duplicated, re-ranked. Access control is applied BEFORE
ranking/generation: clauses from collections the user may not access are
never retrieved, never cited, never sent to the LLM.

Vector path uses a deterministic TF-hash embedding (same interface as
IncidentPilot's hash_embedding) so the build needs no model download;
sentence-transformers is the documented swap-in (see README).
"""
import hashlib
import json
import math
import re
from collections import Counter

from sqlalchemy.orm import Session

from . import models
from .config import settings

STOPWORDS = set(
    "a an the and or of to in on for with by is are was were be been it its this that "
    "what which who whom when where how many much does do did can could should would "
    "from at as into over under between after before about per".split()
)
DIM = 1024


def _stem(w: str) -> str:
    if len(w) > 5 and w.endswith("ing"):
        return w[:-3]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    if len(w) > 4 and w.endswith("e"):
        return w[:-1]
    return w


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOPWORDS]


def hash_embedding(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    for word in tokenize(text):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def allowed_collection_ids(db: Session, user) -> set[str]:
    """Admin sees everything. Others: public collections + explicit grants."""
    if user.role == "admin":
        return {c.id for c in db.query(models.Collection).all()}
    ids = {c.id for c in db.query(models.Collection).filter_by(is_public=True).all()}
    for acc in db.query(models.CollectionAccess).filter_by(user_id=user.id).all():
        ids.add(acc.collection_id)
    return ids


def _bm25(query_terms: list[str], clauses: list[models.Clause], k1=1.5, b=0.75) -> dict[str, float]:
    docs = [tokenize(c.heading + " " + c.text) for c in clauses]
    n = len(docs) or 1
    avgdl = sum(len(d) for d in docs) / n
    df = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    scores: dict[str, float] = {}
    for clause, d in zip(clauses, docs):
        tf = Counter(d)
        s = 0.0
        for t in query_terms:
            if df.get(t, 0) == 0:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * len(d) / (avgdl or 1)))
        scores[clause.id] = s
    return scores


def _graph_expand(db: Session, seed_clause_ids: list[str], allowed_docs: set[str],
                  max_depth: int = 2) -> dict[str, float]:
    """Traverse AMENDS/SUPERSEDES/REFERENCES/CONFLICTS_WITH/BINDS edges from
    seed clauses. Returns clause_id -> graph score (decays with depth)."""
    found: dict[str, float] = {}
    frontier = list(seed_clause_ids)
    for depth in range(1, max_depth + 1):
        nxt: list[str] = []
        for src in frontier:
            edges = db.query(models.GraphEdge).filter(
                models.GraphEdge.src_id == src,
                models.GraphEdge.rel_type.in_(["AMENDS", "SUPERSEDES", "REFERENCES", "CONFLICTS_WITH", "BINDS"]),
            ).all()
            for e in edges:
                if e.dst_type == "Clause" and e.dst_id not in found:
                    found[e.dst_id] = 0.5 / depth
                    nxt.append(e.dst_id)
                elif e.dst_type == "Clause":
                    found[e.dst_id] = max(found[e.dst_id], 0.5 / depth)
        frontier = nxt
        if not frontier:
            break
    # Drop any graph hit whose document is not allowed (defence in depth).
    if found:
        ok = {c.id for c in db.query(models.Clause).filter(models.Clause.id.in_(list(found))).all()
              if c.document_id in allowed_docs}
        found = {k: v for k, v in found.items() if k in ok}
    return found


def retrieve(db: Session, user, question: str, collection_ids: list[str] | None = None,
             top_k: int | None = None, modes: tuple[str, ...] = ("vector", "bm25", "graph")) -> list[dict]:
    """Return ranked clause dicts with a retrieval trace (score per path)."""
    top_k = top_k or settings.retrieval_top_k
    allowed = allowed_collection_ids(db, user)
    if collection_ids:
        allowed &= set(collection_ids)
    docs = db.query(models.Document).filter(
        models.Document.collection_id.in_(list(allowed)) if allowed else models.Document.id == "__none__",
        models.Document.status == "ready",
    ).all()
    allowed_doc_ids = {d.id for d in docs}
    if not allowed_doc_ids:
        return []
    clauses = db.query(models.Clause).filter(
        models.Clause.document_id.in_(list(allowed_doc_ids)),
        models.Clause.is_current.is_(True),
    ).all()
    if not clauses:
        return []
    q_terms = tokenize(question)
    q_vec = hash_embedding(question)
    by_id = {c.id: c for c in clauses}
    doc_by_id = {d.id: d for d in docs}

    # IDF-weighted topic coverage: how much of the question's distinctive
    # vocabulary does a clause actually contain? A question naming a real
    # document ("force majeure in the Supply Agreement") must not be
    # "answered" by a clause that only shares the document's name. Terms
    # absent from the whole corpus get max IDF, so unanswerable topics
    # (force majeure, arbitration) score near zero coverage.
    clause_tokens = [set(tokenize(c.heading + " " + c.text)) for c in clauses]
    n_docs = len(clauses) or 1
    idf: dict[str, float] = {}
    for t in set(q_terms):
        df = sum(1 for toks in clause_tokens if t in toks)
        idf[t] = math.log((n_docs + 1) / (df + 0.5)) + 1.0
    total_idf = sum(idf.values()) or 1.0

    scores: dict[str, dict] = {c.id: {"bm25": 0.0, "vector": 0.0, "graph": 0.0} for c in clauses}
    if "bm25" in modes:
        for cid, s in _bm25(q_terms, clauses).items():
            scores[cid]["bm25"] = s
    if "vector" in modes:
        for c in clauses:
            try:
                emb = json.loads(c.embedding_json or "[]")
            except Exception:
                emb = []
            if len(emb) == DIM:
                scores[c.id]["vector"] = cosine(q_vec, emb)
            else:
                scores[c.id]["vector"] = cosine(q_vec, hash_embedding(c.heading + " " + c.text))
    # Normalise each path to [0,1] so the merge is not dominated by raw BM25.
    for path in ("bm25", "vector"):
        mx = max((scores[c.id][path] for c in clauses), default=0.0) or 1.0
        for c in clauses:
            scores[c.id][path] /= mx
    if "graph" in modes:
        seed_ids = sorted(clauses, key=lambda c: scores[c.id]["bm25"] + scores[c.id]["vector"], reverse=True)[:3]
        for cid, s in _graph_expand(db, [c.id for c in seed_ids], allowed_doc_ids).items():
            if cid in scores:
                scores[cid]["graph"] = s
    # Re-rank: weighted merge + exact-term overlap bonus (the local re-ranker).
    # Guard: a clause sharing NO content word with the question and no BM25
    # hit cannot be "about" the question on hash-vector similarity alone
    # (TF-hash collisions inflate cosine on short texts) — cap its score
    # below the abstention threshold so Ask abstains honestly.
    ranked = []
    for c in clauses:
        s = scores[c.id]
        overlap = len(set(q_terms) & set(tokenize(c.heading + " " + c.text))) / max(len(set(q_terms)), 1)
        # The overlap bonus IS the local re-ranker: it only applies when
        # the caller passes "rerank" in modes, so the ablation can measure it.
        rerank_bonus = 0.25 * overlap if "rerank" in modes else 0.0
        total = 0.45 * s["vector"] + 0.35 * s["bm25"] + 0.20 * s["graph"] + rerank_bonus
        if overlap == 0 and s["bm25"] == 0:
            total = min(total, 0.25)
        ranked.append((total, c, dict(s), overlap))
    ranked.sort(key=lambda r: r[0], reverse=True)
    out = []
    for total, c, trace, overlap in ranked[:top_k]:
        d = doc_by_id[c.document_id]
        toks = set(tokenize(c.heading + " " + c.text))
        coverage = round(sum(idf[t] for t in set(q_terms) if t in toks) / total_idf, 3)
        out.append({
            "clause_id": c.id, "document_id": c.document_id, "document_title": d.title,
            "document_type": d.doc_type, "version": d.current_version,
            "clause_no": c.clause_no, "section": c.section_path, "heading": c.heading,
            "text": c.text, "page_ref": c.page_ref, "score": round(total, 4),
            "coverage": coverage,
            "trace": {k: round(v, 4) for k, v in trace.items()} | {"overlap": round(overlap, 4)},
            "superseded_by": c.superseded_by_clause_id,
        })
    return out


# Top-score below this means "no clause is really about the question":
# the Ask endpoint abstains instead of quoting irrelevant clauses.
ABSTAIN_TOP_SCORE_THRESHOLD = 0.30
# Best IDF-weighted topic coverage (over the top 3 retrieved clauses)
# below this also abstains: the question's distinctive terms appear in
# no retrieved clause (e.g. "force majeure" in a corpus that has none).
ABSTAIN_COVERAGE_THRESHOLD = 0.40
