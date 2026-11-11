# RegLens — Grounded GraphRAG for Contracts & Compliance

> **Understand Every Clause. Trust Every Answer.**

RegLens reads contracts, policies and regulatory circulars as a structured
knowledge graph — not just as text chunks — and answers questions only with
clause-level citations a lawyer, auditor or compliance officer can verify.
If the evidence is not in the documents, it says so plainly.

**RegLens provides evidence, not legal advice.**

## Layout — frontend and backend are completely separate

| Part | Path | Stack |
| --- | --- | --- |
| **Backend** | [`backend/`](backend/) | Python 3.11+ · FastAPI + Pydantic · SQLAlchemy · pytest |
| **Frontend** | [`frontend/`](frontend/) | Vite + React + TypeScript |
| Eval harness | `backend/evals/` (+ copy of golden set in `evals/`) | 47-case golden set, four-way ablation |

The two communicate **only over the REST API** (frontend → backend via
`VITE_API_URL`). No backend code lives in `frontend/`, no frontend code in
`backend/`. Docker Compose runs them as separate services (`api`, `worker`,
`frontend`, plus `postgres` and `redis`).

## Run locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py            # http://localhost:8000  (API docs: /docs)

# Frontend (new terminal)
cd frontend
npm install
npm run dev              # http://localhost:5173
```

Or with Docker Compose (needs Docker; not available in this sandbox):

```bash
docker compose up --build
```

No `GROQ_API_KEY` is needed to run: without it the API runs in
**extractive mode** — answers quote retrieved clauses directly and label
themselves `extractive (no LLM)`. With a key set, generation uses Groq
`openai/gpt-oss-120b`, and every claim is still checked by the faithfulness
gate before display. Never put a real key in the repo; see `.env.example`.

## Demo journey (5 minutes)

1. Register the first account — it becomes **Admin**. (Overview → Admin → Load demo data, or `POST /api/admin/seed`.)
2. **AI Ask:** “What is the current termination penalty if Acme Corp ends the Master Services Agreement for convenience?” → ₹2,50,000, citing Amendment No. 1, Clause 2 — the amendment superseded the original ₹5,00,000 clause.
3. Click any citation — it opens the exact clause in its document context.
4. Ask an unanswerable question (“What is the arbitration venue…?”) → honest abstention, with what was searched.
5. **Conflict Detection:** the Acme termination-penalty candidate (₹2,50,000 vs ₹15,00,000) shown side by side for human confirmation.
6. **Obligation Register:** filter by party/type/due date, export CSV.
7. **Evidence Packs:** download the answer as a PDF with citations, versions and audit reference.
8. Upload a new version of a document — previous answers citing it are flagged **stale** in Answer History.

Seed data is synthetic and labelled **DEMO / SYNTHETIC** everywhere it appears.

## Architecture

```
Upload (PDF/DOCX/TXT)
  → Parse (pypdf / python-docx, parse-quality flags)
  → Clause-aware chunking (heading + doc context always attached)
  → Deterministic extraction (parties, dates, obligations, penalties, notice, references)
  → Knowledge graph (CONTAINS / BINDS / IMPOSES / AMENDS / SUPERSEDES / REFERENCES / CONFLICTS_WITH)
  → Hybrid indexing (BM25 + TF-hash vector + graph)
Question
  → Access-filtered retrieval (collections you cannot access are excluded BEFORE ranking)
  → Merge + re-rank (retrieval trace shows each path's contribution)
  → Generation (Groq LLM, or honest extractive fallback)
  → Faithfulness gate (lexical claim-support check; unsupported claims dropped, else abstain)
  → Answer with citations + audit record
```

PostgreSQL is the source of truth for identity, metadata, clauses and
audit. The vector hash-embeddings and graph edges are derived stores,
rebuildable from PostgreSQL + the original documents. See
[`docs/architecture.md`](docs/architecture.md).

## Evaluation — real numbers, golden-v1, 47 cases (11 Nov 2026)

Run it yourself: `cd backend && python -m evals.run_eval` (writes
`backend/evals/results.json`). Mode: **extractive (no LLM)** — no Groq key
was set for this run. Metrics are RAGAS-style, implemented locally with
the real retrieval + faithfulness code.

| Retrieval mode | Precision@5 | Recall@5 | MRR | Faithfulness | Answer relevancy | Correct abstention |
| --- | --- | --- | --- | --- | --- | --- |
| vector-only | 0.205 | 0.782 | 0.626 | 0.846 | 0.453 | 0.875 |
| vector+BM25 | 0.226 | 0.872 | 0.679 | 0.949 | 0.520 | 0.875 |
| hybrid+rerank | 0.226 | 0.872 | 0.682 | 0.949 | 0.518 | 0.875 |
| hybrid+graph | 0.231 | 0.897 | 0.720 | 0.949 | 0.520 | 0.875 |

Per-category context recall (hybrid+graph): single-clause 1.0,
cross-document 1.0, conflict 1.0, temporal 0.8.

**Honest reading:** BM25 adds the most (recall@5 0.782 → 0.872); the
re-ranker adds a little MRR (0.679 → 0.682); the graph adds the rest
(MRR 0.682 → 0.720, recall@5 0.872 → 0.897) — on this 34-clause demo
corpus the deltas are small, and the graph's real value is temporal
handling (superseded clauses are excluded from retrieval) and the
conflict candidates, not a large recall jump. Precision@5 is low in
absolute terms because each question has only 1–2 expected clauses
against 5 retrieved. Abstention is 7/8: the one failure asks which
court has jurisdiction over the Supply Agreement and is answered from
the MSA's governing-law clause (topically about jurisdiction, wrong
document). The temporal miss asks when the MSA expires — the clause
says “remain in effect until 31 December 2026”, a paraphrase keyword
retrieval cannot catch; sentence-transformer embeddings are the
documented fix.

## LLM mode (Groq) — verified live, 11 Nov 2026

Set `GROQ_API_KEY` (Groq `openai/gpt-oss-120b`) and a strong, unique
`JWT_SECRET` — the backend refuses to start with the demo JWT secret
while a Groq key is set. Without a key it runs in extractive mode
(see above); with a key, `/api/health` reports `mode: "llm"`.

Live Ask verification against the seeded demo corpus (real HTTP calls,
not the eval harness): “What is the current termination penalty if
Acme Corp ends the Master Services Agreement for convenience?” →
**answered, mode `llm`, “The termination penalty is ₹2,50,000 …
[C1]”, citing Amendment No. 1 Clause 2, faithfulness 1.0,
confidence 0.95, 1,107 tokens, $0.000247, 1,182 ms.** An
unanswerable question abstained, and an instruction-injection
question abstained with no leak. The faithfulness gate still
applies in LLM mode: an LLM answer that fails it falls back to
extractive quoting of the same clauses.

LLM-mode ablation on the same 47-case golden set
(`backend/evals/results-llm.json`; the eval scores the real generated
answers when a key is set, extractive answers otherwise):

| Retrieval mode | Precision@5 | Recall@5 | MRR | Faithfulness | Answer relevancy | Correct abstention |
| --- | --- | --- | --- | --- | --- | --- |
| vector-only | 0.205 | 0.782 | 0.626 | 0.590 | 0.441 | 0.875 |
| vector+BM25 | 0.226 | 0.872 | 0.679 | 0.897 | 0.503 | 0.875 |
| hybrid+rerank | 0.226 | 0.872 | 0.682 | 0.897 | 0.518 | 0.875 |
| hybrid+graph | 0.231 | 0.897 | 0.720 | 0.923 | 0.503 | 0.875 |

**Honest reading:** LLM faithfulness (hybrid+graph 0.923) is slightly
*below* extractive quoting (0.949) — generation paraphrases, and the
lexical faithfulness check scores paraphrase lower than direct quotes.
The gap is largest where retrieval is weakest: vector-only collapses
to 0.590 in LLM mode vs 0.846 extractive. In other words, retrieval
quality matters more once a generator is in the loop, which is exactly
what the hybrid+graph pipeline is for.

Implementation note: the Groq client sends a browser User-Agent
(Groq's edge 403s non-browser UAs), verifies TLS against the system
CA store, and reads the egress proxy URL explicitly from
`HTTPS_PROXY`/`HTTP_PROXY` when set (direct connection otherwise).

## Tests

```bash
cd backend && pytest -q    # 11 passed (unit + integration + security)
```

Covered: chunking boundaries, extraction schema, citation/faithfulness
check, upload → Ready → cited answer, unanswerable abstention,
restricted-collection leak test (viewer gets nothing from the admin-only
collection; admin gets the clause), prompt-injection document treated as
data, obligations/conflicts/graph/evidence-pack, duplicate handling +
stale flag, role enforcement.

## What RegLens will not do

- No legal advice; conflict candidates are never verdicts.
- No uncited answers: a claim without a supporting clause is dropped or the answer abstains.
- No confidential documents in the public demo — seed data is synthetic.
- No silent failures: failed ingestion is listed with its error and retryable; the worker re-runs stuck/failed jobs.

## Known limits (v1)

- Embeddings are deterministic TF-hash vectors, not sentence-transformers
  (documented swap-in; the interface is one function). This is why
  paraphrase cases like “expire” vs “remain in effect until” can miss.
- Ingestion runs in-process in the API in v1; the worker polls the DB for
  stuck/failed jobs. Celery + Redis is the scale path, not a v1 dependency.
- The LoRA extractor from the PRD is **not** built in v1 — extraction is
  the deterministic rules-v1 extractor, measured against the golden set.
  Training a LoRA run is a follow-up milestone, not claimed here.
- Email verification and password-reset email are stubs, labelled as such;
  reset tokens are returned in dev only.
- Scanned PDFs are flagged by parse quality, not OCR'd.
- No proctoring-style guarantees: this is a document-intelligence system,
  not a court filing.
