from typing import Optional
from pydantic import BaseModel


class TokenUsage(BaseModel):
    session_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


class CostUsage(BaseModel):
    session_id: str
    model: str
    cost_usd: float = 0.0
