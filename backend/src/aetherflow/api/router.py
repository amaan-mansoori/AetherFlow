"""Versioned API router composition."""

from fastapi import APIRouter

from aetherflow.api.health import router as health_router
from aetherflow.api.v1.admin import router as admin_router
from aetherflow.api.v1.api_keys import router as api_keys_router
from aetherflow.api.v1.auth import router as auth_router
from aetherflow.api.v1.jobs import router as jobs_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(api_keys_router)
router.include_router(admin_router)
router.include_router(jobs_router)
