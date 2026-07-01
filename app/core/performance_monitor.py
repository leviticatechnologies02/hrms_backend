# -*- coding: utf-8 -*-
"""
Advanced Performance Monitoring System
Tracks detailed system performance and health metrics.

Storage strategy (Render-compatible):
  1. Primary:  Redis  – survives restarts, shared across workers
  2. Fallback: In-memory dict – works when Redis is unavailable
  Local JSON files are NOT used (Render has an ephemeral filesystem).
"""

import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from .metrics import metrics_collector

logger = logging.getLogger(__name__)

try:
    import psutil
    # Test that psutil works
    _ = psutil.cpu_percent(interval=0)
    _ = psutil.virtual_memory()
    PSUTIL_AVAILABLE = True
except Exception:
    # Silently disable if psutil doesn't work (common with uvicorn --reload)
    PSUTIL_AVAILABLE = False
    psutil = None


# ─── Redis helpers ─────────────────────────────────────────────────────────────

def _get_redis():
    """Lazy import to avoid circular dependency at module load time."""
    try:
        from .redis_client import redis_client
        return redis_client.get_client()
    except Exception:
        return None


_REDIS_PERF_KEY = "hrms:performance"
_REDIS_TTL = 60 * 60 * 48  # 48 hours


# ─── In-memory fallback ────────────────────────────────────────────────────────

def _default_performance_data() -> Dict[str, Any]:
    return {
        "cpu_usage_history": [],
        "memory_usage_history": [],
        "response_times": [],
        "error_rates": [],
        "peak_usage": {
            "cpu_peak": 0.0,
            "memory_peak": 0.0,
            "slowest_response": 0.0,
        },
        "health_score": 100.0,
        "last_updated": datetime.now().isoformat(),
    }


_in_memory_perf: Dict[str, Any] = _default_performance_data()


# ─── Load / save helpers ───────────────────────────────────────────────────────

def _load_performance_data() -> Dict[str, Any]:
    """Load performance data from Redis, fall back to in-memory."""
    redis = _get_redis()
    if redis:
        try:
            raw = redis.get(_REDIS_PERF_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis perf read failed, using in-memory: {e}")
    return dict(_in_memory_perf)


def _save_performance_data(data: Dict[str, Any]) -> None:
    """Persist performance data to Redis; also update in-memory fallback."""
    global _in_memory_perf
    _in_memory_perf = dict(data)

    redis = _get_redis()
    if redis:
        try:
            redis.set(_REDIS_PERF_KEY, json.dumps(data), ex=_REDIS_TTL)
        except Exception as e:
            logger.warning(f"Redis perf write failed, using in-memory only: {e}")


# ─── PerformanceMonitor ────────────────────────────────────────────────────────

class PerformanceMonitor:
    """Advanced performance monitoring for HRMS system (Redis-backed, in-memory fallback)."""

    def __init__(self):
        self.monitoring_active = False
        self.monitor_thread = None

        # Ensure initial data exists
        existing = _load_performance_data()
        if not existing.get("peak_usage"):
            _save_performance_data(_default_performance_data())

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start_monitoring(self):
        """Start background performance monitoring."""
        if not self.monitoring_active and PSUTIL_AVAILABLE:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True, name="perf-monitor"
            )
            self.monitor_thread.start()
            logger.info("[OK] Performance monitoring started")
        elif not PSUTIL_AVAILABLE:
            logger.info("[INFO] psutil unavailable – performance monitoring skipped")

    def stop_monitoring(self):
        """Stop background performance monitoring."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("[STOP] Performance monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                self._collect_system_metrics()
                time.sleep(30)  # Collect metrics every 30 seconds
            except Exception as e:
                logger.debug(f"Performance monitoring error: {e}")
                time.sleep(60)  # Wait longer on error

    def _collect_system_metrics(self):
        """Collect current system performance metrics."""
        if not PSUTIL_AVAILABLE:
            return

        try:
            data = _load_performance_data()
            current_time = datetime.now().isoformat()

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Update history (keep last 100 readings)
            data["cpu_usage_history"].append({"timestamp": current_time, "value": cpu_percent})
            data["memory_usage_history"].append({"timestamp": current_time, "value": memory_percent})

            data["cpu_usage_history"] = data["cpu_usage_history"][-100:]
            data["memory_usage_history"] = data["memory_usage_history"][-100:]

            # Update peak values
            data["peak_usage"]["cpu_peak"] = max(data["peak_usage"]["cpu_peak"], cpu_percent)
            data["peak_usage"]["memory_peak"] = max(data["peak_usage"]["memory_peak"], memory_percent)

            data["health_score"] = self._calculate_health_score(data)
            data["last_updated"] = current_time

            _save_performance_data(data)
        except Exception as e:
            logger.debug(f"Error collecting system metrics: {e}")

    # ── Write helpers ──────────────────────────────────────────────────────────

    def log_response_time(self, response_time_ms: float):
        """Log API response time."""
        try:
            data = _load_performance_data()
            current_time = datetime.now().isoformat()

            data["response_times"].append({"timestamp": current_time, "value": response_time_ms})

            # Keep only last 1000 response times
            data["response_times"] = data["response_times"][-1000:]

            data["peak_usage"]["slowest_response"] = max(
                data["peak_usage"]["slowest_response"], response_time_ms
            )

            _save_performance_data(data)
        except Exception as e:
            logger.debug(f"Error logging response time: {e}")

    def log_error(self, error_type: str = "general"):
        """Log system error for error rate calculation."""
        try:
            data = _load_performance_data()
            current_time = datetime.now().isoformat()

            data["error_rates"].append({"timestamp": current_time, "type": error_type})
            data["error_rates"] = data["error_rates"][-500:]

            _save_performance_data(data)
        except Exception as e:
            logger.debug(f"Error logging error: {e}")

    # ── Read helpers ───────────────────────────────────────────────────────────

    def _calculate_health_score(self, data: Dict[str, Any]) -> float:
        """Calculate overall system health score."""
        try:
            base_score = 100.0

            # CPU usage penalty (recent average)
            cpu_history = data.get("cpu_usage_history", [])
            if cpu_history:
                recent_cpu = [e["value"] for e in cpu_history[-10:]]
                avg_cpu = sum(recent_cpu) / len(recent_cpu)
                if avg_cpu > 80:
                    base_score -= (avg_cpu - 80) * 0.5

            # Memory usage penalty
            memory_history = data.get("memory_usage_history", [])
            if memory_history:
                recent_memory = [e["value"] for e in memory_history[-10:]]
                avg_memory = sum(recent_memory) / len(recent_memory)
                if avg_memory > 85:
                    base_score -= (avg_memory - 85) * 0.3

            # Response time penalty
            response_times = data.get("response_times", [])
            if response_times:
                recent_responses = [e["value"] for e in response_times[-50:]]
                avg_response = sum(recent_responses) / len(recent_responses)
                if avg_response > 1000:
                    base_score -= min(20, (avg_response - 1000) / 100)

            # Error rate penalty
            error_rates = data.get("error_rates", [])
            recent_errors = [
                e for e in error_rates
                if datetime.fromisoformat(e["timestamp"]) > datetime.now() - timedelta(hours=1)
            ]
            if len(recent_errors) > 10:
                base_score -= min(30, len(recent_errors) - 10)

            return max(0.0, min(100.0, base_score))
        except Exception as e:
            logger.debug(f"Error calculating health score: {e}")
            return 85.0

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        try:
            data = _load_performance_data()

            cpu_history = data.get("cpu_usage_history", [])
            memory_history = data.get("memory_usage_history", [])
            response_times = data.get("response_times", [])

            avg_cpu = 0.0
            avg_memory = 0.0
            avg_response = 0.0

            if cpu_history:
                recent_cpu = [e["value"] for e in cpu_history[-20:]]
                avg_cpu = sum(recent_cpu) / len(recent_cpu)

            if memory_history:
                recent_memory = [e["value"] for e in memory_history[-20:]]
                avg_memory = sum(recent_memory) / len(recent_memory)

            if response_times:
                recent_responses = [e["value"] for e in response_times[-100:]]
                avg_response = sum(recent_responses) / len(recent_responses)

            return {
                "health_score": data.get("health_score", 100.0),
                "avg_cpu_usage": round(avg_cpu, 1),
                "avg_memory_usage": round(avg_memory, 1),
                "avg_response_time": round(avg_response, 1),
                "peak_cpu": data.get("peak_usage", {}).get("cpu_peak", 0.0),
                "peak_memory": data.get("peak_usage", {}).get("memory_peak", 0.0),
                "slowest_response": data.get("peak_usage", {}).get("slowest_response", 0.0),
                "total_errors_today": len([
                    e for e in data.get("error_rates", [])
                    if datetime.fromisoformat(e["timestamp"]).date() == datetime.now().date()
                ]),
                "monitoring_active": self.monitoring_active,
            }
        except Exception as e:
            logger.debug(f"Error getting performance summary: {e}")
            return {
                "health_score": 85.0,
                "avg_cpu_usage": 0.0,
                "avg_memory_usage": 0.0,
                "avg_response_time": 0.0,
                "peak_cpu": 0.0,
                "peak_memory": 0.0,
                "slowest_response": 0.0,
                "total_errors_today": 0,
                "monitoring_active": False,
            }


# Global performance monitor instance
performance_monitor = PerformanceMonitor()