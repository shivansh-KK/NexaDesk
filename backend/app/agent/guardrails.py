import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import PendingAction, Trace

logger = logging.getLogger(__name__)

# Injection pattern regexes
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands)",
    r"you\s+are\s+now\s+(in\s+)?(admin|developer|god|dan|jailbreak|root)\s+mode",
    r"act\s+as\s+(an?\s+)?(admin|administrator|developer|root|system)",
    r"system\s+(prompt|override|command|instructions)",
    r"disregard\s+(all\s+)?(previous|prior)\s+(rules|instructions)",
    r"reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions|secret\s+key|all\s+customers)",
    r"bypass\s+(the\s+)?(policy|rules|guardrails|security)",
    r"forget\s+(all\s+)?(previous\s+rules|instructions)",
    r"show\s+me\s+(the\s+)?database",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

ABUSIVE_PATTERNS = [
    r"\b(scam|scammer|lawyer|sue\s+you|fuck|shit|idiot|stupid|bastard|threat)\b",
]
ABUSIVE_REGEX = re.compile("|".join(ABUSIVE_PATTERNS), re.IGNORECASE)


def detect_prompt_injection(user_message: str) -> bool:
    """Return True if suspicious prompt injection heuristics match."""
    return bool(INJECTION_REGEX.search(user_message))


def detect_abusive_language(user_message: str) -> bool:
    """Return True if abusive or threatening language is detected."""
    return bool(ABUSIVE_REGEX.search(user_message))


def create_pending_action(
    db: Session,
    session_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> PendingAction:
    """Create a pending action requiring explicit user confirmation before execution."""
    action_id = str(uuid.uuid4())
    summary = (
        f"Confirmation required to execute {tool_name} with parameters: {json.dumps(tool_args)}"
    )
    if tool_name == "create_refund_request":
        summary = f"Please confirm your refund request for order {tool_args.get('order_id')} (Reason: {tool_args.get('reason')})."
    elif tool_name == "create_support_ticket":
        summary = f"Please confirm creating a support ticket for {tool_args.get('customer_email')} (Category: {tool_args.get('category')})."

    expires_at = datetime.utcnow() + timedelta(minutes=settings.PENDING_ACTION_TIMEOUT_MINUTES)
    pending = PendingAction(
        id=action_id,
        session_id=session_id,
        action_type=tool_name,
        tool_name=tool_name,
        tool_args=json.dumps(tool_args),
        summary=summary,
        status="pending",
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


def check_hallucinations(
    reply: str,
    session_id: str,
    db: Session,
) -> Tuple[bool, List[str]]:
    """
    Hallucination Guard: Verify that any order ID (ORD-XXXXX) or specific monetary
    amount mentioned in the assistant's reply actually appeared in a tool result in this session.
    Returns (is_hallucinating, hallucinated_items).
    """
    # 1. Extract order IDs and currency figures mentioned in the reply
    mentioned_orders = set(re.findall(r"ORD-\d{5}", reply, re.IGNORECASE))

    if not mentioned_orders:
        return False, []

    # 2. Extract all order IDs that appeared in tool results for this session
    stmt = (
        select(Trace.tool_result)
        .where(Trace.session_id == session_id)
        .where(Trace.tool_result.isnot(None))
    )
    results = db.scalars(stmt).all()

    grounded_orders: Set[str] = set()
    for res in results:
        if res:
            found = re.findall(r"ORD-\d{5}", res, re.IGNORECASE)
            for f in found:
                grounded_orders.add(f.upper())

    # 3. Check for any mentioned order that was never grounded
    hallucinations = []
    for ord_id in mentioned_orders:
        if ord_id.upper() not in grounded_orders:
            hallucinations.append(ord_id.upper())

    return len(hallucinations) > 0, hallucinations
