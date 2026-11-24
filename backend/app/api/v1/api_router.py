"""API v1 master router aggregating all sub-routers."""

from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, interviews

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(interviews.router)
