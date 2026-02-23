from datetime import datetime
from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel


class EventName(str, Enum):
    USER_PROMPT = "user_prompt"
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    TOOL_DECISION = "tool_decision"
    TOOL_RESULT = "tool_result"


class OtelLogEvent(BaseModel):
    """Parsed event from otel_logs table."""
    event_name: EventName
    timestamp: str
    sequence: int
    session_id: str
    prompt_id: Optional[str] = None
    user_id: Optional[str] = None
    terminal_type: Optional[str] = None

    # user_prompt fields
    prompt: Optional[str] = None
    prompt_length: Optional[int] = None

    # api_request fields
    model: Optional[str] = None
    duration_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    speed: Optional[str] = None

    # api_error fields
    error: Optional[str] = None
    status_code: Optional[str] = None
    attempt: Optional[int] = None

    # tool_decision fields
    tool_name: Optional[str] = None
    decision: Optional[str] = None
    source: Optional[str] = None

    # tool_result fields
    success: Optional[bool] = None
    tool_parameters: Optional[str] = None
    tool_result_size_bytes: Optional[int] = None

    # Raw attributes for anything not explicitly modeled
    raw_attributes: Optional[Dict[str, str]] = None

    @classmethod
    def from_row(cls, row: dict) -> "OtelLogEvent":
        """Parse a raw otel_logs row (with attributes as a dict)."""
        attrs = row.get("attributes", {})

        def _int(key: str) -> Optional[int]:
            v = attrs.get(key)
            return int(v) if v is not None else None

        def _float(key: str) -> Optional[float]:
            v = attrs.get(key)
            return float(v) if v is not None else None

        def _bool(key: str) -> Optional[bool]:
            v = attrs.get(key)
            if v is None:
                return None
            return v.lower() == "true" if isinstance(v, str) else bool(v)

        return cls(
            event_name=EventName(attrs.get("event.name", "")),
            timestamp=attrs.get("event.timestamp", ""),
            sequence=int(attrs.get("event.sequence", 0)),
            session_id=attrs.get("session.id", ""),
            prompt_id=attrs.get("prompt.id"),
            user_id=attrs.get("user.id"),
            terminal_type=attrs.get("terminal.type"),
            # user_prompt
            prompt=attrs.get("prompt"),
            prompt_length=_int("prompt_length"),
            # api_request / api_error
            model=attrs.get("model"),
            duration_ms=_int("duration_ms"),
            cost_usd=_float("cost_usd"),
            input_tokens=_int("input_tokens"),
            output_tokens=_int("output_tokens"),
            cache_read_tokens=_int("cache_read_tokens"),
            cache_creation_tokens=_int("cache_creation_tokens"),
            speed=attrs.get("speed"),
            error=attrs.get("error"),
            status_code=attrs.get("status_code"),
            attempt=_int("attempt"),
            # tool_decision / tool_result
            tool_name=attrs.get("tool_name"),
            decision=attrs.get("decision"),
            source=attrs.get("source"),
            success=_bool("success"),
            tool_parameters=attrs.get("tool_parameters"),
            tool_result_size_bytes=_int("tool_result_size_bytes"),
            raw_attributes=attrs,
        )

    @property
    def is_mcp_tool(self) -> bool:
        """MCP tools have names starting with 'mcp__'."""
        return self.tool_name.startswith("mcp__") if self.tool_name else False

    @property
    def mcp_server(self) -> Optional[str]:
        """Extract MCP server name from tool_name like 'mcp__glean__search'."""
        if self.is_mcp_tool and self.tool_name:
            parts = self.tool_name.split("__")
            return parts[1] if len(parts) >= 2 else None
        return None
