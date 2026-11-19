import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.agent.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall
from app.config import settings

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        ollama_messages = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content or ""}
            if msg.role == "assistant" and msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            ollama_messages.append(m)

        ollama_tools = None
        if tools:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {}),
                    },
                }
                for t in tools
            ]

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": 0.0},
        }
        if ollama_tools:
            payload["tools"] = ollama_tools

        start_time = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.time() - start_time) * 1000.0
        msg_obj = data.get("message", {})
        content = msg_obj.get("content")

        tool_calls: List[LLMToolCall] = []
        raw_tool_calls = msg_obj.get("tool_calls", [])
        for i, tc in enumerate(raw_tool_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            tool_calls.append(
                LLMToolCall(
                    id=f"call_{fn.get('name', 'tool')}_{i}",
                    name=fn.get("name", ""),
                    arguments=args,
                )
            )

        prompt_eval_count = data.get("prompt_eval_count", 0) or 0
        eval_count = data.get("eval_count", 0) or 0

        return LLMResponse(
            content=content if content else None,
            tool_calls=tool_calls,
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            latency_ms=latency_ms,
            raw_response=data,
        )
