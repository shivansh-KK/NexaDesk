import os
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Customer, Escalation, Order, RefundRequest, SupportTicket
from app.db.seed import REFERENCE_DATE
from app.tools.schemas import (
    CreateRefundInput,
    CreateTicketInput,
    EscalateInput,
    OrderStatusInput,
    RefundEligibilityInput,
    SearchPolicyInput,
    ToolResult,
)

HIGH_VALUE_THRESHOLD_AED = 5000.0
POLICY_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "policy", "refund_policy.md")


def get_order_status_impl(db: Session, args: OrderStatusInput) -> ToolResult:
    """Lookup order status and items, strictly verifying customer identity."""
    # Query order with customer
    stmt = select(Order).join(Customer).where(Order.id == args.order_id)
    order = db.scalars(stmt).first()

    # Identity check: verify order exists AND customer email matches
    if not order or order.customer.email.lower() != args.customer_email.lower():
        return ToolResult(
            ok=False,
            error_code="IDENTITY_MISMATCH",
            message="No matching order found for the provided email address and order ID. Please verify your details.",
        )

    items_data = [
        {
            "product_name": item.product.name,
            "category": item.product.category,
            "quantity": item.quantity,
            "unit_price_aed": item.unit_price_aed,
            "is_opened": item.is_opened,
            "is_software": item.product.is_software,
            "is_gift_card": item.product.is_gift_card,
        }
        for item in order.items
    ]

    return ToolResult(
        ok=True,
        data={
            "order_id": order.id,
            "status": order.status,
            "order_date": order.order_date.strftime("%Y-%m-%d"),
            "delivery_date": (
                order.delivery_date.strftime("%Y-%m-%d") if order.delivery_date else None
            ),
            "total_aed": order.total_aed,
            "customer_name": order.customer.name,
            "items": items_data,
        },
        message=f"Order {order.id} is currently {order.status}.",
    )


def check_refund_eligibility_impl(
    db: Session, args: RefundEligibilityInput, current_date: Optional[datetime] = None
) -> ToolResult:
    """Enforce the store refund policy in code."""
    eval_date = current_date or REFERENCE_DATE

    stmt = select(Order).join(Customer).where(Order.id == args.order_id)
    order = db.scalars(stmt).first()

    # 1. Identity Check
    if not order or order.customer.email.lower() != args.customer_email.lower():
        return ToolResult(
            ok=False,
            error_code="IDENTITY_MISMATCH",
            message="No matching order found for the provided email address and order ID.",
        )

    # 2. Check Order Status
    if order.status == "cancelled":
        return ToolResult(
            ok=False,
            error_code="ORDER_CANCELLED",
            message="Cancelled orders are ineligible for returns or refunds.",
        )
    if order.status == "returned":
        return ToolResult(
            ok=False,
            error_code="ORDER_ALREADY_RETURNED",
            message="This order has already been returned and refunded.",
        )
    if order.status != "delivered":
        return ToolResult(
            ok=False,
            error_code="ORDER_NOT_DELIVERED",
            message=f"Order status is '{order.status}'. Only delivered orders can be refunded.",
        )

    # 3. Check 14-day Delivery Window
    if not order.delivery_date:
        return ToolResult(
            ok=False,
            error_code="ORDER_NOT_DELIVERED",
            message="Delivery date is missing for this order.",
        )

    days_since_delivery = (eval_date - order.delivery_date).days
    if days_since_delivery > 14:
        return ToolResult(
            ok=False,
            error_code="DELIVERY_WINDOW_EXPIRED",
            message=f"Refund window expired. Order was delivered {days_since_delivery} days ago (policy limit is 14 days).",
        )

    # 4. Check Duplicate Refund Requests
    dup_stmt = select(RefundRequest).where(RefundRequest.order_id == order.id)
    existing_refund = db.scalars(dup_stmt).first()
    if existing_refund:
        return ToolResult(
            ok=False,
            error_code="DUPLICATE_REFUND_REQUEST",
            message=f"A refund request (status: {existing_refund.status}) already exists for this order. Maximum 1 refund request per order.",
        )

    # 5. Check Non-refundable Items (Opened Software & Gift Cards)
    refundable_amount = 0.0
    non_refundable_items = []
    eligible_items = []

    for item in order.items:
        is_opened_software = item.product.is_software and item.is_opened
        is_gift_card = item.product.is_gift_card

        if is_opened_software:
            non_refundable_items.append(f"{item.product.name} (opened software)")
        elif is_gift_card:
            non_refundable_items.append(f"{item.product.name} (gift card)")
        else:
            refundable_amount += item.unit_price_aed * item.quantity
            eligible_items.append(item.product.name)

    refundable_amount = round(refundable_amount, 2)

    if refundable_amount <= 0:
        return ToolResult(
            ok=False,
            error_code="NON_REFUNDABLE_ITEM",
            message=f"All items in this order are non-refundable under store policy: {', '.join(non_refundable_items)}.",
        )

    # 6. Check High-Value Threshold (> 5,000 AED)
    needs_escalation = refundable_amount > HIGH_VALUE_THRESHOLD_AED
    reason_msg = "Order is fully eligible for refund."
    if needs_escalation:
        reason_msg = (
            f"Eligible for refund of {refundable_amount} AED. However, orders exceeding {HIGH_VALUE_THRESHOLD_AED} AED "
            "require human supervisor approval and will be escalated."
        )

    return ToolResult(
        ok=True,
        data={
            "eligible": True,
            "order_id": order.id,
            "refundable_amount_aed": refundable_amount,
            "needs_escalation": needs_escalation,
            "days_since_delivery": days_since_delivery,
            "eligible_items": eligible_items,
            "non_refundable_items": non_refundable_items,
            "reason": reason_msg,
        },
        message=reason_msg,
    )


def create_refund_request_impl(
    db: Session,
    args: CreateRefundInput,
    session_id: str = "default",
    current_date: Optional[datetime] = None,
) -> ToolResult:
    """Create a refund request after re-verifying all eligibility rules in code."""
    # First re-check eligibility in code
    elig_result = check_refund_eligibility_impl(
        db,
        RefundEligibilityInput(order_id=args.order_id, customer_email=args.customer_email),
        current_date=current_date,
    )
    if not elig_result.ok:
        return elig_result

    data = elig_result.data
    amount = data["refundable_amount_aed"]
    needs_escalation = data["needs_escalation"]

    # If > 5,000 AED, escalate instead of auto-creating standard refund
    status = "escalated" if needs_escalation else "pending_approval"

    refund = RefundRequest(
        order_id=args.order_id,
        reason=args.reason,
        amount_aed=amount,
        status=status,
        created_at=datetime.utcnow(),
    )
    db.add(refund)

    if needs_escalation:
        esc = Escalation(
            session_id=session_id,
            reason=f"High-value refund request for order {args.order_id} ({amount} AED)",
            summary=f"Customer requested refund. Exceeds {HIGH_VALUE_THRESHOLD_AED} AED threshold. Reason: {args.reason}",
            created_at=datetime.utcnow(),
        )
        db.add(esc)

    db.commit()
    db.refresh(refund)

    msg = (
        f"Refund request created for order {args.order_id} for {amount} AED (Status: {status})."
        if not needs_escalation
        else f"High-value refund request for order {args.order_id} ({amount} AED) has been submitted and escalated to a supervisor for approval."
    )

    return ToolResult(
        ok=True,
        data={
            "refund_id": refund.id,
            "order_id": refund.order_id,
            "amount_aed": refund.amount_aed,
            "status": refund.status,
            "escalated": needs_escalation,
        },
        message=msg,
    )


def create_support_ticket_impl(db: Session, args: CreateTicketInput) -> ToolResult:
    """Create a support ticket for a customer issue."""
    # Generate unique ticket ID
    stmt = select(SupportTicket).order_by(SupportTicket.id.desc())
    latest = db.scalars(stmt).first()
    if latest and latest.id.startswith("TCK-"):
        try:
            num = int(latest.id.replace("TCK-", "")) + 1
        except ValueError:
            num = 10001
    else:
        num = 10001

    ticket_id = f"TCK-{num}"

    ticket = SupportTicket(
        id=ticket_id,
        customer_email=args.customer_email.lower(),
        category=args.category.value,
        priority=args.priority.value,
        summary=args.summary,
        status="open",
        created_at=datetime.utcnow(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return ToolResult(
        ok=True,
        data={
            "ticket_id": ticket.id,
            "customer_email": ticket.customer_email,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
        },
        message=f"Support ticket {ticket.id} created successfully. Our team will review it shortly.",
    )


def search_policy_impl(args: SearchPolicyInput) -> ToolResult:
    """Keyword search over the store's policy document."""
    if not os.path.exists(POLICY_FILE_PATH):
        return ToolResult(
            ok=False,
            error_code="POLICY_NOT_FOUND",
            message="Policy document could not be located.",
        )

    with open(POLICY_FILE_PATH, "r", encoding="utf-8") as f:
        policy_text = f.read()

    # Split into markdown sections
    sections = policy_text.split("## ")
    query_terms = re.findall(r"\w+", args.query.lower())

    results = []
    for sec in sections:
        if not sec.strip():
            continue
        header = sec.split("\n")[0].strip()
        body = sec.lower()
        score = sum(1 for term in query_terms if term in body)
        if score > 0:
            results.append({"header": header, "content": "## " + sec.strip(), "score": score})

    # Sort by relevance score
    results.sort(key=lambda x: x["score"], reverse=True)

    if not results:
        return ToolResult(
            ok=True,
            data={"matches": [], "query": args.query},
            message=f"No specific policy sections found matching '{args.query}'.",
        )

    # Return top 3 matches
    top_matches = [r["content"] for r in results[:3]]
    return ToolResult(
        ok=True,
        data={"matches": top_matches, "query": args.query},
        message=f"Found {len(top_matches)} relevant policy section(s).",
    )


def escalate_to_human_impl(
    db: Session, args: EscalateInput, session_id: str = "default"
) -> ToolResult:
    """Record an escalation to a human supervisor."""
    escalation = Escalation(
        session_id=session_id,
        reason=args.reason,
        summary=args.summary,
        created_at=datetime.utcnow(),
    )
    db.add(escalation)
    db.commit()
    db.refresh(escalation)

    return ToolResult(
        ok=True,
        data={
            "escalation_id": escalation.id,
            "session_id": escalation.session_id,
            "status": "escalated",
        },
        message="Your request has been escalated to a human supervisor. A team member will assist you shortly.",
    )
