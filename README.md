# LitScope

> **Research Paper Intelligence Platform**  
> A persistent, local-first platform designed to discover, organize, retrieve, compare, and synthesize academic research papers across multiple research projects over time.

---

## 1. Overview & Core Concept

LitScope transitions academic literature exploration from temporary "chat with a PDF" sessions into an auditable, long-term research tool.

* **Canonical Master Library:** Papers are stored once in a persistent, deduplicated master library using DOI and metadata matching. 
* **Project Separability:** Papers can be curated into separate research projects without duplicating PDFs or re-extracting text. Each project maintains its own research question, scope boundaries, inclusion/exclusion criteria, and analysis history.
* **Conventional RAG Architecture:** Deterministic retrieval (hybrid keyword + semantic search) with inspectable, page-level citations.

---

## 2. Technical Stack

* **Backend:** Python + FastAPI (Asynchronous REST API)
* **Database:** PostgreSQL (SQL-First schema & migrations via dedicated runner)
* **Frontend:** React + TypeScript (Vite + Tailwind CSS)
* **Data Layer:** SQLAlchemy Core with parameterized SQL queries
* **PDF Processing:** PyMuPDF (`fitz`) *(upcoming)*
* **Local Inference:** Ollama *(quantized 3B–7B models)* + SentenceTransformers *(local embeddings)*

---

## 3. Local Setup & Running

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
2. In `backend/`, copy `.env.example` to `.env` and set your PostgreSQL password:
   ```text
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/litscope_dev
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
From the `backend/` directory:
```cmd
pytest -v
```

---

## 4. Development Roadmap

- [x] **Phase 1:** Project Skeleton, PostgreSQL Persistence, and REST API Baseline
- [ ] **Phase 2:** Authentication, Roles & Project Curation
- [ ] **Phase 3:** PDF Ingestion, Text Extraction & Master Library
- [ ] **Phase 4:** Local Embeddings & Conventional RAG Question Answering
- [ ] **Phase 5:** Scholarly Discovery Connectors (OpenAlex & Crossref)
- [ ] **Phase 6:** Structured Evidence Extraction & Cross-Paper Comparison Matrix
- [ ] **Phase 7:** Evidence-Based Candidate Research-Gap Analysis
- [ ] **Phase 8:** Evolving Literature Review & Report Exporting
- [ ] **Phase 9:** Cloud Deployment & Access Management
- [ ] **Phase 10:** Evaluation Suite & System Hardening

---

## License & Author
* **Author:** [akshat-vidyarthi](https://github.com/akshat-vidyarthi)
