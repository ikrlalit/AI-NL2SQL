# main.py
import re
import time
import asyncio
import sqlite3
import logging
from difflib import SequenceMatcher
from datetime import datetime, timezone

import numpy as np
import openai
import pandas as pd
import plotly.express as px
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from vanna.core.user import RequestContext, User
from vanna.components.rich import (
    ComponentType,
    DataFrameComponent,
    ChartComponent,
    RichTextComponent,
    CardComponent,
)

from vanna_setup import create_agent, build_memory
from seed_memory import seed_async, QA_PAIRS

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
log = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Clinic NL2SQL API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── Global state ──────────────────────────────────────────────────────────────
memory = None
agent  = None
DEFAULT_USER = User(id="clinic_user", email="user@clinic.local",
                    group_memberships=["user"])

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global memory, agent
    log.info("Seeding memory with %d Q&A pairs …", len(QA_PAIRS))
    memory = await seed_async()
    agent  = create_agent(memory=memory)
    log.info("Agent ready.")
    log.info("Pre-flight lookup armed with %d Q&A pairs.", len(QA_PAIRS))

# ── Rate limiting ─────────────────────────────────────────────────────────────
_rate_store: dict[str, list[float]] = {}
RATE_LIMIT, RATE_WINDOW = 20, 60

def check_rate_limit(ip: str):
    now  = time.time()
    hits = [t for t in _rate_store.get(ip, []) if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    _rate_store[ip] = hits + [now]

# ── SQL Validation ────────────────────────────────────────────────────────────
BLOCKED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE|GRANT|REVOKE"
    r"|SHUTDOWN|TRUNCATE|CREATE|ATTACH|DETACH|xp_|sp_)\b",
    re.IGNORECASE,
)
SYS_TABLES = re.compile(
    r"\b(sqlite_master|sqlite_sequence|information_schema)\b",
    re.IGNORECASE,
)

def validate_sql(sql: str) -> tuple[bool, str]:
    if not sql.strip().upper().startswith("SELECT"):
        return False, "Only SELECT queries are permitted."
    if m := BLOCKED.search(sql):
        return False, f"Blocked keyword: '{m.group()}'"
    if SYS_TABLES.search(sql):
        return False, "Access to system tables is not allowed."
    return True, ""

# ── Numpy / JSON sanitiser ────────────────────────────────────────────────────
def _to_python(v):
    """Convert numpy scalar types to JSON-serializable Python natives."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v

def sanitize_rows(rows: list) -> list:
    """Apply _to_python to every cell in a list-of-lists."""
    return [[_to_python(v) for v in row] for row in rows]

# ── SQL extractor — pulls SELECT out of embedded agent text ──────────────────
_EMBEDDED_SQL = re.compile(r'(SELECT\b[\s\S]+?)(?=\n\n|\Z)', re.IGNORECASE)

def extract_sql(text: str) -> str | None:
    """Extract the first SELECT statement found anywhere in a text block."""
    if not text:
        return None
    if text.strip().upper().startswith("SELECT"):
        return text.strip()
    m = _EMBEDDED_SQL.search(text)
    if m:
        candidate = m.group(1).strip()
        if candidate.upper().startswith("SELECT"):
            return candidate
    return None

# ── Message sanitiser ─────────────────────────────────────────────────────────
_NOISE = re.compile(
    r"(Results saved to file:[^\n]*"
    r"|query_results_[a-f0-9]+\.csv[^\n]*"
    r"|\*{0,2}IMPORTANT:[^\n]*"
    r"|FOR VISUALIZE_DATA[^\n]*)",
    re.IGNORECASE,
)

def clean_message(text: str) -> str:
    """Strip internal agent tool-orchestration lines from the message."""
    if not text:
        return text
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if _NOISE.search(stripped):
            continue
        if re.fullmatch(r"[\w()*,\s]+", stripped) and "\t" not in stripped and len(stripped) < 60:
            continue
        if stripped:
            lines.append(stripped)
    return " ".join(lines).strip()

# ── Chart helper ──────────────────────────────────────────────────────────────

def auto_chart(df: pd.DataFrame, question: str) -> tuple[dict | None, str | None]:
    num = df.select_dtypes(include="number").columns.tolist()
    cat = [c for c in df.columns if c not in num]
    if not num or not (cat or len(df.columns) > 1):
        return None, None
    x = cat[0] if cat else df.columns[0]
    y = num[0]
    q = question.lower()
    is_trend = any(w in q for w in ["trend", "month", "over time", "daily"])
    fig = (px.line(df, x=x, y=y, title=question)
           if is_trend else px.bar(df, x=x, y=y, title=question))
    import json
    return json.loads(fig.to_json()), "line" if is_trend else "bar"
# ── Pre-flight SQL lookup ─────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.70

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def find_seeded_sql(question: str) -> str | None:
    """Return SQL for the closest seeded Q&A pair if above threshold."""
    best_score = 0.0
    best_sql   = None
    best_q     = None
    for seeded_q, seeded_sql in QA_PAIRS:
        score = _similarity(question, seeded_q)
        if score > best_score:
            best_score = score
            best_sql   = seeded_sql
            best_q     = seeded_q
    log.info("Pre-flight best match score=%.2f for: '%s'", best_score, best_q)
    if best_score >= SIMILARITY_THRESHOLD:
        log.info("Pre-flight HIT (score=%.2f) — bypassing agent.", best_score)
        return best_sql
    log.info("Pre-flight MISS (score=%.2f < %.2f) — forwarding to agent.",
             best_score, SIMILARITY_THRESHOLD)
    return None

# ── Direct SQL runner ─────────────────────────────────────────────────────────
def run_sql_direct(sql: str, question: str) -> JSONResponse:
    """Validate, execute SQL, sanitize numpy types, and return a JSONResponse."""
    valid, reason = validate_sql(sql)
    if not valid:
        log.warning("SQL blocked: %s | %s", sql, reason)
        return JSONResponse(status_code=400,
            content={"error": f"SQL rejected: {reason}", "sql_query": sql})
    try:
        conn = sqlite3.connect("clinic.db")
        df   = pd.read_sql_query(sql, conn)
        conn.close()
    except Exception as e:
        log.error("DB error: %s", e)
        return JSONResponse(status_code=500,
            content={"error": "Database query failed.", "detail": str(e),
                     "sql_query": sql})

    if df.empty:
        return JSONResponse(content={
            "message": "No data found.", "sql_query": sql,
            "columns": [], "rows": [], "row_count": 0,
            "chart": None, "chart_type": None,
        })

    # sanitize_rows converts np.int64 / np.float64 → plain Python int/float
    rows = sanitize_rows(df.values.tolist())
    chart_data, chart_type = auto_chart(df, question)
    if chart_data:
        log.info("Auto-generated %s chart.", chart_type)

    return JSONResponse({
        "message":    f"Found {len(df)} result(s).",
        "sql_query":  sql,
        "columns":    df.columns.tolist(),
        "rows":       rows,
        "row_count":  len(df),
        "chart":      chart_data,
        "chart_type": chart_type,
    })

# ── Agent call with retry ─────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 1.5
_TOOL_FAIL  = "failed to call a function"

async def call_agent(ctx: RequestContext, question: str):
    """
    Stream components from the agent with retry on Groq tool-call failures.
    Returns (sql, message, df_columns, df_rows, chart_data, chart_type).
    """
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        sql        = None
        message    = None
        df_rows    = []
        df_columns = []
        chart_data = None
        chart_type = None

        try:
            async for component in agent.send_message(
                request_context=ctx,
                message=question,
            ):
                rc = component.rich_component
                sc = component.simple_component

                log.info("COMPONENT type=%s | simple=%s",
                    type(rc).__name__,
                    getattr(sc, "text", "")[:80] if sc else None,
                )

                if isinstance(rc, RichTextComponent):
                    content = (rc.content or "").strip()
                    if not sql:
                        if rc.code_language == "sql":
                            sql = content
                            log.info("SQL from RichText code block.")
                        else:
                            extracted = extract_sql(content)
                            if extracted:
                                sql = extracted
                                log.info("SQL extracted from RichText prose.")
                            elif content and not message:
                                message = clean_message(content)
                    elif content and not message:
                        message = clean_message(content)

                elif isinstance(rc, CardComponent):
                    content = (rc.content or "").strip()
                    if not sql:
                        extracted = extract_sql(content)
                        if extracted:
                            sql = extracted
                            log.info("SQL extracted from CardComponent.")
                        elif content and not message:
                            message = clean_message(content)

                elif isinstance(rc, DataFrameComponent):
                    df_columns = rc.columns or []
                    df_rows    = rc.rows    or []
                    log.info("DataFrameComponent: %d rows, cols=%s",
                             len(df_rows), df_columns)

                elif isinstance(rc, ChartComponent):
                    chart_data = rc.data
                    chart_type = rc.chart_type

                if sc:
                    text = (getattr(sc, "text", "") or "").strip()
                    if not sql:
                        extracted = extract_sql(text)
                        if extracted:
                            sql = extracted
                            log.info("SQL extracted from simple_component.")
                    cleaned = clean_message(text)
                    if cleaned and not message and not cleaned.upper().startswith("SELECT"):
                        message = cleaned

            return sql, message, df_columns, df_rows, chart_data, chart_type

        except openai.APITimeoutError:
            raise
        except openai.APIConnectionError:
            raise
        except openai.APIError as e:
            if _TOOL_FAIL in str(e).lower():
                last_exc = e
                log.warning(
                    "Groq tool-call failure (attempt %d/%d) — retrying in %.1fs …",
                    attempt, MAX_RETRIES, RETRY_DELAY,
                )
                await asyncio.sleep(RETRY_DELAY)
                continue
            raise
        except Exception:
            raise

    log.error("All %d retry attempts failed. Last error: %s", MAX_RETRIES, last_exc)
    raise last_exc

# ── Query cache ───────────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}

# ── Request model ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        if len(v) > 500:
            raise ValueError("Question too long (max 500 chars).")
        return v

# ── POST /chat ────────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(request: Request, body: ChatRequest):
    import json as _json
    check_rate_limit(request.client.host)
    question = body.question
    log.info("QUESTION: %s", question)

    # ── Cache check ───────────────────────────────────────────────────────────
    key = question.lower().strip()
    if key in _cache:
        log.info("Cache hit.")
        return JSONResponse(_cache[key])

    # ── Pre-flight: bypass agent for known questions ───────────────────────────
    matched_sql = find_seeded_sql(question)
    if matched_sql:
        response = run_sql_direct(matched_sql, question)
        if response.status_code == 200:
            _cache[key] = _json.loads(response.body)
        return response

    # ── Agent path: novel questions ───────────────────────────────────────────
    ctx = RequestContext(user=DEFAULT_USER)

    try:
        sql, message, df_columns, df_rows, chart_data, chart_type = \
            await call_agent(ctx, question)

    except openai.APITimeoutError:
        log.warning("Groq API timed out for question: %s", question)
        return JSONResponse(status_code=504,
            content={"error": "The AI service timed out. Please try again in a moment."})
    except openai.APIConnectionError:
        log.warning("Groq API connection error for question: %s", question)
        return JSONResponse(status_code=503,
            content={"error": "Could not reach the AI service. Check your internet connection."})
    except openai.APIError as e:
        log.error("Groq API error after retries: %s", e)
        return JSONResponse(status_code=502,
            content={"error": "The AI service failed to respond correctly. Please rephrase your question."})
    except Exception as e:
        log.error("Agent error: %s", e)
        return JSONResponse(status_code=500,
            content={"error": "Agent error.", "detail": str(e)})

    # ── Agent returned DataFrame ──────────────────────────────────────────────
    if df_columns and df_rows:
        rows_list = sanitize_rows([[row.get(col) for col in df_columns] for row in df_rows])

        if sql:
            valid, reason = validate_sql(sql)
            if not valid:
                log.warning("SQL blocked: %s | %s", sql, reason)
                return JSONResponse(status_code=400,
                    content={"error": f"SQL rejected: {reason}", "sql_query": sql})

        if not chart_data:
            df_auto = pd.DataFrame(rows_list, columns=df_columns)
            chart_data, chart_type = auto_chart(df_auto, question)
            if chart_data:
                log.info("Auto-generated %s chart from DataFrameComponent.", chart_type)

        result = {
            "message":    clean_message(message) or f"Found {len(rows_list)} result(s).",
            "sql_query":  sql or "",
            "columns":    df_columns,
            "rows":       rows_list,
            "row_count":  len(rows_list),
            "chart":      chart_data,
            "chart_type": chart_type,
        }
        _cache[key] = result
        log.info("Returning %d rows from DataFrameComponent.", len(rows_list))
        return JSONResponse(result)

    # ── Agent returned SQL only — run it ourselves ────────────────────────────
    if sql:
        log.info("Running agent-extracted SQL directly: %s", sql[:120])
        response = run_sql_direct(sql, question)
        if response.status_code == 200:
            _cache[key] = _json.loads(response.body)
        return response

    # ── Nothing usable ────────────────────────────────────────────────────────
    error_msg = clean_message(message) or "Could not generate an answer. Please rephrase your question."
    log.warning("No usable result. Agent message: %s", error_msg)
    return JSONResponse(status_code=422, content={"error": error_msg})


# ── GET /health ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    try:
        conn = sqlite3.connect("clinic.db")
        conn.execute("SELECT 1")
        conn.close()
        db = "connected"
    except Exception:
        db = "error"

    try:
        mem_count = len(memory._memories) if memory else 0
    except Exception:
        mem_count = -1

    return {
        "status":             "ok",
        "database":           db,
        "agent_memory_items": mem_count,
        "timestamp":          datetime.now(timezone.utc).isoformat(),
    }