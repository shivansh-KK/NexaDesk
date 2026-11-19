import re
from typing import Any, Dict, List, Optional

from app.agent.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall


class MockProvider(LLMProvider):
    """
    Deterministic Mock LLM Provider for unit tests, offline evaluation,
    and testing the agent loop without an external API.
    """

    def __init__(self, scripted_responses: Optional[List[LLMResponse]] = None):
        self.scripted_responses: List[LLMResponse] = list(scripted_responses or [])
        self.call_history: List[List[LLMMessage]] = []

    def add_response(self, response: LLMResponse) -> None:
        self.scripted_responses.append(response)

    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        self.call_history.append(messages)

        # 1. If user provided explicit scripted responses, consume the next one
        if self.scripted_responses:
            return self.scripted_responses.pop(0)

        # 2. Otherwise, use deterministic mock behavior
        last_msg = messages[-1] if messages else None

        # If last message was a tool result, generate an assistant summary
        if last_msg and last_msg.role == "tool":
            tool_name = last_msg.name or "tool"
            tool_content = last_msg.content or ""
            return LLMResponse(
                content=f"I have processed your request with {tool_name}. Details: {tool_content}",
                input_tokens=150,
                output_tokens=35,
                latency_ms=12.0,
            )

        # If user message, inspect the text
        user_text = ""
        for m in reversed(messages):
            if m.role == "user" and m.content:
                user_text = m.content
                break

        # Extract order ID and email if present
        order_match = re.search(r"ORD-\d{5}", user_text, re.IGNORECASE)
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", user_text)
        order_id = order_match.group(0).upper() if order_match else None
        email = email_match.group(0).lower() if email_match else None

        lower_text = user_text.lower()

        # Check for injection attempts
        if any(
            kw in lower_text
            for kw in ["ignore previous", "act as admin", "system prompt", "you are now"]
        ):
            return LLMResponse(
                content="I cannot comply with requests to alter system policies or bypass security guardrails. How may I assist you with your store order?",
                input_tokens=120,
                output_tokens=25,
                latency_ms=8.0,
            )

        # Check for explicit human / agent escalation request
        if any(
            kw in lower_text for kw in ["human", "agent", "supervisor", "representative", "manager"]
        ):
            return LLMResponse(
                tool_calls=[
                    LLMToolCall(
                        id="call_esc_1",
                        name="escalate_to_human",
                        arguments={
                            "reason": "Customer explicitly requested a human representative.",
                            "summary": user_text,
                        },
                    )
                ],
                input_tokens=140,
                output_tokens=30,
                latency_ms=15.0,
            )

        # Check for policy inquiries
        if any(
            kw in lower_text
            for kw in ["policy", "return window", "shipping", "warranty", "how many days"]
        ):
            return LLMResponse(
                tool_calls=[
                    LLMToolCall(
                        id="call_search_1",
                        name="search_policy",
                        arguments={"query": user_text[:100]},
                    )
                ],
                input_tokens=130,
                output_tokens=25,
                latency_ms=10.0,
            )

        # Check for refund intent
        if any(kw in lower_text for kw in ["refund", "return", "money back"]):
            if not order_id or not email:
                missing = []
                if not order_id:
                    missing.append("order ID (e.g. ORD-10001)")
                if not email:
                    missing.append("registered email address")
                return LLMResponse(
                    content=f"I would be glad to help you with your refund request. Please provide your {' and '.join(missing)} so I can check your order eligibility.",
                    input_tokens=110,
                    output_tokens=35,
                    latency_ms=10.0,
                )

            # If user already says confirm/proceed with refund
            if any(
                kw in lower_text
                for kw in ["please refund", "create refund", "submit refund", "want a refund"]
            ):
                return LLMResponse(
                    tool_calls=[
                        LLMToolCall(
                            id="call_ref_1",
                            name="check_refund_eligibility",
                            arguments={"order_id": order_id, "customer_email": email},
                        )
                    ],
                    input_tokens=150,
                    output_tokens=35,
                    latency_ms=15.0,
                )
            else:
                return LLMResponse(
                    tool_calls=[
                        LLMToolCall(
                            id="call_elig_1",
                            name="check_refund_eligibility",
                            arguments={"order_id": order_id, "customer_email": email},
                        )
                    ],
                    input_tokens=140,
                    output_tokens=30,
                    latency_ms=15.0,
                )

        # Check for order status inquiry
        if any(kw in lower_text for kw in ["order", "status", "track", "delivery", "where is"]):
            if not order_id or not email:
                missing = []
                if not order_id:
                    missing.append("order ID (e.g. ORD-10001)")
                if not email:
                    missing.append("email address")
                return LLMResponse(
                    content=f"To check your order status, please provide your {' and '.join(missing)}.",
                    input_tokens=100,
                    output_tokens=25,
                    latency_ms=10.0,
                )
            return LLMResponse(
                tool_calls=[
                    LLMToolCall(
                        id="call_status_1",
                        name="get_order_status",
                        arguments={"order_id": order_id, "customer_email": email},
                    )
                ],
                input_tokens=140,
                output_tokens=30,
                latency_ms=14.0,
            )

        # Check for ticket creation inquiry
        if any(
            kw in lower_text
            for kw in ["ticket", "complaint", "broken", "issue", "defective", "damaged"]
        ):
            if not email:
                return LLMResponse(
                    content="I'm sorry to hear that. Could you please provide your email address so I can create a support ticket for our technical team?",
                    input_tokens=110,
                    output_tokens=30,
                    latency_ms=10.0,
                )
            return LLMResponse(
                tool_calls=[
                    LLMToolCall(
                        id="call_tck_1",
                        name="create_support_ticket",
                        arguments={
                            "customer_email": email,
                            "category": "product_issue",
                            "priority": "medium",
                            "summary": user_text[:200],
                        },
                    )
                ],
                input_tokens=150,
                output_tokens=35,
                latency_ms=15.0,
            )

        # Check for out-of-scope requests
        if any(
            kw in lower_text
            for kw in ["recipe", "homework", "python code", "write a poem", "capital of", "weather"]
        ):
            return LLMResponse(
                content="I am the customer support assistant for ShopAssist Electronics. I can only assist with store orders, product returns, warranty policies, and support tickets.",
                input_tokens=90,
                output_tokens=30,
                latency_ms=8.0,
            )

        # Default fallback
        return LLMResponse(
            content="Hello! I am your ShopAssist customer support assistant. How can I assist you with your electronics order or our store policies today?",
            input_tokens=80,
            output_tokens=25,
            latency_ms=8.0,
        )
