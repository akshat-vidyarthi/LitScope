# LitScope

> **Research Paper Intelligence Platform**

LitScope is a deployable web application that helps researchers discover, organize, retrieve, compare, and synthesize academic research papers across multiple projects over time.

---

## Architecture Baseline

* **Frontend:** React + TypeScript (Vite)
* **Backend:** Python + FastAPI
* **Database:** PostgreSQL (SQLAlchemy + Alembic)
* **PDF Ingestion:** PyMuPDF (`fitz`)
* **Retrieval & Inference:** Conventional RAG with local embeddings and local model runtime (Ollama)
* **Storage:** Local filesystem abstraction (`data/storage/`)

For detailed technical decisions and rationale, see [ADR-001: Architecture Baseline](docs/decisions/ADR-001-architecture-baseline.md).

---

## Roadmap Phases

* **Phase 0:** Requirements & Architecture Baseline
* **Phase 1:** Project Skeleton & Persistence
* **Phase 2:** Authentication, Roles & Project Curation
* **Phase 3:** PDF Ingestion & Master Library
* **Phase 4:** Local Embeddings & Conventional RAG
* **Phase 5:** Scholarly Discovery
* **Phase 6:** Structured Evidence & Matrix Comparison
* **Phase 7:** Candidate Research-Gap Analysis
* **Phase 8:** Evolving Literature Review & Exports
* **Phase 9:** Cloud Deployment & Access
* **Phase 10:** Evaluation & Hardening
