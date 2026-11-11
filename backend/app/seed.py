"""Synthetic DEMO seed data — clearly labelled SYNTHETIC / DEMO.
Never real confidential documents. Includes: a base agreement + an
amendment that supersedes its termination clause, two contracts with a
conflicting termination penalty for the same party, and one RBI-style
circular. Plus a restricted collection (admin-only) for access-control
demonstration and tests.
"""
from sqlalchemy.orm import Session

from . import models
from .ingestion import ingest_document, sha256_of

MSA = """MASTER SERVICES AGREEMENT
Between Acme Corp and Nimbus Technologies
Effective Date: 1 January 2024. Expiry Date: 31 December 2026.

1. Definitions
"Services" means the software development and support services described in Schedule 1. "Confidential Information" means all non-public information disclosed by either party.

2. Services
Nimbus Technologies shall provide the Services in accordance with the service levels in Schedule 1. Nimbus Technologies shall deliver monthly progress reports to Acme Corp.

3. Term
This Agreement is effective from 1 January 2024 and shall remain in effect until 31 December 2026, unless terminated earlier in accordance with Clause 6.

4. Payment Terms
Acme Corp shall pay Nimbus Technologies a monthly fee of ₹8,00,000 within 30 days of receipt of a valid invoice. Late payment shall attract interest at 1.5% per month.

5. Confidentiality
Each party shall keep the other party's Confidential Information strictly confidential and shall not disclose it to any third party without prior written consent.

6. Termination
Either party may terminate this Agreement by giving 90 days prior written notice to the other party. If Acme Corp terminates this Agreement for convenience before the expiry date, Acme Corp shall pay Nimbus Technologies a termination penalty of ₹5,00,000. The termination penalty of ₹5,00,000 is the sole remedy for early termination for convenience.

7. Limitation of Liability
Neither party shall be liable for indirect or consequential losses. The total aggregate liability of either party shall not exceed ₹50,00,000.

8. Governing Law
This Agreement shall be governed by the laws of India. The courts of Mumbai shall have exclusive jurisdiction.
"""

AMENDMENT = """AMENDMENT NO. 1 TO THE MASTER SERVICES AGREEMENT
Between Acme Corp and Nimbus Technologies
Effective Date: 1 March 2025.

1. Amendment to Clause 6 of Master Services Agreement
This Amendment amends Clause 6 of Master Services Agreement between Acme Corp and Nimbus Technologies. Clause 6 of the Master Services Agreement is hereby superseded in its entirety and replaced by the following new Clause 6.

2. New Termination Clause
Either party may terminate the Agreement by giving 30 days prior written notice to the other party. If Acme Corp terminates this Agreement for convenience before the expiry date, Acme Corp shall pay Nimbus Technologies a termination penalty of ₹2,50,000. The termination penalty of ₹2,50,000 replaces the earlier penalty of ₹5,00,000 and is the sole remedy for early termination for convenience.

3. General
Except as amended by this Amendment, all other terms of the Master Services Agreement remain in full force and effect.
"""

IT_SERVICES = """IT SERVICES AGREEMENT
Between Acme Corp and Nimbus Technologies
Effective Date: 1 June 2024. Expiry Date: 31 May 2027.

1. Scope of Services
Nimbus Technologies shall provide managed IT infrastructure services to Acme Corp, including server monitoring, helpdesk support and patch management.

2. Service Levels
Nimbus Technologies shall maintain 99.5% service availability. Failure to meet service levels entitles Acme Corp to service credits of 5% of the monthly fee.

3. Fees
Acme Corp shall pay Nimbus Technologies ₹6,50,000 per month within 15 days of invoice.

4. Data Protection
Nimbus Technologies shall process personal data only on the documented instructions of Acme Corp and shall implement appropriate technical and organisational measures.

5. Termination
Either party may terminate this Agreement by giving 60 days prior written notice. If Acme Corp terminates this Agreement for convenience, Acme Corp shall pay Nimbus Technologies a termination penalty of ₹15,00,000. The termination penalty of ₹15,00,000 applies notwithstanding any other agreement between the parties.

6. Audit Rights
Acme Corp may audit Nimbus Technologies once per year on 30 days prior written notice.
"""

SUPPLY = """SUPPLY AGREEMENT
Between Delta Foods and Nimbus Technologies
Effective Date: 15 February 2024. Expiry Date: 14 February 2026.

1. Supply of Goods
Delta Foods shall supply packaged food products to Nimbus Technologies as per the purchase orders issued from time to time.

2. Delivery
Delta Foods shall deliver the goods within 7 days of a purchase order. Late delivery beyond 7 days entitles Nimbus Technologies to a discount of 2% per week of delay.

3. Payment
Nimbus Technologies shall pay Delta Foods within 45 days of delivery and receipt of invoice. Late payment shall attract a penalty of 2% per month on the outstanding amount. Nimbus Technologies shall pay a late payment penalty of 2% per month.

4. Quality
Delta Foods shall ensure all goods meet the food safety standards prescribed under applicable law. Delta Foods shall replace defective goods within 3 days of notice.

5. Termination
Either party may terminate this Agreement by giving 45 days prior written notice. On termination, all outstanding payments become due immediately.
"""

CIRCULAR = """RBI CIRCULAR (SYNTHETIC DEMO TEXT — NOT AN OFFICIAL CIRCULAR)
Outsourcing of Information Technology Services by Regulated Entities
Issued: 10 April 2024.

1. Applicability
This circular applies to all regulated entities that outsource information technology services to third-party service providers.

2. Audit Rights
A regulated entity shall retain the right to audit its service provider, including access to systems, data and premises, at least once every year. The service provider shall cooperate fully with such audits.

3. Termination Rights for Critical Vendors
For critical vendors, the regulated entity shall ensure that the outsourcing contract permits termination on 30 days prior written notice in the event of a material breach or regulatory direction.

4. Data Localisation
Customer data shall be stored within India unless otherwise permitted by law. The service provider shall not transfer customer data outside India without prior approval.

5. Incident Reporting
The service provider shall report any material information security incident to the regulated entity within 24 hours of discovery.
"""

BOARD = """BOARD RESOLUTION (SYNTHETIC — RESTRICTED)
Confidential — Board Matters only.

1. Executive Retention
The Board approves a CEO retention bonus of ₹50,00,000 payable on 31 December 2026, subject to continued service. This resolution is confidential and is not to be disclosed outside the Board.
"""

SEED_DOCS = [
    ("Vendor Contracts", "Master Services Agreement — Acme Corp & Nimbus Technologies", "contract", MSA),
    ("Vendor Contracts", "Amendment No. 1 to Master Services Agreement — Acme & Nimbus", "amendment", AMENDMENT),
    ("Vendor Contracts", "IT Services Agreement — Acme Corp & Nimbus Technologies", "contract", IT_SERVICES),
    ("Vendor Contracts", "Supply Agreement — Delta Foods & Nimbus Technologies", "contract", SUPPLY),
    ("Regulatory Circulars", "RBI Circular (Synthetic) — Outsourcing of IT Services", "circular", CIRCULAR),
]


def seed_demo(db: Session, user_id: str) -> dict:
    """Idempotent: skips documents whose title already exists."""
    created = 0
    collections: dict[str, models.Collection] = {}
    for coll_name, title, doc_type, text in SEED_DOCS:
        if coll_name not in collections:
            coll = db.query(models.Collection).filter_by(name=coll_name).first()
            if not coll:
                coll = models.Collection(name=coll_name, description=f"DEMO / SYNTHETIC — {coll_name}",
                                         confidentiality="internal", is_public=True, owner_id=user_id)
                db.add(coll)
                db.commit()
            collections[coll_name] = coll
        if db.query(models.Document).filter_by(title=title).first():
            continue
        doc = models.Document(collection_id=collections[coll_name].id, title=title, doc_type=doc_type,
                              sha256=sha256_of(text.encode()), status="uploaded",
                              parse_quality=1.0, is_demo=True, created_by=user_id)
        db.add(doc)
        db.commit()
        ingest_document(db, doc, text, filename=title + ".txt")
        created += 1
    # Restricted collection (admin-only) for the access-control test/demo.
    restricted = db.query(models.Collection).filter_by(name="Confidential — Board Matters").first()
    if not restricted:
        restricted = models.Collection(name="Confidential — Board Matters",
                                       description="DEMO / SYNTHETIC — restricted to Admin only",
                                       confidentiality="confidential", is_public=False, owner_id=user_id)
        db.add(restricted)
        db.commit()
    if not db.query(models.Document).filter_by(title="Board Resolution — Executive Compensation (Restricted)").first():
        doc = models.Document(collection_id=restricted.id,
                              title="Board Resolution — Executive Compensation (Restricted)",
                              doc_type="policy", sha256=sha256_of(BOARD.encode()),
                              status="uploaded", parse_quality=1.0, is_demo=True, created_by=user_id)
        db.add(doc)
        db.commit()
        ingest_document(db, doc, BOARD, filename="board-resolution.txt")
        created += 1
    return {"created": created,
            "documents": db.query(models.Document).count(),
            "clauses": db.query(models.Clause).count()}
