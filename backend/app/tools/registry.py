from typing import Any, Dict, List

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.tools.implementations import (
    check_refund_eligibility_impl,
    create_refund_request_impl,
    create_support_ticket_impl,
    escalate_to_human_impl,
    get_order_status_impl,
    search_policy_impl,
)
from app.tools.schemas import (
    CreateRefundInput,
    CreateTicketInput,
    EscalateInput,
    OrderStatusInput,
    RefundEligibilityInput,
    SearchPolicyInput,
    ToolResult,
)

# Tools that modify state and require human/user confirmation when guardrails are enabled
WRITE_TOOLS = {"create_refund_request", "create_support_ticket"}

TOOL_DEFINITIONS = [
    {
        "name": "get_order_status",
        "description": "Lookup an order's status, delivery dates, items, and total amount. Requires both the exact order ID and the customer's email.",
        "parameters": OrderStatusInput.model_json_schema(),
        "input_model": OrderStatusInput,
        "is_write": False,
    },
    {
        "name": "check_refund_eligibility",
        "description": "Check if an order is eligible for a refund according to store policy (delivered within 14 days, non-software/giftcard, <= 5000 AED).",
        "parameters": RefundEligibilityInput.model_json_schema(),
        "input_model": RefundEligibilityInput,
        "is_write": False,
    },
    {
        "name": "create_refund_request",
        "description": "Submit an official refund request for an eligible delivered order. Modifies database records (WRITE action).",
        "parameters": CreateRefundInput.model_json_schema(),
        "input_model": CreateRefundInput,
        "is_write": True,
    },
    {
        "name": "create_support_ticket",
        "description": "Open a new support ticket for issues like delivery delay, defective products, billing questions, or account help. (WRITE action).",
        "parameters": CreateTicketInput.model_json_schema(),
        "input_model": CreateTicketInput,
        "is_write": True,
    },
    {
        "name": "search_policy",
        "description": "Search the official store policy (refund rules, return conditions, warranty, shipping timelines) using keywords.",
        "parameters": SearchPolicyInput.model_json_schema(),
        "input_model": SearchPolicyInput,
        "is_write": False,
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate the conversation to a human support agent or supervisor when requested, for complex issues, or for high-value disputes.",
        "parameters": EscalateInput.model_json_schema(),
        "input_model": EscalateInput,
        "is_write": False,
    },
]

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {t["name"]: t for t in TOOL_DEFINITIONS}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return JSON schemas for LLM function calling."""
    schemas = []
    for tool in TOOL_DEFINITIONS:
        # Simplify schema for LLM providers
        params = tool["parameters"].copy()
        params.pop("title", None)
        schemas.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": params,
            }
        )
    return schemas


def execute_tool(
    name: str, raw_args: Dict[str, Any], db: Session, session_id: str = "default"
) -> ToolResult:
    """Validate arguments with Pydantic and execute the tool."""
    if name not in TOOL_REGISTRY:
        return ToolResult(
            ok=False,
            error_code="UNKNOWN_TOOL",
            message=f"Tool '{name}' is not recognized.",
        )

    tool_meta = TOOL_REGISTRY[name]
    model_cls = tool_meta["input_model"]

    # 1. Strict Pydantic validation
    try:
        validated_args = model_cls(**raw_args)
    except ValidationError as e:
        error_details = "; ".join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        return ToolResult(
            ok=False,
            error_code="VALIDATION_ERROR",
            message=f"Invalid arguments for {name}: {error_details}",
        )

    # 2. Execution routing
    try:
        if name == "get_order_status":
            return get_order_status_impl(db, validated_args)
        elif name == "check_refund_eligibility":
            return check_refund_eligibility_impl(db, validated_args)
        elif name == "create_refund_request":
            return create_refund_request_impl(db, validated_args, session_id=session_id)
        elif name == "create_support_ticket":
            return create_support_ticket_impl(db, validated_args)
        elif name == "search_policy":
            return search_policy_impl(validated_args)
        elif name == "escalate_to_human":
            return escalate_to_human_impl(db, validated_args, session_id=session_id)
        else:
            return ToolResult(
                ok=False, error_code="UNKNOWN_TOOL", message=f"Tool {name} has no handler."
            )
    except Exception as e:
        return ToolResult(
            ok=False,
            error_code="EXECUTION_ERROR",
            message=f"An error occurred executing {name}: {str(e)}",
        )
