"""RegLens API — FastAPI. Auth + RBAC, documents, AI Ask, compare,
conflicts, obligations, knowledge graph, evidence packs, admin, evals.

All access control is enforced in retrieval (retrieval.py), not in the UI.
"""
import hashlib
import io
import json
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db, init_db
from .faithfulness import check_answer, split_claims
from .generation import PROMPT_VERSION, generate_answer
from .ingestion import ingest_document, parse_bytes, sha256_of
from .retrieval import allowed_collection_ids, retrieve
from .security import contains_injection, create_token, hash_password, redact_pii, verify_password, verify_token
from .seed import seed_demo

app = FastAPI(title="RegLens", version="1.0.0",
              description="Citation-grounded GraphRAG for contracts & compliance.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
init_db()

# ---- rate limiting (in-memory sliding window, per IP) ----
_buckets: dict[str, list[float]] = {}


def _rate_limit(key: str, per_minute: int):
    if not settings.rate_limit_enabled:
        return
    now = time.time()
    b = [t for t in _buckets.get(key, []) if now - t < 60]
    if len(b) >= per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded — try again in a minute.")
    b.append(now)
    _buckets[key] = b


# ---- helpers ----
def audit(db: Session, user_id: str, action: str, object_type: str = "", object_id: str = "", detail: dict | None = None):
    db.add(models.AuditLog(user_id=user_id or "", action=action, object_type=object_type,
                           object_id=object_id, detail_json=json.dumps(detail or {})))
    db.commit()


def user_out(u: models.User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "email_verified": u.email_verified, "created_at": str(u.created_at)}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = verify_token(auth[7:])
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(models.User).filter_by(id=data["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: str):
    def _check(user: models.User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _check


def doc_out(db: Session, d: models.Document) -> dict:
    coll = db.query(models.Collection).filter_by(id=d.collection_id).first()
    n_clauses = db.query(models.Clause).filter_by(document_id=d.id).count()
    n_obl = db.query(models.Obligation).filter_by(document_id=d.id).count()
    return {"id": d.id, "collection_id": d.collection_id, "collection_name": coll.name if coll else "",
            "title": d.title, "doc_type": d.doc_type, "status": d.status,
            "parse_quality": d.parse_quality, "parse_notes": d.parse_notes,
            "current_version": d.current_version, "is_demo": d.is_demo,
            "clauses": n_clauses, "obligations": n_obl, "error": d.error,
            "created_at": str(d.created_at)}


# ---- schemas ----
class RegisterIn(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: str
    password: str


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    collection_ids: list[str] | None = None
    top_k: int = 8


class CollectionIn(BaseModel):
    name: str
    description: str = ""
    confidentiality: str = "internal"
    is_public: bool = True


class CompareIn(BaseModel):
    doc_a_id: str
    doc_b_id: str


class EvidenceIn(BaseModel):
    question_id: str


class RoleIn(BaseModel):
    role: str


class ResetRequestIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


# ---- health ----
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "app": "RegLens", "version": "1.0.0",
            "mode": "extractive (no LLM)" if settings.demo_mode else "llm",
            "model": settings.groq_model if not settings.demo_mode else "extractive (no LLM — GROQ_API_KEY not set)",
            "prompt_version": PROMPT_VERSION}


# ---- auth ----
@app.post("/api/auth/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _rate_limit(f"reg:{request.client.host}", 10)
    email = body.email.strip().lower()
    if db.query(models.User).filter_by(email=email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    is_first = db.query(models.User).count() == 0
    user = models.User(name=body.name.strip(), email=email,
                       password_hash=hash_password(body.password),
                       role="admin" if is_first else "viewer", email_verified=False)
    db.add(user)
    db.commit()
    audit(db, user.id, "user.register", "user", user.id, {"first_user_admin": is_first})
    return {"token": create_token(user.id, user.email, user.role), "user": user_out(user),
            "note": "First registered account becomes Admin. Email verification is a stub in v1 — see /api/auth/verify-email."}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _rate_limit(f"login:{request.client.host}", settings.rate_limit_login_per_minute)
    user = db.query(models.User).filter_by(email=body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid login credentials")
    audit(db, user.id, "user.login", "user", user.id)
    return {"token": create_token(user.id, user.email, user.role), "user": user_out(user)}


@app.get("/api/auth/me")
def me(user: models.User = Depends(get_current_user)):
    return user_out(user)


@app.post("/api/auth/logout")
def logout(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    audit(db, user.id, "user.logout", "user", user.id)
    return {"ok": True, "note": "Tokens are stateless JWTs — logout clears the token client-side."}


@app.post("/api/auth/verify-email")
def verify_email(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Stub, labelled as such: v1 has no email provider; verification is
    recorded directly so the flow is testable end to end."""
    user.email_verified = True
    db.commit()
    audit(db, user.id, "user.verify_email_stub", "user", user.id)
    return {"ok": True, "email_verified": True,
            "note": "STUB — no real email is sent in v1; verification recorded directly."}


@app.post("/api/auth/forgot-password")
def forgot_password(body: ResetRequestIn, request: Request, db: Session = Depends(get_db)):
    _rate_limit(f"forgot:{request.client.host}", 10)
    user = db.query(models.User).filter_by(email=body.email.strip().lower()).first()
    # Always return the same shape (no user enumeration); token only when found.
    if user:
        raw = secrets.token_urlsafe(32)
        db.add(models.PasswordReset(user_id=user.id,
                                    token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                                    expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.commit()
        audit(db, user.id, "user.forgot_password", "user", user.id)
        return {"ok": True, "dev_reset_token": raw,
                "note": "DEV ONLY — no email provider is configured in v1, so the reset token is returned here. Never do this in production."}
    return {"ok": True}


@app.post("/api/auth/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    th = hashlib.sha256(body.token.encode()).hexdigest()
    rec = db.query(models.PasswordReset).filter_by(token_hash=th, used=False).first()
    if not rec or rec.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = db.query(models.User).filter_by(id=rec.user_id).first()
    user.password_hash = hash_password(body.new_password)
    rec.used = True
    db.commit()
    audit(db, user.id, "user.reset_password", "user", user.id)
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_password(body: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.get("current_password", ""), user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(body.get("new_password", ""))
    db.commit()
    return {"ok": True}


# ---- collections ----
@app.get("/api/collections")
def list_collections(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    cols = db.query(models.Collection).filter(models.Collection.id.in_(list(allowed)) if allowed else models.Collection.id == "__none__").all()
    out = []
    for c in cols:
        out.append({"id": c.id, "name": c.name, "description": c.description,
                    "confidentiality": c.confidentiality, "is_public": c.is_public,
                    "documents": db.query(models.Document).filter_by(collection_id=c.id).count(),
                    "owner_id": c.owner_id})
    return out


@app.post("/api/collections")
def create_collection(body: CollectionIn, user: models.User = Depends(require_role("admin", "reviewer")),
                      db: Session = Depends(get_db)):
    coll = models.Collection(name=body.name, description=body.description,
                             confidentiality=body.confidentiality, is_public=body.is_public,
                             owner_id=user.id)
    db.add(coll)
    db.commit()
    db.add(models.CollectionAccess(user_id=user.id, collection_id=coll.id, permission="write"))
    db.commit()
    audit(db, user.id, "collection.create", "collection", coll.id, {"name": coll.name})
    return {"id": coll.id, "name": coll.name, "is_public": coll.is_public}


@app.post("/api/collections/{coll_id}/grant")
def grant_access(coll_id: str, body: dict, user: models.User = Depends(require_role("admin")),
                 db: Session = Depends(get_db)):
    target = db.query(models.User).filter_by(email=body.get("email", "").strip().lower()).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not db.query(models.CollectionAccess).filter_by(user_id=target.id, collection_id=coll_id).first():
        db.add(models.CollectionAccess(user_id=target.id, collection_id=coll_id,
                                       permission=body.get("permission", "read")))
        db.commit()
    audit(db, user.id, "collection.grant", "collection", coll_id, {"granted_to": target.email})
    return {"ok": True}


# ---- documents ----
@app.post("/api/documents")
async def upload_document(request: Request, file: UploadFile = File(...),
                          collection_id: str = Form(...), as_version_of: str = Form(""),
                          user: models.User = Depends(require_role("admin", "reviewer")),
                          db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25 MB)")
    if not file.filename.lower().endswith((".pdf", ".docx", ".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX and TXT are supported in v1")
    digest = sha256_of(data)
    existing = db.query(models.Document).filter_by(sha256=digest).first()
    if existing and not as_version_of:
        return JSONResponse(status_code=409, content={
            "detail": "Duplicate detected — this file matches an existing document.",
            "duplicate_of": {"id": existing.id, "title": existing.title, "version": existing.current_version},
            "hint": "Re-upload with as_version_of=<document id> to create a new version instead."})
    if as_version_of:
        doc = db.query(models.Document).filter_by(id=as_version_of).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document to version not found")
        doc.current_version += 1
        doc.sha256 = digest
        db.commit()
        # Mark prior answers citing this doc as potentially stale.
        for q in db.query(models.Question).all():
            try:
                cits = json.loads(q.citations_json or "[]")
            except Exception:
                cits = []
            if any(c.get("document_id") == doc.id for c in cits) and q.status != "stale":
                q.status = "stale"
        db.commit()
    else:
        coll = db.query(models.Collection).filter_by(id=collection_id).first()
        if not coll:
            raise HTTPException(status_code=404, detail="Collection not found")
        doc = models.Document(collection_id=collection_id, title=file.filename, doc_type="contract",
                              sha256=digest, status="uploaded", created_by=user.id)
        db.add(doc)
        db.commit()
    try:
        text, quality, notes = parse_bytes(file.filename, data)
        doc.parse_quality, doc.parse_notes = quality, notes
        if len(text.strip()) < 50:
            raise ValueError("No extractable text found in file")
        stats = ingest_document(db, doc, text, filename=file.filename)
    except Exception as exc:
        doc.status = "failed"
        doc.error = str(exc)[:500]
        db.commit()
        audit(db, user.id, "document.ingest_failed", "document", doc.id, {"error": doc.error})
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {exc}")
    audit(db, user.id, "document.upload", "document", doc.id, {"title": doc.title, **stats})
    return {**doc_out(db, doc), "ingestion": stats}


@app.get("/api/documents")
def list_documents(collection_id: str = "", status: str = "", q: str = "",
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    query = db.query(models.Document)
    if allowed:
        query = query.filter(models.Document.collection_id.in_(list(allowed)))
    else:
        return []
    if collection_id:
        query = query.filter_by(collection_id=collection_id)
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(models.Document.title.contains(q))
    return [doc_out(db, d) for d in query.order_by(models.Document.created_at.desc()).all()]


@app.get("/api/clauses/{clause_id}")
def clause_detail(clause_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(models.Clause).filter_by(id=clause_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Clause not found")
    doc = db.query(models.Document).filter_by(id=c.document_id).first()
    if doc.collection_id not in allowed_collection_ids(db, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"id": c.id, "document_id": c.document_id, "document_title": doc.title,
            "clause_no": c.clause_no, "section": c.section_path, "heading": c.heading,
            "text": c.text, "page_ref": c.page_ref, "is_current": c.is_current}


@app.get("/api/documents/{doc_id}")
def document_detail(doc_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.collection_id not in allowed_collection_ids(db, user):
        raise HTTPException(status_code=403, detail="Access denied to this document's collection")
    clauses = db.query(models.Clause).filter_by(document_id=doc_id).order_by(models.Clause.clause_no).all()
    obligations = db.query(models.Obligation).filter_by(document_id=doc_id).all()
    versions = db.query(models.DocVersion).filter_by(document_id=doc_id).order_by(models.DocVersion.version_no).all()
    edges = db.query(models.GraphEdge).filter_by(document_id=doc_id).all()
    audit(db, user.id, "document.view", "document", doc_id)
    return {**doc_out(db, doc),
            "clauses": [{"id": c.id, "clause_no": c.clause_no, "section": c.section_path,
                         "heading": c.heading, "text": c.text, "page_ref": c.page_ref,
                         "is_current": c.is_current, "superseded_by": c.superseded_by_clause_id} for c in clauses],
            "obligations": [{"id": o.id, "party": o.party, "obligation": o.obligation_text,
                             "type": o.obligation_type, "effective_date": o.effective_date,
                             "due_date": o.due_date, "penalty": o.penalty, "status": o.status,
                             "source_clause_no": o.source_clause_no} for o in obligations],
            "versions": [{"version_no": v.version_no, "created_at": str(v.created_at),
                          "chars": len(v.text or "")} for v in versions],
            "graph_edges": len(edges)}


@app.post("/api/documents/{doc_id}/reprocess")
def reprocess(doc_id: str, user: models.User = Depends(require_role("admin", "reviewer")),
              db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    version = db.query(models.DocVersion).filter_by(document_id=doc_id).order_by(
        models.DocVersion.version_no.desc()).first()
    if not version or not version.text:
        raise HTTPException(status_code=400, detail="No stored text to reprocess")
    doc.status = "processing"
    db.commit()
    try:
        stats = ingest_document(db, doc, version.text, filename=version.storage_key)
    except Exception as exc:
        doc.status = "failed"
        doc.error = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=422, detail=f"Reprocessing failed: {exc}")
    audit(db, user.id, "document.reprocess", "document", doc_id, stats)
    return {**doc_out(db, doc), "ingestion": stats}


# ---- AI Ask ----
@app.post("/api/ask")
async def ask(body: AskIn, request: Request, user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    _rate_limit(f"ask:{request.client.host}:{user.id}", settings.rate_limit_ask_per_minute)
    started = time.time()
    # Injection in the QUESTION itself is treated as data: it is answered
    # from evidence only; it can never change access rules or tools.
    question = body.question.strip()
    retrieved = retrieve(db, user, question, collection_ids=body.collection_ids, top_k=body.top_k,
                         modes=("vector", "bm25", "graph", "rerank"))
    latency_ms = int((time.time() - started) * 1000)
    from .retrieval import ABSTAIN_COVERAGE_THRESHOLD, ABSTAIN_TOP_SCORE_THRESHOLD
    if retrieved and retrieved[0]["score"] < ABSTAIN_TOP_SCORE_THRESHOLD:
        # Best clause is not really about the question: abstain rather
        # than quote irrelevant clauses as if they answered it.
        retrieved = []
    if retrieved and max(c.get("coverage", 0) for c in retrieved[:3]) < ABSTAIN_COVERAGE_THRESHOLD:
        # The question's distinctive terms appear in no retrieved clause.
        retrieved = []
    if not retrieved:
        q = models.Question(user_id=user.id, question=question, answer_json=json.dumps(
            {"answer": "The answer is not in the provided documents.", "mode": "abstention"}),
            citations_json="[]", confidence=0.0, status="abstained", mode="extractive",
            prompt_version=PROMPT_VERSION, latency_ms=latency_ms)
        db.add(q)
        db.commit()
        audit(db, user.id, "question.ask_abstained", "question", q.id, {"question": redact_pii(question)})
        return {"question_id": q.id, "status": "abstained",
                "answer": "The answer is not in the provided documents.",
                "searched": {"collections": sorted(allowed_collection_ids(db, user)),
                             "clauses_considered": 0,
                             "note": "No clause in collections you can access scored above the retrieval threshold. Try narrower terms, or add the relevant document."},
                "citations": [], "confidence": 0.0, "mode": "abstention", "tokens": 0, "cost_usd": 0.0,
                "latency_ms": latency_ms}
    gen = await generate_answer(question, retrieved)
    clause_text = {c["clause_id"]: c["text"] for c in retrieved}
    check = check_answer(gen["claims"], clause_text)
    if gen["mode"].startswith("llm") and not check["passed"]:
        # Faithfulness gate: fall back to extractive quoting of the same
        # retrieved clauses rather than showing an unsupported answer.
        from .generation import extractive_answer
        gen = extractive_answer(question, retrieved)
        check = check_answer(gen["claims"], clause_text)
    if not check["supported_claims"]:
        q = models.Question(user_id=user.id, question=question, answer_json=json.dumps(
            {"answer": "The answer is not in the provided documents.", "mode": "abstention"}),
            citations_json="[]", confidence=0.0, status="abstained", mode=gen["mode"],
            prompt_version=PROMPT_VERSION, latency_ms=latency_ms)
        db.add(q)
        db.commit()
        audit(db, user.id, "question.ask_abstained", "question", q.id, {"reason": "faithfulness_gate"})
        return {"question_id": q.id, "status": "abstained",
                "answer": "The answer is not in the provided documents. The retrieved clauses did not support a verifiable answer.",
                "searched": {"collections": sorted(allowed_collection_ids(db, user)),
                             "clauses_considered": len(retrieved),
                             "retrieved": [{"clause_id": c["clause_id"], "document_title": c["document_title"],
                                            "clause_no": c["clause_no"]} for c in retrieved]},
                "citations": [], "confidence": 0.0, "mode": "abstention",
                "faithfulness": check["faithfulness"], "tokens": gen.get("tokens", 0),
                "cost_usd": gen.get("cost_usd", 0.0), "latency_ms": latency_ms}
    # Confidence: supported-claim share, boosted by multi-document agreement.
    docs_cited = len({c["document_id"] for c in retrieved[:len(check["supported_claims"])]})
    confidence = round(min(0.98, check["faithfulness"] * 0.8 + 0.1 * min(docs_cited, 2) + 0.05), 2)
    status = "answered" if confidence >= settings.confidence_threshold else "narrowed"
    citations = []
    for i, claim in enumerate(check["supported_claims"], 1):
        c = next((x for x in retrieved if x["clause_id"] == claim["clause_id"]), None)
        if c:
            citations.append({**c, "citation_no": i, "support": claim["support"]})
    total_latency = int((time.time() - started) * 1000)
    q = models.Question(user_id=user.id, question=question,
                        answer_json=json.dumps({"answer": gen["text"], "mode": gen["mode"]}),
                        citations_json=json.dumps(citations), confidence=confidence, status=status,
                        mode=gen["mode"], model=gen.get("model", ""), prompt_version=PROMPT_VERSION,
                        tokens=gen.get("tokens", 0), cost_usd=gen.get("cost_usd", 0.0),
                        latency_ms=total_latency)
    db.add(q)
    db.commit()
    audit(db, user.id, "question.ask", "question", q.id,
          {"question": redact_pii(question), "citations": len(citations),
           "faithfulness": check["faithfulness"], "model": gen.get("model", ""), "mode": gen["mode"]})
    return {"question_id": q.id, "status": status, "answer": gen["text"],
            "citations": citations, "confidence": confidence,
            "confidence_basis": {"supporting_clauses": len(citations),
                                 "documents_cited": docs_cited,
                                 "faithfulness": check["faithfulness"],
                                 "note": "Confidence reflects cited-clause support and cross-document agreement — never a bare percentage."},
            "mode": gen["mode"], "model": gen.get("model", ""), "tokens": gen.get("tokens", 0),
            "cost_usd": gen.get("cost_usd", 0.0), "latency_ms": total_latency,
            "retrieval_trace": [{"clause_id": c["clause_id"], "score": c["score"], "trace": c["trace"]} for c in retrieved]}


@app.get("/api/history")
def history(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    qs = db.query(models.Question).filter_by(user_id=user.id).order_by(models.Question.created_at.desc()).limit(100).all()
    out = []
    for q in qs:
        try:
            ans = json.loads(q.answer_json or "{}").get("answer", "")
            cits = json.loads(q.citations_json or "[]")
        except Exception:
            ans, cits = "", []
        out.append({"id": q.id, "question": q.question, "answer": ans, "citations": cits,
                    "confidence": q.confidence, "status": q.status, "mode": q.mode,
                    "model": q.model, "tokens": q.tokens, "cost_usd": q.cost_usd,
                    "latency_ms": q.latency_ms, "created_at": str(q.created_at)})
    return out


@app.get("/api/history/{qid}")
def history_one(qid: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(models.Question).filter_by(id=qid).first()
    if not q or (q.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"id": q.id, "question": q.question,
            "answer": json.loads(q.answer_json or "{}").get("answer", ""),
            "citations": json.loads(q.citations_json or "[]"), "confidence": q.confidence,
            "status": q.status, "mode": q.mode, "model": q.model,
            "prompt_version": q.prompt_version, "tokens": q.tokens, "cost_usd": q.cost_usd,
            "created_at": str(q.created_at)}


# ---- compare + conflicts ----
def _word_diff(a: str, b: str) -> dict:
    aw, bw = set(re.findall(r"[a-z0-9₹,]+", a.lower())), set(re.findall(r"[a-z0-9₹,]+", b.lower()))
    return {"only_in_a": sorted(aw - bw)[:20], "only_in_b": sorted(bw - aw)[:20],
            "shared": len(aw & bw)}


@app.post("/api/compare")
def compare(body: CompareIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    docs = {d.id: d for d in db.query(models.Document).filter(models.Document.id.in_([body.doc_a_id, body.doc_b_id])).all()}
    for d in docs.values():
        if d.collection_id not in allowed:
            raise HTTPException(status_code=403, detail="Access denied to one of the documents")
    if len(docs) < 2:
        raise HTTPException(status_code=404, detail="One or both documents not found")
    ca = db.query(models.Clause).filter_by(document_id=body.doc_a_id, is_current=True).all()
    cb = db.query(models.Clause).filter_by(document_id=body.doc_b_id, is_current=True).all()
    pairs = []
    for x in ca:
        best, best_score = None, 0.0
        xt = set(re.findall(r"[a-z]+", (x.heading + " " + x.text).lower()))
        for y in cb:
            yt = set(re.findall(r"[a-z]+", (y.heading + " " + y.text).lower()))
            score = len(xt & yt) / max(len(xt | yt), 1)
            if score > best_score:
                best, best_score = y, score
        if best and best_score > 0.15:
            pairs.append({"clause_a": {"id": x.id, "clause_no": x.clause_no, "heading": x.heading, "text": x.text},
                          "clause_b": {"id": best.id, "clause_no": best.clause_no, "heading": best.heading, "text": best.text},
                          "similarity": round(best_score, 3), "diff": _word_diff(x.text, best.text)})
    conflicts = db.query(models.Conflict).filter(
        ((models.Conflict.clause_a_id.in_([c.id for c in ca])) |
         (models.Conflict.clause_b_id.in_([c.id for c in ca])))).all()
    audit(db, user.id, "document.compare", "document", body.doc_a_id, {"with": body.doc_b_id, "pairs": len(pairs)})
    return {"doc_a": docs[body.doc_a_id].title, "doc_b": docs[body.doc_b_id].title,
            "pairs": pairs,
            "conflict_candidates": [{"id": c.id, "topic": c.topic, "party": c.party,
                                     "status": c.status, "explanation": c.explanation} for c in conflicts],
            "note": "Differences are shown for human review. Conflict candidates are NOT legal verdicts."}


@app.get("/api/conflicts")
def list_conflicts(status: str = "", user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    query = db.query(models.Conflict)
    if status:
        query = query.filter_by(status=status)
    out = []
    for c in query.order_by(models.Conflict.created_at.desc()).all():
        a = db.query(models.Clause).filter_by(id=c.clause_a_id).first()
        b = db.query(models.Clause).filter_by(id=c.clause_b_id).first()
        if not a or not b:
            continue
        da = db.query(models.Document).filter_by(id=a.document_id).first()
        db_ = db.query(models.Document).filter_by(id=b.document_id).first()
        if da.collection_id not in allowed or db_.collection_id not in allowed:
            continue
        out.append({"id": c.id, "topic": c.topic, "party": c.party, "status": c.status,
                    "explanation": c.explanation,
                    "clause_a": {"id": a.id, "document": da.title, "clause_no": a.clause_no, "text": a.text},
                    "clause_b": {"id": b.id, "document": db_.title, "clause_no": b.clause_no, "text": b.text}})
    return out


@app.post("/api/conflicts/{cid}/{action}")
def conflict_action(cid: str, action: str, user: models.User = Depends(require_role("admin", "reviewer")),
                    db: Session = Depends(get_db)):
    if action not in ("confirm", "dismiss"):
        raise HTTPException(status_code=400, detail="action must be confirm or dismiss")
    c = db.query(models.Conflict).filter_by(id=cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="Conflict not found")
    c.status = "confirmed" if action == "confirm" else "dismissed"
    db.commit()
    audit(db, user.id, f"conflict.{action}", "conflict", cid)
    return {"ok": True, "status": c.status}


# ---- obligations ----
@app.get("/api/obligations")
def list_obligations(party: str = "", obligation_type: str = "", status: str = "",
                     document_id: str = "", due_before: str = "", due_after: str = "",
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    query = db.query(models.Obligation).join(models.Document, models.Obligation.document_id == models.Document.id)
    if allowed:
        query = query.filter(models.Document.collection_id.in_(list(allowed)))
    else:
        return []
    if party:
        query = query.filter(models.Obligation.party.contains(party))
    if obligation_type:
        query = query.filter(models.Obligation.obligation_type == obligation_type)
    if status:
        query = query.filter(models.Obligation.status == status)
    if document_id:
        query = query.filter(models.Obligation.document_id == document_id)
    if due_before:
        query = query.filter(models.Obligation.due_date != "", models.Obligation.due_date <= due_before)
    if due_after:
        query = query.filter(models.Obligation.due_date != "", models.Obligation.due_date >= due_after)
    out = []
    for o in query.order_by(models.Obligation.due_date).all():
        d = db.query(models.Document).filter_by(id=o.document_id).first()
        out.append({"id": o.id, "document": d.title if d else "", "document_id": o.document_id,
                    "party": o.party, "obligation": o.obligation_text, "type": o.obligation_type,
                    "effective_date": o.effective_date, "due_date": o.due_date, "penalty": o.penalty,
                    "status": o.status, "source_clause_no": o.source_clause_no, "clause_id": o.clause_id})
    return out


@app.get("/api/obligations/export")
def export_obligations(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    import csv
    rows = list_obligations(user=user, db=db)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["document", "party", "obligation", "type", "effective_date",
                                        "due_date", "penalty", "status", "source_clause_no"])
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in w.fieldnames})
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=obligation-register.csv"})


# ---- knowledge graph ----
@app.get("/api/graph")
def graph(collection_id: str = "", doc_id: str = "", user: models.User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    edges = db.query(models.GraphEdge)
    if doc_id:
        edges = edges.filter(models.GraphEdge.document_id == doc_id)
    edges = edges.all()
    nodes: dict[str, dict] = {}
    out_edges = []
    for e in edges:
        doc = db.query(models.Document).filter_by(id=e.document_id).first()
        if doc and doc.collection_id not in allowed:
            continue
        for t, i, label in ((e.src_type, e.src_id, e.src_label), (e.dst_type, e.dst_id, e.dst_label)):
            if i not in nodes:
                nodes[i] = {"id": i, "type": t, "label": label or i[:40]}
        out_edges.append({"id": e.id, "source": e.src_id, "target": e.dst_id, "rel": e.rel_type,
                          "confidence": e.confidence})
    if collection_id:
        docs = {d.id for d in db.query(models.Document).filter_by(collection_id=collection_id).all()}
        out_edges = [e for e in out_edges if True]
    return {"nodes": list(nodes.values()), "edges": out_edges,
            "note": "CONFLICTS_WITH edges are candidates for human confirmation, not settled facts."}


# ---- evidence pack ----
@app.post("/api/evidence-pack")
def evidence_pack(body: EvidenceIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(models.Question).filter_by(id=body.question_id).first()
    if not q or (q.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Answer not found")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph("RegLens — Evidence Pack", styles["Title"]),
             Paragraph(f"Audit reference: {q.id}", styles["Normal"]),
             Paragraph(f"Generated: {q.created_at} UTC &nbsp;|&nbsp; User: {user.email} &nbsp;|&nbsp; "
                       f"Model: {q.model or 'extractive'} &nbsp;|&nbsp; Prompt version: {q.prompt_version} &nbsp;|&nbsp; "
                       f"Status: {q.status}", styles["Normal"]),
             Spacer(1, 6 * mm),
             Paragraph("Question", styles["Heading2"]),
             Paragraph(q.question, styles["Normal"]),
             Paragraph("Answer", styles["Heading2"]),
             Paragraph((json.loads(q.answer_json or '{}').get("answer", "") or "").replace("\n", "<br/>"), styles["Normal"]),
             Paragraph("Cited clauses", styles["Heading2"])]
    for c in json.loads(q.citations_json or "[]"):
        story.append(Paragraph(f"<b>{c.get('document_title', '')} (v{c.get('version', '')}), "
                               f"Clause {c.get('clause_no', '')} — {c.get('heading', '')}, p. {c.get('page_ref', '')}</b>",
                               styles["Normal"]))
        story.append(Paragraph((c.get("text", "") or "").replace("\n", " "), styles["Normal"]))
        story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("This pack lets a second reviewer reproduce the answer without opening RegLens. "
                           "RegLens provides evidence, not legal advice.", styles["Normal"]))
    SimpleDocTemplate(buf, pagesize=A4).build(story)
    audit(db, user.id, "evidence_pack.export", "question", q.id)
    return StreamingResponse(io.BytesIO(buf.getvalue()), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=evidence-pack-{q.id[:8]}.pdf"})


# ---- overview / admin ----
@app.get("/api/overview")
def overview(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = allowed_collection_ids(db, user)
    docs = db.query(models.Document).filter(
        models.Document.collection_id.in_(list(allowed)) if allowed else models.Document.id == "__none__").all()
    doc_ids = {d.id for d in docs}
    return {
        "total_documents": len(docs),
        "indexed_clauses": db.query(models.Clause).filter(models.Clause.document_id.in_(list(doc_ids)) if doc_ids else models.Clause.id == "__none__").count(),
        "active_collections": len(allowed),
        "pending_ingestion": sum(1 for d in docs if d.status not in ("ready", "failed")),
        "failed_ingestion": sum(1 for d in docs if d.status == "failed"),
        "detected_conflicts": db.query(models.Conflict).filter_by(status="candidate").count(),
        "upcoming_obligations": db.query(models.Obligation).filter(
            models.Obligation.document_id.in_(list(doc_ids)) if doc_ids else models.Obligation.id == "__none__",
            models.Obligation.status == "active").count(),
        "recent_questions": db.query(models.Question).filter_by(user_id=user.id).count(),
        "total_tokens": db.query(models.Question).filter_by(user_id=user.id).with_entities(
            __import__("sqlalchemy").func.coalesce(__import__("sqlalchemy").func.sum(models.Question.tokens), 0)).scalar() or 0,
        "total_cost_usd": round(db.query(models.Question).filter_by(user_id=user.id).with_entities(
            __import__("sqlalchemy").func.coalesce(__import__("sqlalchemy").func.sum(models.Question.cost_usd), 0)).scalar() or 0, 6),
        "demo_data_note": "Seeded documents are labelled DEMO / SYNTHETIC. Counts above are real DB counts, not sample analytics.",
    }


@app.get("/api/admin/users")
def admin_users(user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.query(models.User).all()]


@app.patch("/api/admin/users/{uid}/role")
def admin_set_role(uid: str, body: RoleIn, user: models.User = Depends(require_role("admin")),
                   db: Session = Depends(get_db)):
    if body.role not in ("admin", "reviewer", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    target = db.query(models.User).filter_by(id=uid).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = body.role
    db.commit()
    audit(db, user.id, "admin.role_change", "user", uid, {"role": body.role})
    return user_out(target)


@app.get("/api/admin/audit")
def admin_audit(limit: int = 100, user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "user_id": r.user_id, "action": r.action, "object_type": r.object_type,
             "object_id": r.object_id, "detail": r.detail_json, "created_at": str(r.created_at)} for r in rows]


@app.get("/api/admin/health")
def admin_health(user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    docs = db.query(models.Document).all()
    return {"documents_by_status": {s: sum(1 for d in docs if d.status == s) for s in
                                    ["uploaded", "processing", "extracting", "indexing", "ready", "failed"]},
            "failed": [{"id": d.id, "title": d.title, "error": d.error} for d in docs if d.status == "failed"],
            "users": db.query(models.User).count(),
            "questions": db.query(models.Question).count(),
            "mode": "extractive (no LLM)" if settings.demo_mode else "llm",
            "model": settings.groq_model if not settings.demo_mode else "extractive"}


@app.post("/api/admin/seed")
def admin_seed(user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    result = seed_demo(db, user.id)
    audit(db, user.id, "admin.seed_demo", "seed", "", result)
    return result


@app.get("/api/admin/evals/latest")
def evals_latest(user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    run = db.query(models.EvalRun).order_by(models.EvalRun.created_at.desc()).first()
    if not run:
        return {"run": None, "note": "No evaluation run yet. POST /api/admin/evals/run (admin) to run the golden set."}
    return {"run_id": run.id, "dataset_version": run.dataset_version, "model": run.model,
            "prompt_version": run.prompt_version, "created_at": str(run.created_at),
            "scores": json.loads(run.scores_json or "{}")}


@app.post("/api/admin/evals/run")
def evals_run(user: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    from evals.run_eval import run_all
    scores = run_all(db, user)
    run = models.EvalRun(dataset_version="golden-v1", scores_json=json.dumps(scores),
                         model=settings.groq_model if not settings.demo_mode else "extractive",
                         prompt_version=PROMPT_VERSION)
    db.add(run)
    db.commit()
    audit(db, user.id, "admin.eval_run", "eval", run.id, {"ablation": scores.get("ablation", {})})
    return scores


@app.get("/api/dashboard")
def dashboard_alias(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return overview(user=user, db=db)
