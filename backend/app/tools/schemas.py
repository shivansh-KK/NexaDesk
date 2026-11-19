import re
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ORDER_ID_PATTERN = r"^ORD-\d{5}$"
ORDER_ID_REGEX = re.compile(ORDER_ID_PATTERN)


class TicketCategory(str, Enum):
    delivery = "delivery"
    product_issue = "product_issue"
    billing = "billing"
    account = "account"
    other = "other"


class TicketPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class OrderStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(
        ..., description="The unique order ID matching pattern ORD-XXXXX (e.g. ORD-10001)"
    )
    customer_email: EmailStr = Field(
        ..., description="The customer's email address associated with the order"
    )

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not ORDER_ID_REGEX.match(v):
            raise ValueError(
                f"Invalid order_id format '{v}'. Must match pattern ORD-XXXXX (e.g. ORD-10001)."
            )
        return v


class RefundEligibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(
        ..., description="The unique order ID matching pattern ORD-XXXXX (e.g. ORD-10001)"
    )
    customer_email: EmailStr = Field(
        ..., description="The customer's email address associated with the order"
    )

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not ORDER_ID_REGEX.match(v):
            raise ValueError(
                f"Invalid order_id format '{v}'. Must match pattern ORD-XXXXX (e.g. ORD-10001)."
            )
        return v


class CreateRefundInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(
        ..., description="The unique order ID matching pattern ORD-XXXXX (e.g. ORD-10001)"
    )
    customer_email: EmailStr = Field(
        ..., description="The customer's email address associated with the order"
    )
    reason: str = Field(
        ..., min_length=5, max_length=500, description="Detailed reason for the refund request"
    )

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not ORDER_ID_REGEX.match(v):
            raise ValueError(
                f"Invalid order_id format '{v}'. Must match pattern ORD-XXXXX (e.g. ORD-10001)."
            )
        return v


class CreateTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: EmailStr = Field(..., description="The customer's email address")
    category: TicketCategory = Field(
        ..., description="Category: delivery, product_issue, billing, account, or other"
    )
    priority: TicketPriority = Field(
        TicketPriority.medium, description="Priority: low, medium, or high"
    )
    summary: str = Field(
        ..., min_length=5, max_length=1000, description="Clear summary of the support issue"
    )


class SearchPolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Keywords or topic to search within store policies",
    )


class EscalateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Specific reason for escalating to a human agent",
    )
    summary: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional conversation context or summary for human review",
    )


class ToolResult(BaseModel):
    ok: bool
    data: Optional[Any] = None
    error_code: Optional[str] = None
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error_code": self.error_code,
            "message": self.message,
        }
