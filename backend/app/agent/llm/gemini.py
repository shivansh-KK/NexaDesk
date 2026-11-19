import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.agent.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def _convert_schema_to_gemini(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and map JSON schema types to Gemini OpenAPI types."""
        cleaned = dict(schema)
        # Gemini expects uppercase types
        type_mapping = {
            "string": "STRING",
            "integer": "INTEGER",
            "number": "NUMBER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }
        if "type" in cleaned and isinstance(cleaned["type"], str):
            cleaned["type"] = type_mapping.get(cleaned["type"].lower(), cleaned["type"].upper())
        if "properties" in cleaned and isinstance(cleaned["properties"], dict):
            new_props = {}
            for k, v in cleaned["properties"].items():
                if isinstance(v, dict):
                    new_props[k] = self._convert_schema_to_gemini(v)
                else:
                    new_props[k] = v
            cleaned["properties"] = new_props
        if "items" in cleaned and isinstance(cleaned["items"], dict):
            cleaned["items"] = self._convert_schema_to_gemini(cleaned["items"])
        # Remove unsupported keys
        cleaned.pop("title", None)
        cleaned.pop("$defs", None)
        return cleaned

    def _build_tools(self, tools: List[Dict[str, Any]]) -> List[types.Tool]:
        declarations = []
        for t in tools:
            params = self._convert_schema_to_gemini(
                t.get("parameters", {"type": "OBJECT", "properties": {}})
            )
            decl = types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=params,
            )
            declarations.append(decl)
        return [types.Tool(function_declarations=declarations)]

    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self.client:
            raise ValueError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in .env or pass api_key."
            )

        system_instruction = None
        contents: List[types.Content] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg.content or "")],
                    )
                )
            elif msg.role == "assistant":
                parts = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(
                            types.Part.from_function_call(
                                name=tc.name,
                                args=tc.arguments,
                            )
                        )
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                # Function response
                resp_payload = {"result": msg.content}
                try:
                    resp_payload = json.loads(msg.content or "{}")
                except Exception:
                    pass
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=msg.name or "tool_result",
                                response=resp_payload,
                            )
                        ],
                    )
                )

        gemini_tools = self._build_tools(tools) if tools else None

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
            temperature=0.0,  # deterministic output for evaluation and support
        )

        # Retry with exponential backoff on transient errors
        start_time = time.time()
        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                latency_ms = (time.time() - start_time) * 1000.0

                # Parse response
                tool_calls: List[LLMToolCall] = []
                text_content = ""

                if response.candidates and response.candidates[0].content:
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            text_content += part.text
                        if part.function_call:
                            tool_calls.append(
                                LLMToolCall(
                                    id=f"call_{part.function_call.name}_{int(time.time()*1000)}",
                                    name=part.function_call.name,
                                    arguments=(
                                        dict(part.function_call.args)
                                        if part.function_call.args
                                        else {}
                                    ),
                                )
                            )

                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = (
                        getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                    )

                return LLMResponse(
                    content=text_content if text_content else None,
                    tool_calls=tool_calls,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    raw_response=response,
                )

            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2.0
