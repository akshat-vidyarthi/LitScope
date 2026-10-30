# ADR-001: Architecture Baseline & Technology Stack

- **Status:** Accepted
- **Date:** 2026-10-30
- **Author:** akshat-vidyarthi & AntiGravity

---

## 1. Context & Problem Statement

LitScope is a deployable web application designed to help researchers discover, organize, retrieve, compare, and synthesize academic research papers across multiple projects over time. 

The software must avoid being an ephemeral "chat with a folder of PDFs." It requires:
1. A persistent canonical master library decoupled from project-specific curated collections.
2. Grounded, inspectable conventional RAG with page-level citations.
3. Structured evidence extraction and cross-paper matrix comparison.
4. Cautious, evidence-grounded candidate research-gap analysis with counterexample searching.
5. High explainability and local-first execution on the developer's hardware.

### Hardware Baseline
- **Machine:** Dell G7 7588
- **OS:** Windows 11 Home Single Language
- **GPU:** NVIDIA GeForce GTX 1060 Max-Q (6,144 MiB / 6 GB VRAM)
- **RAM:** ~16 GB System Memory
- **Storage:** Free disk headroom > 600 GB

---

## 2. Architectural Decisions

### 2.1 RAG Architecture: Conventional RAG Only
- **Decision:** Use strictly Conventional Retrieval-Augmented Generation (Metadata Filtering $\rightarrow$ Hybrid Keyword + Semantic Retrieval $\rightarrow$ Context Formatting with stable chunk IDs $\rightarrow$ Grounded Answer Generation with Citation Validation).
- **Rule:** Do **not** use STAIR or STAIR-related approaches. Avoid uninspected autonomous agents.

### 2.2 Backend Framework: Python + FastAPI
- **Decision:** Build the backend REST API in Python using FastAPI, Pydantic, and Uvicorn.
- **Rationale:**
  - Native compatibility with Python ML, scientific, and document processing libraries (PyMuPDF, SentenceTransformers, PyTorch).
  - High performance asynchronous I/O and strict type validation with Pydantic.
  - Automatic OpenAPI / Swagger interactive documentation for easy testing and review.

### 2.3 Database & Migrations: PostgreSQL + SQLAlchemy + Alembic
- **Decision:** Use PostgreSQL as the relational database, using SQLAlchemy (2.0 style) for ORM/queries and Alembic for schema migrations.
- **Rationale:**
  - ACID compliance, robust relational capabilities for complex multi-project paper relationships, versioning, and run history.
  - Transparent SQL migrations via Alembic allow the developer to review and understand every schema alteration before execution.
  - Option to integrate `pgvector` for vector similarity search directly within PostgreSQL, or start with an inspectable local vector store with a clear migration path.

### 2.4 Frontend: React (Vite) + TypeScript + Tailwind CSS
- **Decision:** Build a responsive, modular Single-Page Application (SPA) using React, Vite, TypeScript, and Tailwind CSS.
- **Rationale:**
  - Clear separation of concerns: the frontend acts solely as a presentation and interaction layer via REST API calls.
  - No direct frontend connection to model runtimes or database credentials.
  - Component-driven UI ideal for evidence matrices, PDF split-screen citation inspection, and project curation.

### 2.5 PDF Ingestion & Extraction: PyMuPDF (`fitz`)
- **Decision:** Use PyMuPDF for text extraction and layout-aware page provenance.
- **Rationale:**
  - Extremely fast C-backed execution without external cloud API dependencies.
  - Preserves exact page numbers, coordinates/bounding boxes, and offsets essential for auditable citations.
  - Scanned/image-only PDFs will be flagged for optional OCR in later phases.

### 2.6 Local Model Inference: Ollama (Quantized 3B–7B Models)
- **Decision:** Plan for local inference via Ollama or a compatible local runner, keeping the LLM client decoupled behind an abstract provider interface.
- **Hardware Alignment:** Due to the 6 GB VRAM constraint on the GTX 1060 Max-Q, the LLM will be restricted to efficient 4-bit/5-bit quantized models (e.g., Qwen2.5-3B/7B-Instruct or Phi-3.5-mini) to guarantee sub-second token generation without swapping into system RAM.
- **Embeddings:** Local SentenceTransformers model (e.g., `all-MiniLM-L6-v2` or `bge-small-en-v1.5`), which uses minimal VRAM (< 500 MB) and runs fast on CPU/GPU.

### 2.7 Storage Abstraction: Dedicated Local Storage
- **Decision:** PDFs, extracted text caches, and generated exports will be stored in a structured local directory (`data/storage/`), with metadata, paths, and SHA-256 checksums recorded in PostgreSQL.
- **Rationale:** Prevents database bloat from storing large binaries in table rows, while enabling trivial migration to cloud object storage (S3/GCS) in production.

### 2.8 Scholarly Discovery: OpenAlex & Crossref
- **Decision:** Implement external academic discovery using OpenAlex and Crossref open REST APIs.
- **Rationale:** Free, open access, well-documented APIs with rich metadata, DOI resolution, and open-access PDF status checks without requiring paywall bypasses.

---

## 3. Consequences & Non-Goals

- **PostgreSQL is required locally:** Setup and verification will be documented and completed before Phase 1.
- **No Cloud Lock-in:** The entire system will run offline/locally with zero mandatory API costs, retaining a clean path to cloud deployment in Phase 9.
- **Human Explainability:** No code or database migrations will be applied without the developer being able to explain how they operate.
