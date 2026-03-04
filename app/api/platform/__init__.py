from __future__ import annotations

from fastapi import APIRouter

from .assistants import router as assistants_router
from .audit import router as audit_router
from .projects import router as projects_router
from .tenants import router as tenants_router


router = APIRouter(prefix="/_platform", tags=["platform"])
router.include_router(tenants_router)
router.include_router(projects_router)
router.include_router(assistants_router)
router.include_router(audit_router)
