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
| **Memory** | Vanna 2.0 `DemoAgentMemory` (seeded with 15 Q&A pairs on startup) |

---

## 🗂️ Project Structure

```
AI-NL2SQL/
├── setup_database.py   # Creates schema + inserts 200 patients, 500 appointments, etc.
├── vanna_setup.py      # Vanna 2.0 Agent initialization (LLM + tools + memory)
├── seed_memory.py      # Seeds DemoAgentMemory with 15 known Q&A pairs
├── main.py             # FastAPI application (POST /chat, GET /health)
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

Copy the example file and add your API key:

```bash
cp .env.example .env
```

Edit `.env`:

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

The server will automatically seed agent memory with 15 Q&A pairs on startup. You should see:

```
Seeding memory with 15 Q&A pairs …
✅ Done — 15/15 pairs seeded.
Agent ready.
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
{
  "message": "We have 200 patients. The SQL query \"SELECT COUNT(*) FROM patients;\" was used to retrieve this information. This query counts the number of rows in the patients table, giving us the total number of patients.",
  "sql_query": "",
  "columns": [
    "COUNT(*)"
  ],
  "rows": [
    [
      200
    ]
  ],
  "row_count": 1,
  "chart": null,
  "chart_type": null
}
```

**Error responses:**

| Status | Meaning |
|---|---|
| `400` | SQL validation failed (blocked keyword / non-SELECT) |
| `422` | Agent could not generate SQL — rephrase the question |
| `429` | Rate limit exceeded (20 requests/minute) |
| `500` | Agent or database error |

---

### `GET /health`

Returns server and database status.

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 15,
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

## 🏗️ Architecture Overview

```
User Question (HTTP POST /chat)
        │
        ▼
  FastAPI (main.py)
  ├── Input validation (Pydantic)
  ├── Rate limiting (20 req/min)
  └── Cache check (in-memory)
        │
        ▼
  Vanna 2.0 Agent (vanna_setup.py)
  ├── LLM: Groq llama-3.1-70b-versatile
  ├── Memory: DemoAgentMemory (15 seeded Q&A pairs)
  │     └── Searches for similar past questions (similarity ≥ 0.7)
  ├── Tools:
  │     ├── RunSqlTool        → executes SQL on clinic.db
  │     ├── VisualizeDataTool → generates chart components
  │     ├── SaveQuestionToolArgsTool    → learns from interactions
  │     └── SearchSavedCorrectToolUsesTool → retrieves past patterns
  └── Streams UiComponents back
        │
        ▼
  Component Extraction (main.py)
  ├── DataFrameComponent → rows + columns
  ├── RichTextComponent  → SQL query (if exposed)
  ├── ChartComponent     → Plotly chart data
  └── SimpleTextComponent → human-readable message
        │
        ▼
  SQL Validation
  ├── SELECT-only enforcement
  ├── Blocked keyword check (DROP, DELETE, INSERT …)
  └── System table access prevention
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

## ✨ Bonus Features Implemented

| Feature | Status |
|---|---|
| Chart generation (Plotly) | ✅ Auto-generated for multi-column results |
| Input validation | ✅ Empty, too-long, and non-text questions rejected |
| Query caching | ✅ Repeated questions served from cache instantly |
| Rate limiting | ✅ 20 requests/minute per IP |
| Structured logging | ✅ Timestamped logs for every request step |

---

## 🔧 Troubleshooting

**`Failed to call a function` error from Groq:**
Make sure you are using the correct model in `vanna_setup.py`:
```python
model="llama-3.1-70b-versatile"
```

**`429 RESOURCE_EXHAUSTED` from Gemini:**
Switch to Groq (free, no daily quota). See `vanna_setup.py`.

**Agent returns 422 / cannot generate SQL:**
Try rephrasing the question more explicitly, e.g. "Show me total revenue from invoices table".

**Database not found:**
Run `python setup_database.py` first to generate `clinic.db`.

---

## 📦 Requirements

See `requirements.txt`. Key packages:

```
vanna>=2.0.0
fastapi
uvicorn[standard]
pandas
plotly
python-dotenv
groq
```

---

## 📄 License

MIT — free to use, modify, and distribute.