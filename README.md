# 🏥 Clinic NL2SQL — AI-Powered Natural Language to SQL System

An AI agent that converts plain English questions into SQL queries and returns structured results from a clinic management database. Built with **Vanna 2.0**, **Groq (LLaMA)**, **FastAPI**, and **SQLite**.

---

## 📋 Project Overview

| Item | Detail |
|---|---|
| **LLM Provider** | Groq — `llama-3.1-70b-versatile` (free tier) |
| **Framework** | Vanna 2.0 Agent architecture |
| **Database** | SQLite (`clinic.db`) |
| **API** | FastAPI with POST `/chat` and GET `/health` |
| **Memory** | Vanna 2.0 `DemoAgentMemory` (seeded with 25 Q&A pairs on startup) |

---

## 🗂️ Project Structure

```
AI-NL2SQL/
├── setup_database.py   # Creates schema + inserts 200 patients, 500 appointments, etc.
├── vanna_setup.py      # Vanna 2.0 Agent initialization (LLM + tools + memory)
├── seed_memory.py      # Seeds DemoAgentMemory with 25 known Q&A pairs on startup
├── main.py             # FastAPI application (POST /chat, GET /health)
├── test_chart.html     # Browser-based chart viewer for testing API responses
├── clinic.db           # Generated SQLite database
├── requirements.txt    # All dependencies
├── .env                # API keys (not committed)
├── .env.example        # Template for environment variables
├── README.md           # This file
└── RESULTS.md          # Test results for 20 questions
```

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/your-username/AI-NL2SQL.git
cd AI-NL2SQL
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your actual Groq API key:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

Get a free Groq API key at: https://console.groq.com

### 5. Create the database

```bash
python setup_database.py
```

Expected output:
```
Created 200 patients, 15 doctors, 500 appointments, 274 treatments, 300 invoices.
```

### 6. Start the API server

```bash
uvicorn main:app --reload --port 8000
```

The server automatically seeds agent memory with 25 Q&A pairs on startup. You should see:

```
Seeding memory with 25 Q&A pairs …
✅ Done — 25/25 pairs seeded.
Agent ready.
Pre-flight lookup armed with 25 Q&A pairs.
```

> **Note:** `seed_memory.py` does NOT need to be run separately. Memory is seeded automatically on every server startup inside `main.py`.

---

## 🔌 API Documentation

### `POST /chat`

Converts a natural language question into SQL, executes it, and returns structured results.

**Request:**
```json
{
  "question": "How many patients do we have?"
}
```

**Response:**
```json
{
  "message": "Found 1 result(s).",
  "sql_query": "SELECT COUNT(*) AS total_patients FROM patients",
  "columns": ["total_patients"],
  "rows": [[200]],
  "row_count": 1,
  "chart": null,
  "chart_type": null
}
```

For multi-column results the `chart` field contains a Plotly JSON object and `chart_type` is `"bar"` or `"line"`. See [Viewing Charts](#-viewing-charts) below.

**Error responses:**

| Status | Meaning |
|---|---|
| `400` | SQL validation failed (blocked keyword / non-SELECT) |
| `422` | Agent could not generate SQL — rephrase the question |
| `429` | Rate limit exceeded (20 requests/minute) |
| `500` | Agent or database error |
| `502` | Groq tool-call failed after all retries — rephrase the question |
| `503` | Cannot reach Groq API — check internet connection |
| `504` | Groq API request timed out — try again |

---

### `GET /health`

Returns server and database status.

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 25,
  "timestamp": "2026-04-13T00:43:34.506Z"
}
```

---

## 🧪 Example Requests

```bash
# Health check
curl http://localhost:8000/health

# Count patients
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'

# Revenue by doctor
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Show revenue by doctor"}'

# Top patients by spending
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Top 5 patients by spending"}'
```

---

## 📊 Viewing Charts

The `chart` field in responses is a **Plotly JSON object** — not an image. Three ways to render it:

**1. Browser test page (recommended)** — open `test_chart.html` in your browser while the server is running. Provides a full UI with question input, live Plotly chart, data table, and SQL display.

**2. Python script:**
```python
import requests, plotly.graph_objects as go

data = requests.post("http://127.0.0.1:8000/chat",
                     json={"question": "Show revenue by doctor"}).json()
if data.get("chart"):
    go.Figure(data["chart"]).show()   # opens in browser
```

**3. Plotly Chart Studio** — paste the `chart` JSON at https://chart-studio.plotly.com/create

---

## 🏗️ Architecture Overview

```
User Question (HTTP POST /chat)
        │
        ▼
  FastAPI (main.py)
  ├── Input validation (Pydantic, max 500 chars)
  ├── Rate limiting (20 req/min per IP)
  └── Cache check (in-memory, exact question match)
        │
        ▼
  Pre-flight SQL Lookup
  ├── Compares question against 25 seeded Q&A pairs (difflib similarity)
  ├── Score ≥ 0.70 → run SQL directly, skip agent entirely ──→ JSON Response ✅
  └── Score < 0.70 → forward to agent
        │
        ▼
  Vanna 2.0 Agent (vanna_setup.py)
  ├── LLM: Groq llama-3.1-70b-versatile
  ├── Memory: DemoAgentMemory (25 seeded Q&A pairs)
  │     └── Searches for similar past questions (similarity ≥ 0.7)
  ├── Retry: up to 3 attempts on Groq tool-call failures (1.5s delay)
  ├── Tools:
  │     ├── RunSqlTool        → executes SQL on clinic.db
  │     ├── VisualizeDataTool → generates chart components
  │     ├── SaveQuestionToolArgsTool    → learns from interactions
  │     └── SearchSavedCorrectToolUsesTool → retrieves past patterns
  └── Streams UiComponents back
        │
        ▼
  Component Extraction (main.py)
  ├── DataFrameComponent  → rows + columns
  ├── RichTextComponent   → SQL (code block or embedded in prose)
  ├── ChartComponent      → Plotly chart data
  └── SimpleTextComponent → human-readable message
        │
        ▼
  SQL Validation + Execution
  ├── SELECT-only enforcement
  ├── Blocked keyword check (DROP, DELETE, INSERT …)
  ├── System table access prevention
  ├── Numpy type sanitization (np.int64 → int, etc.)
  └── Auto chart generation (bar / line based on question keywords)
        │
        ▼
  JSON Response → client
```

---

## 🛡️ Security Features

- **SELECT-only queries** — INSERT, UPDATE, DELETE, DROP, ALTER etc. are rejected before execution
- **Blocked keywords** — EXEC, xp_, sp_, GRANT, REVOKE, SHUTDOWN are rejected
- **System table protection** — queries on `sqlite_master`, `sqlite_sequence` are blocked
- **Input length limit** — questions longer than 500 characters are rejected
- **Rate limiting** — 20 requests per minute per IP address
- **No API key hardcoding** — all secrets loaded from `.env`

---

## ✨ Features Implemented

| Feature | Status |
|---|---|
| Natural language to SQL | ✅ Via Vanna 2.0 + Groq LLaMA |
| Chart generation (Plotly) | ✅ Auto-generated bar/line for multi-column results |
| Input validation | ✅ Empty, too-long, and non-text questions rejected |
| Query caching | ✅ Repeated questions served from cache instantly |
| Rate limiting | ✅ 20 requests/minute per IP |
| Structured logging | ✅ Timestamped logs for every request step |
| Pre-flight SQL lookup | ✅ Known questions bypass agent entirely (difflib, threshold 0.70) |
| Agent retry logic | ✅ Up to 3 retries on Groq tool-call failures with 1.5s backoff |
| Embedded SQL extraction | ✅ SELECT statements extracted from agent prose responses |
| Numpy JSON sanitization | ✅ np.int64/float64 converted before serialization |
| Browser chart viewer | ✅ `test_chart.html` — full UI with chart, table, and SQL |

---

## 🔧 Troubleshooting

**`Failed to call a function` error from Groq:**
This is an intermittent Groq tool-calling reliability issue. The server automatically retries up to 3 times. If all retries fail, a `502` is returned. Try rephrasing the question or wait a few seconds and retry.

**`ConnectTimeout` / `504` response:**
The Groq API is unreachable. Check your internet connection.

**`422` — Agent cannot generate SQL:**
The question is too ambiguous for the agent. Try rephrasing more explicitly, e.g. `"Show total revenue from the invoices table grouped by doctor name"`.

**`TypeError: Object of type ndarray is not JSON serializable`:**
Ensure you are running the latest `main.py` which includes `sanitize_rows()` and uses `fig.to_json()` in `auto_chart()`.

**Database not found:**
Run `python setup_database.py` first to generate `clinic.db`.

**Charts not showing in Swagger UI:**
Swagger UI does not render Plotly charts. Open `test_chart.html` in your browser instead.

---

## 📦 Requirements

See `requirements.txt`. Key packages:

```
vanna>=2.0.0
fastapi
uvicorn[standard]
pandas
numpy
plotly
python-dotenv
groq
openai
```

---