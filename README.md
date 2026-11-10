# ResolveAI

Support console for a fictional product, Fieldnote. Incoming tickets are classified into a queue, scored for priority and sentiment, matched to similar resolved cases, and given a reply draft an agent has to approve.

The corpus is synthetic. Scores on the Models page are holdout macro-F1 for these pipelines, not a production benchmark.

## What it does

- Ticket classification with TF-IDF and logistic regression
- Priority prediction with TF-IDF and XGBoost
- Sentiment analysis with a second TF-IDF and logistic regression pipeline
- Routing across Billing, Technical Support, Account Access, Orders & Shipping, Returns & Refunds, Product Inquiry, and Trust & Safety
- Semantic search with Sentence Transformers (`all-MiniLM-L6-v2`) when that package is installed, otherwise a 128-dimension TF-IDF + TruncatedSVD embedding
- Reply drafts from department policy and similar tickets, or from an OpenAI-compatible chat API when `OPENAI_API_KEY` is set
- Human review: accept the routing or correct it, then edit and send the draft
- A projected handling-time reduction, recorded when an agent sends the suggested reply (about 75% of that ticket's manual baseline; target 25%)

## Run it

PostgreSQL is used when it is reachable. Docker is the straightforward way to get it:

```powershell
docker compose up -d
```

Without Docker, the API falls back to SQLite at `data/resolve.db`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-embeddings.txt
.\.venv\Scripts\python.exe -m backend.scripts.bootstrap
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

`requirements-embeddings.txt` is optional. It installs Sentence Transformers and downloads `all-MiniLM-L6-v2` the first time the index is built. Install it before `bootstrap` if you want that embedder. If it is missing, search still runs on the SVD embedding and the Models page says so.

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

Bootstrap trains on 5,600 tickets, checks that each pipeline clears 85% holdout macro-F1, and reloads the queue. Running it again wipes the ResolveAI tables in the configured database.

To point at Postgres explicitly:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://resolve:resolve@localhost:5432/resolveai"
.\.venv\Scripts\python.exe -m backend.scripts.bootstrap
```

Copy `.env.example` to `.env` for the same settings, including an optional LLM key.
