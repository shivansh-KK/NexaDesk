import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.agent import AgentResult, run_agent_turn
from app.config import settings
from app.db.models import PendingAction, Trace
from app.db.seed import seed_database
from app.db.session import get_db, init_db
from app.tools.registry import execute_tool
from app.tracing import get_session_traces, log_trace

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ShopAssist Customer Support API",
    description="A reliable, guarded tool-calling customer-support AI agent backend.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local dev and frontend Vite app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique conversation session ID")
    message: str = Field(..., min_length=1, description="Customer message")


class ChatResponse(BaseModel):
    reply: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    pending_action: Optional[Dict[str, Any]] = None
    escalated: bool = False


class ConfirmRequest(BaseModel):
    session_id: str
    action_id: str
    confirm: bool


class ConfirmResponse(BaseModel):
    reply: str
    result: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    provider: str
    guardrails_enabled: bool
    prompt_version: str


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health and status endpoint."""
    return HealthResponse(
        status="ok",
        provider=settings.DEFAULT_PROVIDER,
        guardrails_enabled=settings.GUARDRAILS_ENABLED,
        prompt_version=settings.PROMPT_VERSION,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """Primary chat endpoint communicating with the AI agent."""
    result: AgentResult = await run_agent_turn(
        session_id=req.session_id,
        user_message=req.message,
        db=db,
    )
    return ChatResponse(
        reply=result.reply,
        tool_calls=result.tool_calls,
        pending_action=result.pending_action,
        escalated=result.escalated,
    )


@app.post("/chat/confirm", response_model=ConfirmResponse)
def confirm_action_endpoint(req: ConfirmRequest, db: Session = Depends(get_db)):
    """Confirmation gate endpoint to approve or cancel pending WRITE actions."""
    stmt = (
        select(PendingAction)
        .where(PendingAction.id == req.action_id)
        .where(PendingAction.session_id == req.session_id)
    )
    action = db.scalars(stmt).first()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pending action '{req.action_id}' not found for this session.",
        )

    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action '{req.action_id}' has already been processed (status: {action.status}).",
        )

    if datetime.utcnow() > action.expires_at:
        action.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This pending action has expired. Please initiate a new request.",
        )

    if not req.confirm:
        action.status = "rejected"
        db.commit()
        cancel_msg = "The action has been cancelled upon your request. Is there anything else I can assist you with?"
        log_trace(
            db=db,
            session_id=req.session_id,
            turn=100,
            role="assistant",
            content=cancel_msg,
            guardrail_flags="action_cancelled",
        )
        return ConfirmResponse(reply=cancel_msg, result={"confirmed": False, "status": "rejected"})

    # Action is confirmed: execute the write tool
    action.status = "confirmed"
    raw_args = json.loads(action.tool_args)
    tool_result = execute_tool(
        name=action.tool_name,
        raw_args=raw_args,
        db=db,
        session_id=req.session_id,
    )
    db.commit()

    log_trace(
        db=db,
        session_id=req.session_id,
        turn=101,
        role="tool",
        tool_name=action.tool_name,
        tool_args=raw_args,
        tool_result=tool_result.to_dict(),
        guardrail_flags="action_confirmed",
    )

    reply = f"Thank you! Your action has been confirmed and executed: {tool_result.message}"
    log_trace(
        db=db,
        session_id=req.session_id,
        turn=102,
        role="assistant",
        content=reply,
    )

    return ConfirmResponse(reply=reply, result=tool_result.to_dict())


@app.get("/sessions/{session_id}")
def get_session_history(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the full reconstructed message history for a conversation session."""
    traces = get_session_traces(db, session_id)
    messages = []
    for t in traces:
        messages.append(
            {
                "id": t.id,
                "turn": t.turn,
                "role": t.role,
                "content": t.content,
                "tool_name": t.tool_name,
                "tool_args": json.loads(t.tool_args) if t.tool_args else None,
                "tool_result": json.loads(t.tool_result) if t.tool_result else None,
                "latency_ms": t.latency_ms,
                "guardrail_flags": t.guardrail_flags,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        )
    return {"session_id": session_id, "messages": messages}


@app.get("/traces")
def get_traces_endpoint(
    session_id: Optional[str] = Query(None, description="Filter traces by session ID"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve trace records for observability and auditing."""
    if session_id:
        traces = get_session_traces(db, session_id)
    else:
        stmt = select(Trace).order_by(Trace.id.desc()).limit(limit)
        traces = list(db.scalars(stmt).all())

    return [
        {
            "id": t.id,
            "session_id": t.session_id,
            "turn": t.turn,
            "role": t.role,
            "content": t.content,
            "tool_name": t.tool_name,
            "tool_args": json.loads(t.tool_args) if t.tool_args else None,
            "tool_result": json.loads(t.tool_result) if t.tool_result else None,
            "latency_ms": t.latency_ms,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "error": t.error,
            "guardrail_flags": t.guardrail_flags,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in traces
    ]


@app.post("/admin/reset-db")
def admin_reset_database(db: Session = Depends(get_db)):
    """Development/testing endpoint to reset and reseed the database."""
    bind = db.get_bind()
    from app.db.models import Base

    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)
    n_cust, n_prod, n_ord, n_items = seed_database(db)
    return {
        "status": "database_reset",
        "counts": {
            "customers": n_cust,
            "products": n_prod,
            "orders": n_ord,
            "order_items": n_items,
        },
    }
