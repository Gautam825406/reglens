"""Golden-set evaluation (PRD §13): RAGAS-style scoring implemented locally
with the real retrieval + faithfulness code — no invented scores.

Four-way ablation on the same golden set:
  vector-only | vector+BM25 | hybrid+rerank | hybrid+graph
Metrics: context precision, context recall, faithfulness, answer relevancy,
correct abstention. Run: python -m evals.run_eval  (from backend/)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db  # noqa: E402
from app import models  # noqa: E402
from app.faithfulness import check_answer  # noqa: E402
from app.generation import extractive_answer  # noqa: E402
from app.retrieval import ABSTAIN_COVERAGE_THRESHOLD, ABSTAIN_TOP_SCORE_THRESHOLD, retrieve  # noqa: E402
from app.seed import seed_demo  # noqa: E402

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")

MODES = {
    "vector-only": ("vector",),
    "vector+bm25": ("vector", "bm25"),
    "hybrid+rerank": ("vector", "bm25", "rerank"),
    "hybrid+graph": ("vector", "bm25", "graph", "rerank"),
}


def resolve_expected(db, case) -> set[str]:
    ids = set()
    for exp in case.get("expected", []):
        # Title match is startswith: "Master Services Agreement" must not
        # also match "Amendment No. 1 to Master Services Agreement".
        docs = [d for d in db.query(models.Document).all()
                if d.title.startswith(exp["doc_title_contains"])]
        for d in docs:
            for c in db.query(models.Clause).filter_by(document_id=d.id, clause_no=exp["clause_no"]).all():
                ids.add(c.id)
    return ids


def run_all(db=None, user=None) -> dict:
    own_db = db is None
    if own_db:
        init_db()
        db = SessionLocal()
    admin = user or db.query(models.User).filter_by(role="admin").first()
    if admin is None:
        from app.security import hash_password
        admin = models.User(name="Eval Admin", email="eval-admin@reglens.local",
                            password_hash=hash_password("eval-admin-password"), role="admin",
                            email_verified=True)
        db.add(admin)
        db.commit()
    if db.query(models.Document).count() == 0:
        seed_demo(db, admin.id)
    with open(GOLDEN_PATH) as f:
        golden = json.load(f)
    cases = golden["cases"]
    per_mode: dict[str, dict] = {}
    for mode_name, modes in MODES.items():
        precisions, recalls, faiths, relevs, abst_correct, mrrs, n = [], [], [], [], [], [], 0
        for case in cases:
            expected = resolve_expected(db, case)
            retrieved = retrieve(db, admin, case["question"], top_k=5, modes=modes)
            got = {r["clause_id"] for r in retrieved}
            top_score = retrieved[0]["score"] if retrieved else 0.0
            best_coverage = max((r.get("coverage", 0) for r in retrieved[:3]), default=0.0)
            abstained = top_score < ABSTAIN_TOP_SCORE_THRESHOLD or best_coverage < ABSTAIN_COVERAGE_THRESHOLD
            if case.get("abstain"):
                abst_correct.append(1.0 if abstained else 0.0)
                continue
            n += 1
            if expected:
                precisions.append(len(got & expected) / max(len(got), 1))
                recalls.append(len(got & expected) / len(expected))
                ranks = [i + 1 for i, r in enumerate(retrieved) if r["clause_id"] in expected]
                mrrs.append(1.0 / min(ranks) if ranks else 0.0)
            else:
                precisions.append(0.0)
                recalls.append(0.0)
                mrrs.append(0.0)
            if retrieved and not abstained:
                gen = extractive_answer(case["question"], retrieved)
                check = check_answer(gen["claims"], {r["clause_id"]: r["text"] for r in retrieved})
                faiths.append(check["faithfulness"])
                q_terms = set(case["question"].lower().split())
                a_terms = set(gen["text"].lower().split())
                relevs.append(len(q_terms & a_terms) / max(len(q_terms), 1))
            else:
                faiths.append(0.0)
                relevs.append(0.0)
        def avg(xs):
            return round(sum(xs) / len(xs), 3) if xs else 0.0
        per_mode[mode_name] = {
            "n_answerable": n, "n_abstention": len(abst_correct),
            "context_precision@5": avg(precisions), "context_recall@5": avg(recalls),
            "mrr": avg(mrrs),
            "faithfulness": avg(faiths), "answer_relevancy": avg(relevs),
            "correct_abstention_rate": avg(abst_correct),
        }
    # Per-category context recall for the full hybrid+graph pipeline.
    cat_recall: dict[str, list[float]] = {}
    for case in cases:
        if case.get("abstain"):
            continue
        expected = resolve_expected(db, case)
        if not expected:
            continue
        retrieved = retrieve(db, admin, case["question"], top_k=8, modes=("vector", "bm25", "graph", "rerank"))
        got = {r["clause_id"] for r in retrieved}
        cat_recall.setdefault(case["category"], []).append(len(got & expected) / len(expected))
    per_category = {k: round(sum(v) / len(v), 3) for k, v in sorted(cat_recall.items())}
    result = {"dataset": golden["version"], "n_cases": len(cases),
              "answerable": sum(1 for c in cases if not c.get("abstain")),
              "unanswerable": sum(1 for c in cases if c.get("abstain")),
              "mode": "extractive (no LLM)" if not os.environ.get("GROQ_API_KEY") else "llm",
              "ablation": per_mode,
              "per_category_context_recall_hybrid_graph": per_category,
              "note": "Scores computed by the real retrieval + faithfulness code on the golden set. "
                      "hybrid+rerank adds the overlap re-rank bonus; "
                      "graph adds AMENDS/SUPERSEDES/REFERENCES traversal."}
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    if own_db:
        db.close()
    return result


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2))
