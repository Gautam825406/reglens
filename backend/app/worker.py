"""RegLens worker (v1).

Polls the database for ingestion jobs that need attention and runs them
with the same ingest function the API uses:
- documents stuck in processing/extracting/indexing (e.g. the API died
  mid-ingest) are re-run from their stored version text;
- failed documents are retried once, then left failed with their error
  visible in the Admin ingestion-health view (never silently dropped).

This is deliberately DB-polling in v1. The scale path is Celery + Redis
(the redis service in docker-compose.yml is the broker for that migration);
the worker's interface — ingest_document(db, doc, text) — does not change.
"""
import logging
import time

from app.database import SessionLocal, init_db
from app import models
from app.ingestion import ingest_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reglens-worker")

STUCK = ("processing", "extracting", "indexing")


def run_once() -> dict:
    init_db()
    db = SessionLocal()
    try:
        stuck = db.query(models.Document).filter(models.Document.status.in_(list(STUCK))).all()
        failed = db.query(models.Document).filter_by(status="failed").all()
        retried = 0
        for doc in stuck + failed:
            version = db.query(models.DocVersion).filter_by(document_id=doc.id).order_by(
                models.DocVersion.version_no.desc()).first()
            if not version or not version.text:
                continue
            try:
                doc.error = ""
                ingest_document(db, doc, version.text, filename=version.storage_key)
                retried += 1
                logger.info("worker: re-ingested %s (%s)", doc.id, doc.title)
            except Exception as exc:
                doc.status = "failed"
                doc.error = str(exc)[:500]
                db.commit()
                logger.warning("worker: %s still failing: %s", doc.id, exc)
        return {"stuck": len(stuck), "failed_seen": len(failed), "retried_ok": retried}
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("reglens worker started (poll every 30s)")
    while True:
        try:
            result = run_once()
            if result["stuck"] or result["failed_seen"]:
                logger.info("worker cycle: %s", result)
        except Exception as exc:
            logger.exception("worker cycle failed: %s", exc)
        time.sleep(30)
