# FinDocGPT

FastAPI-based RAG (Retrieval-Augmented Generation) service for **financial document Q&A** with **page-level evidence**. Built around the FinanceBench open dataset and designed to extend toward **sentiment, anomaly detection, forecasting, and strategy**.

> **Project status:** MVP focused on Stage-1 (document Q&A + evidence). Vector/BM25 retrieval, short-answer extraction, sentiment, and forecasting are on the roadmap.

---

## Features

- **Ask questions** over 10-K/10-Q and earnings PDFs; get highlighted answers and **traceable citations**  
  → `sources` are normalized as  
  `{"source":"<pdf path>", "chunk_id": <int>, "page": <int>}`
- **Dependency-light RAG core**
  - PDF parsing via `pdfplumber`
  - Page-aware chunking with overlap
  - Persistent JSONL index (`data/index.jsonl`) for fast restarts
  - Simple keyword scoring (baseline) → Top-K context
- **Debuggability**
  - `GET /debug/env` shows working dir, docs folder, index presence
  - `GET /debug/corpus` warms the corpus and returns size/sample
- **Evaluation harness**
  - `eval/qa_metrics.py` computes EM, F1, Evidence Recall@k, and latency on FinanceBench QA

---

## Repo Structure

```
fin-doc-gpt/
├─ app/
│  ├─ main.py                # FastAPI entrypoint (/ask, /health, /debug/*)
│  ├─ routers/
│  │  └─ ask.py              # POST /ask: request model + response normalization
│  └─ services/
│     └─ rag.py              # PDF→chunk→index(JSONL)→keyword retrieval→highlight
├─ data/
│  ├─ financebench/pdfs/     # FinanceBench PDFs (not tracked)
│  └─ index.jsonl            # Persistent text index (auto-generated; gitignored)
├─ eval/
│  └─ qa_metrics.py          # EM/F1/R@k/latency evaluation
├─ ingest/                   # (reserved) future ingestion utilities
├─ requirements.txt
└─ README.md
```

---

## Quickstart

### 1) Environment

- Python **3.11** recommended
- Create venv and install deps:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Data layout

Put FinanceBench PDFs here:
```
data/financebench/pdfs/
```

Symlink them as the working docs directory:
```bash
rm -rf data/docs
ln -s data/financebench/pdfs data/docs
```

> On first query, the RAG core builds `data/index.jsonl` (persistent). Subsequent runs reuse it.

### 3) Run the API

```bash
uvicorn app.main:app --reload --port 8010
```

Health check:
```bash
curl http://127.0.0.1:8010/health
# {"status":"ok"}
```

---

## API

### `POST /ask/`

**Request**
```json
{
  "question": "What is the FY2018 capital expenditure amount (in USD millions) for 3M?",
  "top_k": 5
}
```

**Response (shape)**
```json
{
  "answer": "…with **bold** highlights of matched terms…",
  "sources": [
    { "source": "data/docs/3M_2018_10K.pdf", "chunk_id": 12, "page": 60 }
  ],
  "meta": { "ticker": null, "top_k": 5 }
}
```

### `GET /health`
Returns `{"status":"ok"}`.

### `GET /debug/env`
Shows runtime working dir, docs folder status, and whether indices exist.

### `GET /debug/corpus`
Warms the RAG corpus and returns:
```json
{ "corpus_size": 1234, "sample_sources": [ { "source": "...", "chunk_id": 0, "page": 1 } ] }
```

---

## Evaluation

Run a small evaluation over FinanceBench open QA:

```bash
python -u eval/qa_metrics.py --n 20 --k 3 --host http://127.0.0.1:8010 --progress
```

**Metrics**
- **EM** (Exact Match)
- **F1** (token-level)
- **Evidence Recall@k** (whether gold evidence is within top-k)
- **Latency** (P50/P95)

---

## Configuration

Environment variables (optional):

- `RAG_CHUNK_SIZE` — default `600`
- `RAG_OVERLAP` — default `80`
- `RAG_USE_VECTOR` — reserved (future: vector search toggle)

---

## Roadmap

- **Answer quality:** short-answer extraction (`short_answer`) with numeric normalization (e.g., `$1,577.00`) to boost EM/F1.
- **Retrieval:** add BM25 and FAISS / `sentence-transformers` with **vector-first, keyword/BM25 fallback**.
- **Sentiment:** baseline VADER → FinBERT for finance-tuned sentiment on calls/PRs/news.
- **Anomalies:** YoY/QoQ **z-score** alerts on extracted metrics.
- **Forecasting:** price/earnings predictions via Yahoo/Alpha Vantage; uncertainty bands.
- **Strategy:** combine fundamentals + sentiment + forecasts into **Buy/Hold/Sell** with cited rationale.
- **UI:** lightweight web front-end with charts and evidence viewer.

---

## Troubleshooting

- **`/debug/env` returns `docs_exists: false`**  
  Ensure the symlink exists:
  ```bash
  rm -rf data/docs
  ln -s data/financebench/pdfs data/docs
  ```
  Delete stale index to rebuild:
  ```bash
  rm -f data/index.jsonl
  ```

- **Large files / datasets in git**  
  Add a `.gitignore` entry for `data/financebench/pdfs/` and `data/index.*`.

---

## License

MIT (or your preferred license). Include dataset license constraints for FinanceBench materials.

