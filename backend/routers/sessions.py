from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from backend.config import settings
from backend.services.query_service import QueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("")
async def list_sessions(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = query_service.build_sessions_list_query(
        limit=limit, offset=offset, user_id=user_id
    )
    rows = get_executor().execute(query)
    return {"sessions": rows}


@router.get("/{session_id}")
async def get_session(session_id: str):
    query = query_service.build_session_detail_query(session_id=session_id)
    rows = get_executor().execute(query)
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return rows[0]


@router.get("/{session_id}/timeline")
async def get_session_timeline(
    session_id: str,
    event_names: Optional[List[str]] = Query(None),
):
    query = query_service.build_session_timeline_query(
        session_id=session_id, event_names=event_names
    )
    rows = get_executor().execute(query)
    return {"session_id": session_id, "events": rows}


@router.get("/{session_id}/prompts/{prompt_id}")
async def get_prompt_events(session_id: str, prompt_id: str):
    query = query_service.build_prompt_events_query(
        session_id=session_id, prompt_id=prompt_id
    )
    rows = get_executor().execute(query)
    return {"session_id": session_id, "prompt_id": prompt_id, "events": rows}
