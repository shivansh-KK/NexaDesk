from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LLMToolCall(BaseModel):
    id: str = Field(default="")
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class LLMMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[LLMToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # tool name if role == "tool"


class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[LLMToolCall] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: Optional[Any] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Generate a response given a list of messages and optional tool definitions."""
        pass
