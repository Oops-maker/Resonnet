"""Libs admin API: cache invalidation for hot-reload."""

from fastapi import APIRouter

from app.core.libs_service import invalidate_libs_cache

router = APIRouter()


@router.post("/invalidate-cache")
def invalidate_cache():
    """Clear libs meta cache. Call after updating libs/ (skills, mcps, moderator_modes) for immediate refresh."""
    invalidate_libs_cache()
    return {"message": "Libs cache invalidated"}
