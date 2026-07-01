# -*- coding: utf-8 -*-
"""
Real-time Metrics Collection System
Tracks actual system performance and usage data.

Storage strategy (Render-compatible):
  1. Primary:  Redis  – survives restarts, shared across workers
  2. Fallback: In-memory dict – works when Redis is unavailable
  Local JSON files are NOT used (Render has an ephemeral filesystem).
"""

import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import text
from .database import get_db

logger = logging.getLogger(__name__)

# Optional psutil import for system metrics
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.info("psutil not available - system metrics will use fallbacks")


# ─── Redis helpers ─────────────────────────────────────────────────────────────

def _get_redis():
    """Lazy import to avoid circular dependency at module load time."""
    try:
        from .redis_client import redis_client
        return redis_client.get_client()
    except Exception:
        return None


_REDIS_METRICS_KEY = "hrms:metrics"
_REDIS_TTL = 60 * 60 * 48  # 48 hours – reset if server is cold for 2 days


# ─── In-memory fallback ────────────────────────────────────────────────────────

def _default_metrics() -> Dict[str, Any]:
    return {
        "app_start_time": time.time(),
        "api_calls_today": 0,
        "api_calls_total": 0,
        "data_processed_mb": 0.0,
        "last_reset_date": datetime.now().date().isoformat(),
        "security_events": {
            "failed_logins": 0,
            "successful_logins": 0,
            "blocked_requests": 0,
            "last_security_scan": None,
        },
        "database_operations": {
            "queries_today": 0,
            "inserts_today": 0,
            "updates_today": 0,
            "deletes_today": 0,
        },
    }


_in_memory_metrics: Dict[str, Any] = _default_metrics()


# ─── Load / save helpers ───────────────────────────────────────────────────────

def _load_metrics() -> Dict[str, Any]:
    """Load metrics from Redis, fall back to in-memory."""
    redis = _get_redis()
    if redis:
        try:
            raw = redis.get(_REDIS_METRICS_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis metrics read failed, using in-memory: {e}")
    return dict(_in_memory_metrics)


def _save_metrics(metrics: Dict[str, Any]) -> None:
    """Persist metrics to Redis; also update in-memory fallback."""
    global _in_memory_metrics
    _in_memory_metrics = dict(metrics)

    redis = _get_redis()
    if redis:
        try:
            redis.set(_REDIS_METRICS_KEY, json.dumps(metrics), ex=_REDIS_TTL)
        except Exception as e:
            logger.warning(f"Redis metrics write failed, using in-memory only: {e}")


def _reset_daily_metrics_if_needed(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Reset daily counters when the calendar day changes."""
    today = datetime.now().date().isoformat()
    if metrics.get("last_reset_date") != today:
        metrics["api_calls_today"] = 0
        metrics["data_processed_mb"] = 0.0
        metrics["last_reset_date"] = today
        metrics["database_operations"] = {
            "queries_today": 0,
            "inserts_today": 0,
            "updates_today": 0,
            "deletes_today": 0,
        }
        _save_metrics(metrics)
    return metrics


# ─── MetricsCollector ──────────────────────────────────────────────────────────

class MetricsCollector:
    """Collects and stores real system metrics (Redis-backed, in-memory fallback)."""

    def __init__(self):
        self.app_start_time = time.time()
        # Ensure an initial record exists
        m = _load_metrics()
        if "app_start_time" not in m:
            m["app_start_time"] = self.app_start_time
            _save_metrics(m)

    # ── Write helpers ──────────────────────────────────────────────────────────

    def log_api_call(self, endpoint: str = "", method: str = "GET"):
        """Log an API call."""
        try:
            metrics = _load_metrics()
            metrics = _reset_daily_metrics_if_needed(metrics)
            metrics["api_calls_today"] += 1
            metrics["api_calls_total"] += 1
            _save_metrics(metrics)
        except Exception as e:
            logger.debug(f"log_api_call error: {e}")

    def log_data_processed(self, size_mb: float):
        """Log data processing."""
        try:
            metrics = _load_metrics()
            metrics = _reset_daily_metrics_if_needed(metrics)
            metrics["data_processed_mb"] += size_mb
            _save_metrics(metrics)
        except Exception as e:
            logger.debug(f"log_data_processed error: {e}")

    def log_database_operation(self, operation_type: str):
        """Log database operations (query, insert, update, delete)."""
        try:
            metrics = _load_metrics()
            metrics = _reset_daily_metrics_if_needed(metrics)
            op = operation_type.lower()
            if op in ("select", "query"):
                metrics["database_operations"]["queries_today"] += 1
            elif op == "insert":
                metrics["database_operations"]["inserts_today"] += 1
            elif op == "update":
                metrics["database_operations"]["updates_today"] += 1
            elif op == "delete":
                metrics["database_operations"]["deletes_today"] += 1
            _save_metrics(metrics)
        except Exception as e:
            logger.debug(f"log_database_operation error: {e}")

    def log_security_event(self, event_type: str):
        """Log security events."""
        try:
            metrics = _load_metrics()
            if event_type == "failed_login":
                metrics["security_events"]["failed_logins"] += 1
            elif event_type == "successful_login":
                metrics["security_events"]["successful_logins"] += 1
            elif event_type == "blocked_request":
                metrics["security_events"]["blocked_requests"] += 1
            _save_metrics(metrics)
        except Exception as e:
            logger.debug(f"log_security_event error: {e}")

    # ── Read helpers ───────────────────────────────────────────────────────────

    def get_app_uptime_hours(self) -> float:
        """Get real application uptime in hours."""
        try:
            metrics = _load_metrics()
            start_time = metrics.get("app_start_time", self.app_start_time)
            return (time.time() - start_time) / 3600
        except Exception:
            return (time.time() - self.app_start_time) / 3600

    def get_system_uptime_hours(self) -> float:
        """Get system uptime in hours."""
        try:
            if PSUTIL_AVAILABLE and hasattr(psutil, "boot_time"):
                return (time.time() - psutil.boot_time()) / 3600
        except Exception:
            pass
        return self.get_app_uptime_hours()

    def get_api_calls_today(self) -> int:
        """Get real API calls count for today."""
        try:
            metrics = _load_metrics()
            metrics = _reset_daily_metrics_if_needed(metrics)
            return metrics.get("api_calls_today", 0)
        except Exception:
            return 0

    def get_data_processed_today(self) -> float:
        """Get real data processed today in MB."""
        try:
            metrics = _load_metrics()
            metrics = _reset_daily_metrics_if_needed(metrics)
            return metrics.get("data_processed_mb", 0.0)
        except Exception:
            return 0.0

    def calculate_security_score(self) -> float:
        """Calculate real security score based on actual events."""
        try:
            metrics = _load_metrics()
            security = metrics.get("security_events", {})

            base_score = 85.0
            total_logins = security.get("successful_logins", 0) + security.get("failed_logins", 0)
            if total_logins > 0:
                success_rate = security.get("successful_logins", 0) / total_logins
                login_score = success_rate * 10
            else:
                login_score = 5.0

            blocked_penalty = min(security.get("blocked_requests", 0) * 0.5, 15.0)
            monitoring_bonus = 5.0 if total_logins > 0 else 0.0

            final_score = base_score + login_score + monitoring_bonus - blocked_penalty
            return round(min(100.0, max(0.0, final_score)), 1)
        except Exception as e:
            logger.debug(f"calculate_security_score error: {e}")
            return 0.0

    def get_database_stats(self) -> Dict[str, int]:
        """Get real database operation statistics."""
        try:
            metrics = _load_metrics()
            metrics = _reset_daily_metrics_if_needed(metrics)

            # Also query real database size (best-effort)
            try:
                db = next(get_db())
                try:
                    db.execute(text(
                        "SELECT pg_size_pretty(pg_database_size(current_database()))"
                    ))
                    self.log_database_operation("query")
                finally:
                    db.close()
            except Exception as db_error:
                logger.debug(f"Database stats query error: {db_error}")

            return metrics["database_operations"]
        except Exception as e:
            logger.debug(f"get_database_stats error: {e}")
            return {"queries_today": 0, "inserts_today": 0, "updates_today": 0, "deletes_today": 0}


# Global metrics collector instance
metrics_collector = MetricsCollector()