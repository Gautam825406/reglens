# RegLens architecture

## Services (separate, REST only)

- `backend/` — FastAPI app (`app/main.py`), SQLAlchemy models, ingestion,
  retrieval, generation, evals, tests. Own `requirements.txt`, `Dockerfile`, `README.md`.
- `frontend/` — Vite + React + TypeScript (`src/App.tsx`, `src/api.ts`).
  Own `package.json`, `Dockerfile`, `README.md`. Calls the backend only via
  `VITE_API_URL`.
- `docker-compose.yml` — `api`, `worker`, `frontend`, `postgres` (pgvector
  image), `redis` (broker for the Celery scale path).

## Data flow

Ingestion: upload → object bytes hashed (SHA-256 duplicate detection) →
parse → clause chunking → extraction → obligations → graph edges →
hash-embedding index → status Ready. Failures keep their error and are
retried by the worker.

Question: access-filtered retrieval → merge/re-rank → generation →
faithfulness gate → answer + citations + audit. Updates to a document
mark prior answers citing it `stale`.

## Key decisions

- **Clause-aware chunking** over fixed-token windows: legal meaning lives
  in the clause; citations must resolve to whole clauses.
- **Access control in retrieval**, not in the UI: `allowed_collection_ids`
  filters clauses before BM25/vector/graph scoring, so a restricted clause
  can never be cited, ranked, or sent to the LLM.
- **Faithfulness as a gate, not a score**: lexical claim-support check;
  unsupported claims are dropped; if none survive, the answer abstains.
- **Extractive fallback**: with no Groq key, answers quote clauses
  directly and say so. No faked generation.
- **TF-hash embeddings in v1**: deterministic, no model download; the
  swap to sentence-transformers is one function (`retrieval.hash_embedding`).
- **PostgreSQL is the source of truth**; vectors and graph edges are
  derived and rebuildable. SQLite is the local-dev default only.
- **Document text is data**: injection patterns in documents are flagged
  and never executed; the generator only ever receives access-filtered
  clauses.
