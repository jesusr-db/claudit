from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SessionSummary(BaseModel):
    session_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    event_count: int = 0
    prompt_count: int = 0
    total_cost_usd: float = 0.0
    tool_calls: int = 0
    errors: int = 0
