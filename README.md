# LitScope

> **Research Paper Intelligence Platform**  
> A persistent, local-first platform designed to discover, organize, retrieve, compare, and synthesize academic research papers across multiple research projects over time.

---

## 1. Overview & Core Concept

LitScope transitions academic literature exploration from temporary "chat with a PDF" sessions into an auditable, long-term research tool.

* **Canonical Master Library:** Papers are stored once in a persistent, deduplicated master library using DOI and normalized title matching. Upload once, curate across multiple studies without duplicating files or re-extracting text.
* **Project Workspaces & Scoping:** Papers can be curated into separate research projects. Each project maintains its own research question, scope boundaries, inclusion/exclusion criteria, collaborator permissions, and analysis history.
* **Granular Role-Based Access:** Projects support collaborative workflows with `OWNER`, `EDITOR`, and `VIEWER` roles, complete with member invitation management and dynamic role switching.
* **In-App PDF Reader:** High-fidelity document reader with page navigation, zoom controls, and thumbnail/text inspection.
* **Deterministic RAG & Evidence Grounding:** Hybrid retrieval (dense vector similarity + PostgreSQL full-text keyword search) coupled with academic synthesis that strictly enforces page-level citations (`[Paper Title, p. X]`).
* **Interactive Citations:** Clicking citation pills in Q&A responses navigates the reader directly to the cited page.

---

## 2. System Architecture

```text
[Academic PDFs] ───────► [Master Library (Canonical Deduplication)]
                                   │
                                   ▼
                        [Project Curated Studies]
                      (OWNER / EDITOR / VIEWER Roles)
                                   │
            ┌──────────────────────┴──────────────────────┐
            ▼                                             ▼
   [PyMuPDF Text Engine]                        [Interactive In-App Reader]
            │                                             ▲
            ▼                                             │ (Click Citation Pill)
[Sentence-Aware Chunker]                                  │
 (Page-Tracked Boundaries)                                │
            │                                             │
            ▼                                             │
 [FastEmbed Vector Model]                                 │
  (BAAI/bge-small-en-v1.5)                                │
            │                                             │
            ▼                                             │
[PostgreSQL Hybrid Index]                                 │
(Vector Cosine + tsvector Full-Text)                      │
            │                                             │
            ▼                                             │
 [Evidence Retrieval Engine]                              │
            │                                             │
            ▼                                             │
[Grounded Academic Synthesis] ────────────────────────────┘
  (Strict [Title, p. X] Citations)
```

---

## 3. Technical Stack

* **Backend:** Python 3.12+, FastAPI (Asynchronous REST API)
* **Database & Search:** PostgreSQL 16/17 with SQL-first migrations, `vector` (cosine distance), and `tsvector` (full-text search)
* **Embeddings & Extraction:** FastEmbed (`BAAI/bge-small-en-v1.5`), PyMuPDF (`fitz`), NumPy
* **Data Access & Security:** SQLAlchemy Core, PyJWT, Bcrypt password hashing
* **Synthesis & LLM Connectors:** Ollama (local inference), with fallback connectors for Gemini, Groq, or OpenAI
* **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons

---

## 4. Local Setup & Running

### Prerequisites
* **Python 3.12+**
* **Node.js 18+** & npm
* **PostgreSQL 16 or 17** running locally on port `5432`

---

### Step 1: Database Setup
1. Create the development database in PostgreSQL:
   ```cmd
   createdb -U postgres litscope_dev
   ```
2. In `backend/`, copy `.env.example` to `.env` and set your PostgreSQL credentials:
   ```text
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/litscope_dev
   JWT_SECRET_KEY=your-secure-random-secret-key-at-least-32-characters
   ```
3. Run the SQL schema migrations:
   ```cmd
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python -m app.core.migrate
   ```

---

### Step 2: Running the Backend
From the `backend/` directory:
```cmd
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```
* **API Root:** `http://localhost:8000/`
* **Interactive OpenAPI Docs:** `http://localhost:8000/docs`

---

### Step 3: Running the Frontend
From the `frontend/` directory:
```cmd
npm install
npm run dev
```
* **Web UI:** `http://localhost:5173/`

---

### Running Automated Tests

* **Backend Unit & API Tests:**
  ```cmd
  cd backend
  .venv\Scripts\pytest.exe -v
  ```

* **Frontend Build Check:**
  ```cmd
  cd frontend
  npm run build
  ```

---

## 5. Development Roadmap

- [x] **Phase 1:** Project Skeleton, PostgreSQL Persistence, and REST API Baseline
- [x] **Phase 2:** Authentication, User Roles & Project Curation Workspaces
- [x] **Phase 3:** PDF Ingestion, Text Extraction & Master Library Reader
- [x] **Phase 4:** Sentence-Aware Chunking, Hybrid Vector Retrieval & Grounded Q&A Synthesis
- [ ] **Phase 5:** Scholarly Discovery Connectors (OpenAlex & Crossref)
- [ ] **Phase 6:** Structured Evidence Extraction & Cross-Paper Comparison Matrix
- [ ] **Phase 7:** Evidence-Based Candidate Research-Gap Analysis
- [ ] **Phase 8:** Evolving Literature Review & Report Exporting
- [ ] **Phase 9:** Cloud Deployment & Access Management
- [ ] **Phase 10:** Evaluation Suite & System Hardening

---

## 6. License & Author
* **Author:** [akshat-vidyarthi](https://github.com/akshat-vidyarthi)
* **License:** MIT
