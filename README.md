# LitScope

> **Academic Literature Intelligence & Multi-Study Synthesis Platform**  
> A research assistant built to organize, track, and compare 20-25 reference papers across research projects.

[![Live App](https://img.shields.io/badge/Live_App-litscope.onrender.com-4F46E5?style=flat&logo=render)](https://litscope.onrender.com)
[![API Docs](https://img.shields.io/badge/Swagger_API-Documentation-0EA5E9?style=flat&logo=fastapi)](https://litscope-api.onrender.com/docs)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2F17-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌐 Live Website
* **Web App:** [https://litscope.onrender.com](https://litscope.onrender.com)
* **Backend API Docs:** [https://litscope-api.onrender.com/docs](https://litscope-api.onrender.com/docs)

---

## 1. Why I Built LitScope

As an **MBA Tech student**, I frequently write research and review papers across various subjects.

Going through a bunch of reference papers (typically 20-25 papers per project) quickly becomes tedious:
* Manually reading through dozens of papers and trying to keep track of each paper's problem statement, methodology, and results in scattered notes.
* While giants like **NotebookLM** can handle document Q&A with the right prompts, they are general-purpose tools rather than specialized software for systematic multi-paper reviews.
* LitScope is purpose-built purely for this goal: it automatically extracts 5-dimensional comparison tables, discovers papers directly from arXiv/Scopus, and finds research gaps without prompt engineering.

I wanted to build a tool that would **speed up, keep track of, and simplify** the process of managing information across multiple papers. 

Most importantly, **I wanted a tool that would aid me, not do my work for me**, so that I can do the important thinking and analysis on my own and actually learn, instead of having everything end up in a mess.

---

## 2. What LitScope Does

* **Central Library:** Upload a reference paper once, and use it across any project without duplicate files.
* **Comparison Matrix:** Automatically tracks each paper's objective, methodology, dataset, findings, and limitations in a clean comparative table (exportable to CSV).
* **Clickable Page Citations:** Every answer references the exact paper and page (`[Paper Title, p. X]`). Clicking the citation opens the built-in PDF viewer right to that page.
* **Research Gap Finder:** Scans your curated papers to highlight limitations, unstudied datasets, and conflicting results.
* **Literature Review Drafts:** Generates structured reviews with word-count presets (`200w`, `350w`, `500w`) and exports to Markdown and BibTeX.
* **Paper Discovery:** Search and import papers with verified full-text PDFs directly from **arXiv**, **OpenAlex**, **Crossref**, and **Elsevier Scopus**.

---

## 3. System Architecture

```text
               ┌────────────────────────────────────────────────────────┐
               │              React 18 + TypeScript Client              │
               │  (Workspace, PDF Reader, Matrix, Discovery, Synthesis) │
               └───────────────────────────┬────────────────────────────┘
                                           │  REST API (JWT Auth)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FastAPI Backend Core                                   │
│  ┌───────────────────────┐  ┌───────────────────────────┐  ┌────────────────────────┐  │
│  │ Tiered Rate Limiter   │  │   PyMuPDF Document Parser │  │  FastEmbed Embedder    │  │
│  │ (Protects API Quotas) │  │   (Sentence Chunking)     │  │  (bge-small-en-v1.5)   │  │
│  └───────────────────────┘  └───────────────────────────┘  └────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────────────┬─────────────────┘
                           │                                           │
                           ▼                                           ▼
       ┌───────────────────────────────────────┐           ┌─────────────────────────────┐
       │         PostgreSQL Database           │           │     LLM Reasoning Engine    │
       │  • Vector Index (Cosine Distance)     │           │  • Google Gemini API        │
       │  • Full-Text Search (tsvector)        │           │  • Extractive Synthesizer   │
       │  • Relational Workspaces & Auth       │           │  • Discovery Connectors     │
       └───────────────────────────────────────┘           │    (arXiv, OpenAlex, Scopus)│
                                                           └─────────────────────────────┘
```

---

## 4. Reliability & Safeguards

* **API Rate Limiting:** Prevents server abuse and protects Gemini API key quotas by limiting login attempts (10/min) and AI requests (15/min).
* **Automatic Cloud Database Setup:** Runs database migrations automatically on server boot.
* **Automated Evaluation (`evaluate.py`):** Test scripts verify that citations match real pages and measure search speed.
* **Error Recovery:** Frontend error boundary catches unexpected display issues with a clean reload button.

---

## 5. Tech Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend** | Python 3.12+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy |
| **Database** | PostgreSQL 16/17, `vector` (similarity search), `tsvector` (full-text search) |
| **PDF Processing** | PyMuPDF (`fitz`), NumPy, FastEmbed (`BAAI/bge-small-en-v1.5`) |
| **AI Models** | Google Gemini API (`gemini-3.5-flash-lite`), Rule-based fallbacks |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons |
| **Cloud Hosting** | Render (Web Service + Managed PostgreSQL + Static Site CDN) |

---

## 6. Running Locally

### Prerequisites
* **Python 3.12+**
* **Node.js 18+** & npm
* **PostgreSQL** running locally on port `5432`

### 1. Database Setup
```bash
createdb -U postgres litscope_dev
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
* **API Root:** `http://localhost:8000`
* **Swagger Documentation:** `http://localhost:8000/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
* **Web UI:** `http://localhost:5173`

---

## 7. Author & License
* **Author:** [Akshat Vidyarthi](https://github.com/akshat-vidyarthi) | [akshatvidyarthi@gmail.com](mailto:akshatvidyarthi@gmail.com)
* **License:** [MIT License](LICENSE)
