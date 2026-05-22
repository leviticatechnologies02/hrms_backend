"""                                  
System Statistics API
Provides real-time backend architecture statistics
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.utils.backend_analyzer import get_backend_stats, get_cached_stats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/backend-stats", response_model=Dict[str, Any])
async def get_backend_statistics():
    """
    Get comprehensive backend architecture statistics
    
    **Returns:**
    - Real-time analysis of models, endpoints, services, repositories
    - Module breakdown and categorization
    - Total counts for dashboard display
    """
    try:
        logger.info("📊 Fetching backend statistics...")
        stats = get_backend_stats()
        
        return {
            "success": True,
            "message": "Backend statistics retrieved successfully",
            "data": stats,
            "timestamp": stats.get("last_updated")
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get backend statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze backend: {str(e)}"
        )


@router.get("/backend-stats/cached", response_model=Dict[str, Any])
async def get_cached_backend_statistics():
    """
    Get cached backend architecture statistics (faster response)
    
    **Returns:**
    - Cached analysis of backend components
    - Suitable for frequent dashboard updates
    """
    try:
        stats = get_cached_stats()
        
        return {
            "success": True,
            "message": "Cached backend statistics retrieved successfully",
            "data": stats,
            "timestamp": stats.get("last_updated"),
            "cached": True
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get cached backend statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cached stats: {str(e)}"
        )


@router.get("/backend-stats/summary", response_model=Dict[str, Any])
async def get_backend_summary():
    """
    Get summary statistics for dashboard display
    
    **Returns:**
    - Key metrics only (models, endpoints, services, repositories)
    - Optimized for landing page display
    """
    try:
        stats = get_cached_stats()
        total_counts = stats.get("total_counts", {})
        
        summary = {
            "models": {
                "count": total_counts.get("models", 0),
                "description": "Comprehensive data models across core domains"
            },
            "endpoints": {
                "count": total_counts.get("endpoints", 0),
                "description": "RESTful endpoints with comprehensive validation"
            },
            "services_and_repositories": {
                "count": total_counts.get("services_and_repos", 0),
                "description": "Business logic and data access layers"
            },
            "core_modules": {
                "count": total_counts.get("core_modules", 0),
                "description": "Modular architecture for scalability"
            },
            "last_updated": stats.get("last_updated"),
            "analysis_available": bool(stats.get("last_updated"))
        }
        
        return {
            "success": True,
            "message": "Backend summary retrieved successfully",
            "data": summary
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get backend summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get summary: {str(e)}"
        )


@router.post("/backend-stats/refresh")
async def refresh_backend_statistics():
    """
    Force refresh of backend statistics
    
    **Returns:**
    - Newly analyzed backend statistics
    - Use when backend structure has changed
    """
    try:
        logger.info("🔄 Force refreshing backend statistics...")
        stats = get_backend_stats()  # Force fresh analysis
        
        return {
            "success": True,
            "message": "Backend statistics refreshed successfully",
            "data": stats,
            "timestamp": stats.get("last_updated"),
            "refreshed": True
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to refresh backend statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh stats: {str(e)}"
        )