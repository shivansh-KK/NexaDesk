import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent.guardrails import (
    check_hallucinations,
    create_pending_action,
    detect_abusive_language,
    detect_prompt_injection,
)
from app.agent.llm.base import LLMMessage, LLMProvider, LLMResponse
from app.agent.llm.gemini import GeminiProvider
from app.agent.llm.mock import MockProvider
from app.agent.llm.ollama import OllamaProvider
from app.agent.prompts import get_system_prompt
from app.config import settings
from app.tools.registry import WRITE_TOOLS, execute_tool, get_tool_schemas
from app.tracing import get_session_traces, log_trace

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    reply: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    pending_action: Optional[Dict[str, Any]] = None
    escalated: bool = False


def get_default_provider(provider_name: Optional[str] = None) -> LLMProvider:
    name = (provider_name or settings.DEFAULT_PROVIDER).lower()
    if name == "mock":
        return MockProvider()
    elif name == "ollama":
        return OllamaProvider()
    else:
        return GeminiProvider()


async def run_agent_turn(
    session_id: str,
    user_message: str,
    db: Session,
    provider: Optional[LLMProvider] = None,
    guardrails_enabled: Optional[bool] = None,
    prompt_version: Optional[str] = None,
) -> AgentResult:
    """Execute a single multi-turn interaction loop for the user message."""
    llm = provider or get_default_provider()
    use_guardrails = (
        settings.GUARDRAILS_ENABLED if guardrails_enabled is None else guardrails_enabled
    )
    version = prompt_version or settings.PROMPT_VERSION

    # Fetch existing session traces to determine current turn index
    traces = get_session_traces(db, session_id)
    turn_index = len(traces) + 1

    # Log user turn in traces
    log_trace(
        db=db,
        session_id=session_id,
        turn=turn_index,
        role="user",
        content=user_message,
    )

    # 1. Guardrail: Prompt Injection Detection
    if use_guardrails and detect_prompt_injection(user_message):
        refusal_msg = (
            "I cannot comply with requests to alter system policies or bypass security guardrails. "
            "How may I assist you with your store order?"
        )
        log_trace(
            db=db,
            session_id=session_id,
            turn=turn_index + 1,
            role="assistant",
            content=refusal_msg,
            guardrail_flags="injection_detected",
        )
        return AgentResult(reply=refusal_msg, tool_calls=[], pending_action=None, escalated=False)

    # 2. Guardrail: Abusive Language / Hostility Escalation
    if use_guardrails and detect_abusive_language(user_message):
        execute_tool(
            "escalate_to_human",
            {"reason": "Abusive or threatening language detected", "summary": user_message},
            db,
            session_id=session_id,
        )
        esc_msg = "Your message has been escalated to a supervisor due to company policy. An agent will follow up shortly."
        log_trace(
            db=db,
            session_id=session_id,
            turn=turn_index + 1,
            role="assistant",
            content=esc_msg,
            guardrail_flags="abusive_escalated",
        )
        return AgentResult(reply=esc_msg, tool_calls=[], pending_action=None, escalated=True)

    # Build conversation messages for the LLM
    system_text = get_system_prompt(version)
    messages: List[LLMMessage] = [LLMMessage(role="system", content=system_text)]

    for t in traces:
        if t.role in ("user", "assistant"):
            messages.append(LLMMessage(role=t.role, content=t.content))
        elif t.role == "tool":
            messages.append(
                LLMMessage(
                    role="tool",
                    name=t.tool_name,
                    content=t.tool_result,
                )
            )

    messages.append(LLMMessage(role="user", content=user_message))

    # Agent tool calling loop (up to MAX_TOOL_STEPS)
    tool_schemas = get_tool_schemas()
    executed_tool_calls: List[Dict[str, Any]] = []
    is_escalated = False
    step = 0
    max_steps = settings.MAX_TOOL_STEPS

    while step < max_steps:
        step += 1

        response: LLMResponse = await llm.generate(messages, tools=tool_schemas)

        # Log assistant raw LLM turn
        log_trace(
            db=db,
            session_id=session_id,
            turn=turn_index + step,
            role="assistant",
            content=response.content,
            latency_ms=response.latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        # If LLM did not call any tools, it is ready to reply to the user
        if not response.has_tool_calls:
            reply = response.content or ""

            # Check Hallucination Guard
            if use_guardrails and reply:
                is_hallucinating, fake_items = check_hallucinations(reply, session_id, db)
                if is_hallucinating:
                    logger.warning(f"Hallucination detected in session {session_id}: {fake_items}")
                    log_trace(
                        db=db,
                        session_id=session_id,
                        turn=turn_index + step,
                        role="system",
                        content=f"Hallucination blocked: unverified order references {fake_items}",
                        guardrail_flags="hallucination_detected",
                    )
                    reply = (
                        "I was unable to verify those order details with our backend system. "
                        "Could you please provide your order ID (format: ORD-XXXXX) and email so I can look up your verified order information?"
                    )

            return AgentResult(
                reply=reply,
                tool_calls=executed_tool_calls,
                pending_action=None,
                escalated=is_escalated,
            )

        # If tools were requested, process them
        # Append assistant message with its tool calls
        messages.append(
            LLMMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
        )

        for tc in response.tool_calls:
            tool_name = tc.name
            tool_args = tc.arguments

            # Check Confirmation Gate for WRITE actions
            if use_guardrails and tool_name in WRITE_TOOLS:
                pending = create_pending_action(
                    db=db,
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
                pending_dict = {
                    "action_id": pending.id,
                    "action_type": pending.action_type,
                    "tool_name": pending.tool_name,
                    "tool_args": tool_args,
                    "summary": pending.summary,
                    "expires_at": pending.expires_at.isoformat(),
                }
                gate_reply = (
                    f"To proceed, please confirm the following action:\n\n{pending.summary}\n\n"
                    "Would you like me to submit this request?"
                )
                log_trace(
                    db=db,
                    session_id=session_id,
                    turn=turn_index + step,
                    role="assistant",
                    content=gate_reply,
                    guardrail_flags="confirmation_pending",
                )
                return AgentResult(
                    reply=gate_reply,
                    tool_calls=executed_tool_calls,
                    pending_action=pending_dict,
                    escalated=is_escalated,
                )

            # Otherwise, execute the tool
            tool_result = execute_tool(
                name=tool_name,
                raw_args=tool_args,
                db=db,
                session_id=session_id,
            )

            if tool_name == "escalate_to_human" or (
                tool_result.data and tool_result.data.get("escalated")
            ):
                is_escalated = True

            executed_tool_calls.append(
                {
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "result": tool_result.to_dict(),
                }
            )

            # Log tool execution to traces
            log_trace(
                db=db,
                session_id=session_id,
                turn=turn_index + step,
                role="tool",
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result.to_dict(),
                error=tool_result.error_code,
            )

            # Append tool result to messages for next LLM iteration
            messages.append(
                LLMMessage(
                    role="tool",
                    name=tool_name,
                    content=json.dumps(tool_result.to_dict()),
                    tool_call_id=tc.id,
                )
            )

    # Exceeded MAX_TOOL_STEPS -> safe fallback and escalation
    execute_tool(
        "escalate_to_human",
        {
            "reason": "Exceeded maximum tool execution steps",
            "summary": f"Turn loop reached {max_steps} steps without resolution",
        },
        db,
        session_id=session_id,
    )
    fallback_reply = (
        "I apologize, but I am having trouble completing this request automatically. "
        "I have escalated this conversation to a human supervisor who will follow up with you shortly."
    )
    log_trace(
        db=db,
        session_id=session_id,
        turn=turn_index + max_steps,
        role="assistant",
        content=fallback_reply,
        guardrail_flags="max_steps_escalated",
    )
    return AgentResult(
        reply=fallback_reply,
        tool_calls=executed_tool_calls,
        pending_action=None,
        escalated=True,
    )
