"""路由注册 — 聚合所有子路由"""

from fastapi import APIRouter

from .system import router as system_router
from .audit import router as audit_router
from .catalog import router as catalog_router
from .rules import router as rules_router
from .icd import router as icd_router
from .sandbox import router as sandbox_router
from .chat import router as chat_router
from .agent import router as agent_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(audit_router)
api_router.include_router(catalog_router)
api_router.include_router(rules_router)
api_router.include_router(icd_router)
api_router.include_router(sandbox_router)
api_router.include_router(chat_router)
api_router.include_router(agent_router)
