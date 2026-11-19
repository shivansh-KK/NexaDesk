import json
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Trace


def log_trace(
    db: Session,
    session_id: str,
    turn: int,
    role: str,
    content: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_args: Optional[Any] = None,
    tool_result: Optional[Any] = None,
    latency_ms: Optional[float] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    error: Optional[str] = None,
    guardrail_flags: Optional[str] = None,
) -> Trace:
    """Persist a single execution turn or tool call event to the database traces table."""
    tool_args_str = None
    if tool_args is not None:
        tool_args_str = (
            json.dumps(tool_args) if isinstance(tool_args, (dict, list)) else str(tool_args)
        )

    tool_result_str = None
    if tool_result is not None:
        tool_result_str = (
            json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
        )

    trace = Trace(
        session_id=session_id,
        turn=turn,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_args=tool_args_str,
        tool_result=tool_result_str,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error=error,
        guardrail_flags=guardrail_flags,
        created_at=datetime.utcnow(),
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return trace


def get_session_traces(db: Session, session_id: str) -> List[Trace]:
    """Retrieve all traces associated with a given session in chronological order."""
    stmt = select(Trace).where(Trace.session_id == session_id).order_by(Trace.id.asc())
    return list(db.scalars(stmt).all())


def get_all_traces(db: Session, limit: int = 100, offset: int = 0) -> List[Trace]:
    """Retrieve recent traces across all sessions."""
    stmt = select(Trace).order_by(Trace.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())
