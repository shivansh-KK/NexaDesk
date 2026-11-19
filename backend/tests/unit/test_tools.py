import pytest
from pydantic import ValidationError

from app.tools.registry import WRITE_TOOLS, execute_tool
from app.tools.schemas import (
    OrderStatusInput,
)


def test_write_tools_classification():
    assert "create_refund_request" in WRITE_TOOLS
    assert "create_support_ticket" in WRITE_TOOLS
    assert "get_order_status" not in WRITE_TOOLS
    assert "check_refund_eligibility" not in WRITE_TOOLS


def test_get_order_status_happy_path(test_db):
    result = execute_tool(
        "get_order_status",
        {"order_id": "ORD-10001", "customer_email": "alice.smith@example.com"},
        test_db,
    )
    assert result.ok is True
    assert result.error_code is None
    assert result.data["order_id"] == "ORD-10001"
    assert result.data["status"] == "delivered"
    assert len(result.data["items"]) == 1
    assert result.data["customer_name"] == "Alice Smith"


def test_get_order_status_identity_mismatch(test_db):
    # Correct order ID, wrong email
    result = execute_tool(
        "get_order_status",
        {"order_id": "ORD-10001", "customer_email": "wrong.person@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "IDENTITY_MISMATCH"
    assert "No matching order found" in result.message


def test_get_order_status_nonexistent_order(test_db):
    # Nonexistent order ID (valid format)
    result = execute_tool(
        "get_order_status",
        {"order_id": "ORD-99999", "customer_email": "alice.smith@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "IDENTITY_MISMATCH"


def test_order_id_regex_validation():
    with pytest.raises(ValidationError):
        OrderStatusInput(order_id="10001", customer_email="alice.smith@example.com")
    with pytest.raises(ValidationError):
        OrderStatusInput(order_id="ORD-123", customer_email="alice.smith@example.com")
    with pytest.raises(ValidationError):
        OrderStatusInput(order_id="ORD-10001-A", customer_email="alice.smith@example.com")


def test_check_refund_eligibility_eligible(test_db):
    # ORD-10001: delivered 4 days ago, iPhone 15 Pro, price 4299 AED (<= 5000 AED)
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10001", "customer_email": "alice.smith@example.com"},
        test_db,
    )
    assert result.ok is True
    assert result.data["eligible"] is True
    assert result.data["refundable_amount_aed"] == 4299.0
    assert result.data["needs_escalation"] is False


def test_check_refund_eligibility_expired_window(test_db):
    # ORD-10002: delivered 25 days ago (> 14 days)
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10002", "customer_email": "bob.jones@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "DELIVERY_WINDOW_EXPIRED"


def test_check_refund_eligibility_cancelled_order(test_db):
    # ORD-10003: cancelled
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10003", "customer_email": "carol.white@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "ORDER_CANCELLED"


def test_check_refund_eligibility_returned_order(test_db):
    # ORD-10004: returned
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10004", "customer_email": "david.brown@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "ORDER_ALREADY_RETURNED"


def test_check_refund_eligibility_high_value(test_db):
    # ORD-10005: MacBook Pro (12,499 AED > 5,000 AED)
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10005", "customer_email": "eva.green@example.com"},
        test_db,
    )
    assert result.ok is True
    assert result.data["eligible"] is True
    assert result.data["needs_escalation"] is True
    assert result.data["refundable_amount_aed"] == 12499.0


def test_check_refund_eligibility_opened_software(test_db):
    # ORD-10006: contains opened software
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10006", "customer_email": "frank.miller@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "NON_REFUNDABLE_ITEM"


def test_check_refund_eligibility_gift_card(test_db):
    # ORD-10007: gift card
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10007", "customer_email": "grace.lee@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "NON_REFUNDABLE_ITEM"


def test_check_refund_eligibility_duplicate(test_db):
    # ORD-10008: already has a refund request
    result = execute_tool(
        "check_refund_eligibility",
        {"order_id": "ORD-10008", "customer_email": "hassan.ali@example.com"},
        test_db,
    )
    assert result.ok is False
    assert result.error_code == "DUPLICATE_REFUND_REQUEST"


def test_create_refund_request_happy_path(test_db):
    result = execute_tool(
        "create_refund_request",
        {
            "order_id": "ORD-10001",
            "customer_email": "alice.smith@example.com",
            "reason": "Battery life does not meet expectations",
        },
        test_db,
    )
    assert result.ok is True
    assert result.data["order_id"] == "ORD-10001"
    assert result.data["amount_aed"] == 4299.0
    assert result.data["status"] == "pending_approval"
    assert result.data["escalated"] is False

    # Second attempt must fail as duplicate
    dup_result = execute_tool(
        "create_refund_request",
        {
            "order_id": "ORD-10001",
            "customer_email": "alice.smith@example.com",
            "reason": "Trying again",
        },
        test_db,
    )
    assert dup_result.ok is False
    assert dup_result.error_code == "DUPLICATE_REFUND_REQUEST"


def test_create_refund_request_high_value_escalates(test_db):
    result = execute_tool(
        "create_refund_request",
        {
            "order_id": "ORD-10005",
            "customer_email": "eva.green@example.com",
            "reason": "Display panel flickering",
        },
        test_db,
    )
    assert result.ok is True
    assert result.data["status"] == "escalated"
    assert result.data["escalated"] is True


def test_create_support_ticket(test_db):
    result = execute_tool(
        "create_support_ticket",
        {
            "customer_email": "alice.smith@example.com",
            "category": "delivery",
            "priority": "high",
            "summary": "Courier marked delivered but package not received.",
        },
        test_db,
    )
    assert result.ok is True
    assert result.data["ticket_id"].startswith("TCK-")
    assert result.data["status"] == "open"


def test_search_policy(test_db):
    result = execute_tool(
        "search_policy",
        {"query": "refund 14 days"},
        test_db,
    )
    assert result.ok is True
    assert len(result.data["matches"]) > 0
    assert "14 calendar days" in result.data["matches"][0]


def test_escalate_to_human(test_db):
    result = execute_tool(
        "escalate_to_human",
        {"reason": "Customer is extremely upset and requested a supervisor"},
        test_db,
        session_id="test-session-123",
    )
    assert result.ok is True
    assert result.data["status"] == "escalated"
