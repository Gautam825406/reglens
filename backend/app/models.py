"""RegLens data model (PRD §9). Roles: admin / reviewer / viewer.
Collection access is enforced in retrieval (see retrieval.py), not in UI.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from .database import Base


def _id():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")  # admin | reviewer | viewer
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Collection(Base):
    __tablename__ = "collections"
    id = Column(String, primary_key=True, default=_id)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    confidentiality = Column(String, default="internal")  # public | internal | confidential
    is_public = Column(Boolean, default=True)  # visible/retrievable by all signed-in users
    owner_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class CollectionAccess(Base):
    __tablename__ = "collection_access"
    id = Column(String, primary_key=True, default=_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    collection_id = Column(String, ForeignKey("collections.id"), nullable=False)
    permission = Column(String, default="read")  # read | write


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_id)
    collection_id = Column(String, ForeignKey("collections.id"), nullable=False)
    title = Column(String, nullable=False)
    doc_type = Column(String, default="contract")  # contract | amendment | circular | policy
    sha256 = Column(String, index=True)
    status = Column(String, default="uploaded")  # uploaded|processing|extracting|indexing|ready|failed
    parse_quality = Column(Float, default=1.0)  # 0..1, low for scanned/poor text
    parse_notes = Column(String, default="")
    current_version = Column(Integer, default=1)
    is_demo = Column(Boolean, default=False)
    created_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    error = Column(String, default="")


class DocVersion(Base):
    __tablename__ = "document_versions"
    id = Column(String, primary_key=True, default=_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    storage_key = Column(String, default="")
    text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Clause(Base):
    __tablename__ = "clauses"
    id = Column(String, primary_key=True, default=_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    version_id = Column(String, ForeignKey("document_versions.id"))
    clause_no = Column(String, default="")  # e.g. "7.2"
    section_path = Column(String, default="")
    heading = Column(String, default="")
    text = Column(Text, nullable=False)
    page_ref = Column(Integer, default=1)
    embedding_json = Column(Text, default="[]")  # TF-hash vector (derived store)
    superseded_by_clause_id = Column(String, default="")
    is_current = Column(Boolean, default=True)


class Extraction(Base):
    __tablename__ = "extractions"
    id = Column(String, primary_key=True, default=_id)
    clause_id = Column(String, ForeignKey("clauses.id"), nullable=False)
    field_type = Column(String, nullable=False)  # party | date | obligation | penalty | notice | reference
    value = Column(Text, default="")
    confidence = Column(Float, default=0.8)
    model_version = Column(String, default="rules-v1")


class Obligation(Base):
    __tablename__ = "obligations"
    id = Column(String, primary_key=True, default=_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    clause_id = Column(String, ForeignKey("clauses.id"))
    party = Column(String, default="")
    obligation_text = Column(Text, default="")
    obligation_type = Column(String, default="payment")  # payment|termination|delivery|compliance|notice|other
    effective_date = Column(String, default="")
    due_date = Column(String, default="")
    penalty = Column(String, default="")
    status = Column(String, default="active")  # active | fulfilled | overdue | superseded
    source_clause_no = Column(String, default="")


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    id = Column(String, primary_key=True, default=_id)
    src_type = Column(String, nullable=False)  # Document | Clause | Party | Obligation | DateEvent | Regulation
    src_id = Column(String, nullable=False)
    src_label = Column(String, default="")
    dst_type = Column(String, nullable=False)
    dst_id = Column(String, nullable=False)
    dst_label = Column(String, default="")
    rel_type = Column(String, nullable=False)  # CONTAINS|BINDS|IMPOSES|AMENDS|SUPERSEDES|REFERENCES|CONFLICTS_WITH
    confidence = Column(Float, default=0.9)
    document_id = Column(String, ForeignKey("documents.id"))


class Question(Base):
    __tablename__ = "questions"
    id = Column(String, primary_key=True, default=_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer_json = Column(Text, default="{}")
    citations_json = Column(Text, default="[]")
    confidence = Column(Float, default=0.0)
    status = Column(String, default="answered")  # answered | narrowed | abstained | stale
    mode = Column(String, default="extractive")  # extractive | llm
    model = Column(String, default="")
    prompt_version = Column(String, default="")
    tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True, default=_id)
    user_id = Column(String, default="")
    action = Column(String, nullable=False)
    object_type = Column(String, default="")
    object_id = Column(String, default="")
    detail_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id = Column(String, primary_key=True, default=_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class Conflict(Base):
    __tablename__ = "conflicts"
    id = Column(String, primary_key=True, default=_id)
    clause_a_id = Column(String, ForeignKey("clauses.id"), nullable=False)
    clause_b_id = Column(String, ForeignKey("clauses.id"), nullable=False)
    topic = Column(String, default="")
    party = Column(String, default="")
    status = Column(String, default="candidate")  # candidate | confirmed | dismissed
    explanation = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id = Column(String, primary_key=True, default=_id)
    dataset_version = Column(String, default="golden-v1")
    scores_json = Column(Text, default="{}")
    model = Column(String, default="")
    prompt_version = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
