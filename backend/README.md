# RegLens — Backend

FastAPI + Pydantic backend for RegLens, the citation-grounded GraphRAG
platform for contracts & compliance. SQLite for local dev; Postgres
(+pgvector in Docker Compose) is the deployed path — same models, same code.

## Run (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # optional; GROQ_API_KEY is optional
python run.py              # http://localhost:8000  (docs: /docs)
```

Without `GROQ_API_KEY` the API runs in **extractive mode**: answers quote
retrieved clauses directly and label themselves `extractive (no LLM)`.
With a key set, generation uses Groq `openai/gpt-oss-120b` and every claim
is still checked by the faithfulness gate before display.

## Tests

```bash
pytest -q            # from this directory
```

## Evaluation

```bash
python -m evals.run_eval     # writes evals/results.json (4-way ablation)
```

## Layout

| File | What it does |
| --- | --- |
| `app/main.py` | FastAPI routes: auth, collections, documents, ask, compare, conflicts, obligations, graph, evidence packs, admin, evals |
| `app/models.py` | SQLAlchemy models (PRD §9) |
| `app/chunking.py` | Clause-aware chunking (never splits a clause from its heading) |
| `app/extraction.py` | Deterministic rules-v1 extraction (parties, dates, penalties, obligations) |
| `app/retrieval.py` | Hybrid retrieval: BM25 + TF-hash vector + graph expansion, access-filtered before ranking |
| `app/faithfulness.py` | Real lexical claim-support check (not a hardcoded pass) |
| `app/generation.py` | Groq client + honest extractive fallback |
| `app/ingestion.py` | Parse (pypdf/python-docx) → chunk → extract → graph → index |
| `app/seed.py` | Synthetic DEMO seed data (labelled as such) |
| `app/security.py` | PBKDF2 hashing, HMAC JWT, PII redaction, injection detection |
| `evals/` | Golden set (47 cases) + ablation runner |
| `tests/` | Unit, integration and security tests |

## Honest limits (v1)

- Embeddings are deterministic TF-hash vectors, not sentence-transformers
  (documented swap-in; see root README). BM25 + graph carry the signal.
- Ingestion runs in-process in v1; Celery + Redis is the scale path in
  Compose (worker service runs the same ingest function).
- The LoRA extractor from the PRD is NOT built in v1 — extraction is the
  deterministic rules-v1 extractor, measured against the golden set.
- Email verification and password-reset email are stubs, labelled as such;
  reset tokens are returned in dev only.
- No legal advice: RegLens retrieves and summarises evidence for a
  qualified reviewer; conflict candidates are never legal verdicts.
