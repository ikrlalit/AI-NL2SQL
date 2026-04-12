# main.py
import re
import time
import uuid
import sqlite3
import logging
from datetime import datetime, timezone

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
    check_rate_limit(request.client.host)
    question = body.question
    log.info("QUESTION: %s", question)

    # Cache check
    key = question.lower().strip()
    if key in _cache:
        log.info("Cache hit.")
        return JSONResponse(_cache[key])

    ctx = RequestContext(user=DEFAULT_USER)

    # ── Collect all streamed components ───────────────────────────────────────
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

            # ── DEBUG (remove after confirming) ───────────────────────────
            log.info("COMPONENT type=%s | simple=%s",
                type(rc).__name__,
                getattr(sc, "text", "")[:80] if sc else None
            )

            # ── Extract SQL from RichTextComponent (code_language=sql) ────
            if isinstance(rc, RichTextComponent):
                content = (rc.content or "").strip()
                if rc.code_language == "sql" and not sql:
                    sql = content
                elif content.upper().startswith("SELECT") and not sql:
                    sql = content
                elif content and not message:
                    message = content

            # ── Extract SQL from CardComponent ────────────────────────────
            elif isinstance(rc, CardComponent):
                content = (rc.content or "").strip()
                if content.upper().startswith("SELECT") and not sql:
                    sql = content
                elif content and not message:
                    message = content

            # ── Extract results from DataFrameComponent ───────────────────
            elif isinstance(rc, DataFrameComponent):
                df_columns = rc.columns or []
                df_rows    = rc.rows    or []   # list of dicts
                log.info("DataFrameComponent: %d rows, cols=%s",
                         len(df_rows), df_columns)

            # ── Extract chart from ChartComponent ─────────────────────────
            elif isinstance(rc, ChartComponent):
                chart_data = rc.data
                chart_type = rc.chart_type

            # ── Extract message from simple_component ─────────────────────
            if sc:
                text = (getattr(sc, "text", "") or "").strip()
                if text and not message and not text.upper().startswith("SELECT"):
                    message = text

    except Exception as e:
        log.error("Agent error: %s", e)
        return JSONResponse(status_code=500,
            content={"error": "Agent error.", "detail": str(e)})

    # ── If agent returned DataFrame results directly — use them ───────────────
    if df_columns and df_rows:
        # Convert list-of-dicts to list-of-lists matching column order
        rows_list = [[row.get(col) for col in df_columns] for row in df_rows]

        # Validate SQL if we got it (for audit), but don't block on it
        if sql:
            valid, reason = validate_sql(sql)
            if not valid:
                log.warning("SQL blocked: %s | %s", sql, reason)
                return JSONResponse(status_code=400,
                    content={"error": f"SQL rejected: {reason}", "sql_query": sql})

        result = {
            "message":    message or "Here are the results.",
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

    # ── Fallback: run SQL ourselves if agent returned SQL but no DataFrame ─────
    if sql:
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
                content={"error": "Database query failed.",
                         "detail": str(e), "sql_query": sql})

        if df.empty:
            return JSONResponse(content={
                "message": "No data found.", "sql_query": sql,
                "columns": [], "rows": [], "row_count": 0,
                "chart": None, "chart_type": None,
            })

        # Auto-generate chart if agent didn't provide one
        if not chart_data:
            num = df.select_dtypes(include="number").columns.tolist()
            cat = [c for c in df.columns if c not in num]
            if num and (cat or len(df.columns) > 1):
                x = cat[0] if cat else df.columns[0]
                y = num[0]
                q = question.lower()
                fig = (px.line(df, x=x, y=y, title=question)
                       if any(w in q for w in ["trend","month","over time","daily"])
                       else px.bar(df, x=x, y=y, title=question))
                chart_data = fig.to_dict()
                chart_type = "line" if any(w in q for w in ["trend","month","over time"]) else "bar"

        result = {
            "message":    message or "Here are the results.",
            "sql_query":  sql,
            "columns":    df.columns.tolist(),
            "rows":       df.values.tolist(),
            "row_count":  len(df),
            "chart":      chart_data,
            "chart_type": chart_type,
        }
        _cache[key] = result
        return JSONResponse(result)

    # ── Nothing usable came back ──────────────────────────────────────────────
    return JSONResponse(status_code=422,
        content={"error": "Could not generate an answer. Please rephrase your question."})


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