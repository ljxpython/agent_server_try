from __future__ import annotations

from fastapi import APIRouter

from app.api.langgraph.assistants import router as assistants_router
from app.api.langgraph.runs import router as runs_router
from app.api.langgraph.threads import router as threads_router

router = APIRouter(prefix="/api/langgraph", tags=["langgraph-sdk"])
router.include_router(assistants_router)
router.include_router(threads_router)
router.include_router(runs_router)
