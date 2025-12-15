"""
Monitoring Service - Gathers system stats from Celery, Redis, MongoDB.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis
from celery import Celery
from pymongo.database import Database

from app.config import settings
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class MonitoringService:
    """Service to gather system monitoring stats."""

    def __init__(self, db: Database):
        self.db = db
        self._redis_client: Optional[redis.Redis] = None

    @property
    def redis_client(self) -> redis.Redis:
        if self._redis_client is None:
            self._redis_client = redis.from_url(settings.REDIS_URL)
        return self._redis_client

    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system stats."""
        return {
            "celery": self._get_celery_stats(),
            "redis": self._get_redis_stats(),
            "mongodb": self._get_mongodb_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_celery_stats(self) -> Dict[str, Any]:
        """Get Celery worker and queue stats."""
        try:
            inspect = celery_app.control.inspect(timeout=2.0)

            # Get active workers
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            stats = inspect.stats() or {}

            workers = []
            for worker_name, worker_stats in stats.items():
                active_tasks = len(active.get(worker_name, []))
                reserved_tasks = len(reserved.get(worker_name, []))

                workers.append(
                    {
                        "name": worker_name,
                        "status": "online",
                        "active_tasks": active_tasks,
                        "reserved_tasks": reserved_tasks,
                        "processed": worker_stats.get("total", {}).get("app.tasks", 0),
                        "pool": worker_stats.get("pool", {}).get("max-concurrency", 0),
                    }
                )

            # Get queue lengths from Redis
            queues = self._get_queue_lengths()

            return {
                "workers": workers,
                "worker_count": len(workers),
                "queues": queues,
                "status": "online" if workers else "offline",
            }
        except Exception as e:
            logger.error(f"Failed to get Celery stats: {e}")
            return {
                "workers": [],
                "worker_count": 0,
                "queues": {},
                "status": "error",
                "error": str(e),
            }

    def _get_queue_lengths(self) -> Dict[str, int]:
        """Get message count for each Celery queue."""
        queue_names = ["default", "ingestion", "processing", "sonar_scan", "trivy_scan"]
        queues = {}

        try:
            for queue_name in queue_names:
                # Celery uses Redis lists for queues
                length = self.redis_client.llen(queue_name)
                queues[queue_name] = length
        except Exception as e:
            logger.error(f"Failed to get queue lengths: {e}")

        return queues

    def _get_redis_stats(self) -> Dict[str, Any]:
        """Get Redis server stats."""
        try:
            info = self.redis_client.info()
            return {
                "connected": True,
                "version": info.get("redis_version", "unknown"),
                "memory_used": info.get("used_memory_human", "0B"),
                "memory_peak": info.get("used_memory_peak_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_days": info.get("uptime_in_days", 0),
                "total_commands": info.get("total_commands_processed", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return {
                "connected": False,
                "error": str(e),
            }

    def _get_mongodb_stats(self) -> Dict[str, Any]:
        """Get MongoDB server stats."""
        try:
            # Get server status
            server_status = self.db.command("serverStatus")

            # Get collection names
            collections = self.db.list_collection_names()

            return {
                "connected": True,
                "version": server_status.get("version", "unknown"),
                "uptime_seconds": server_status.get("uptime", 0),
                "connections": {
                    "current": server_status.get("connections", {}).get("current", 0),
                    "available": server_status.get("connections", {}).get(
                        "available", 0
                    ),
                },
                "collections": len(collections),
                "operations": {
                    "insert": server_status.get("opcounters", {}).get("insert", 0),
                    "query": server_status.get("opcounters", {}).get("query", 0),
                    "update": server_status.get("opcounters", {}).get("update", 0),
                    "delete": server_status.get("opcounters", {}).get("delete", 0),
                },
            }
        except Exception as e:
            logger.error(f"Failed to get MongoDB stats: {e}")
            return {
                "connected": False,
                "error": str(e),
            }

    def get_pipeline_runs(
        self,
        limit: int = 50,
        skip: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recent pipeline runs."""
        from app.repositories.pipeline_run import PipelineRunRepository

        repo = PipelineRunRepository(self.db)

        query = {}
        if status:
            query["status"] = status

        runs, total = repo.paginate(
            query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

        return {
            "runs": [
                {
                    "id": str(run.id),
                    "repo_id": str(run.repo_id),
                    "workflow_run_id": run.workflow_run_id,
                    "status": run.status,
                    "started_at": (
                        run.started_at.isoformat() if run.started_at else None
                    ),
                    "completed_at": (
                        run.completed_at.isoformat() if run.completed_at else None
                    ),
                    "duration_ms": run.duration_ms,
                    "feature_count": run.feature_count,
                    "nodes_executed": run.nodes_executed,
                    "nodes_succeeded": run.nodes_succeeded,
                    "nodes_failed": run.nodes_failed,
                    "errors": run.errors[:3] if run.errors else [],  # Limit to 3
                }
                for run in runs
            ],
            "total": total,
        }

    def get_background_jobs(self) -> Dict[str, Any]:
        """Get overview of all background jobs."""
        from app.repositories.export_job import ExportJobRepository
        from app.repositories.dataset_scan import DatasetScanRepository
        from app.repositories.dataset_version import DatasetVersionRepository

        export_repo = ExportJobRepository(self.db)
        scan_repo = DatasetScanRepository(self.db)
        version_repo = DatasetVersionRepository(self.db)

        # Get active export jobs
        active_exports = list(
            export_repo.collection.find(
                {"status": {"$in": ["pending", "processing"]}},
                sort=[("created_at", -1)],
                limit=10,
            )
        )

        # Get active scans
        active_scans = list(
            scan_repo.collection.find(
                {"status": {"$in": ["pending", "running", "partial"]}},
                sort=[("created_at", -1)],
                limit=10,
            )
        )

        # Get active enrichment versions
        active_enrichments = list(
            version_repo.collection.find(
                {"status": {"$in": ["pending", "processing"]}},
                sort=[("created_at", -1)],
                limit=10,
            )
        )

        return {
            "exports": [
                {
                    "id": str(j["_id"]),
                    "status": j.get("status"),
                    "format": j.get("format"),
                    "total_rows": j.get("total_rows", 0),
                    "processed_rows": j.get("processed_rows", 0),
                    "created_at": (
                        j.get("created_at").isoformat() if j.get("created_at") else None
                    ),
                }
                for j in active_exports
            ],
            "scans": [
                {
                    "id": str(s["_id"]),
                    "dataset_id": str(s.get("dataset_id")),
                    "tool_type": s.get("tool_type"),
                    "status": s.get("status"),
                    "total_commits": s.get("total_commits", 0),
                    "scanned_commits": s.get("scanned_commits", 0),
                    "created_at": (
                        s.get("created_at").isoformat() if s.get("created_at") else None
                    ),
                }
                for s in active_scans
            ],
            "enrichments": [
                {
                    "id": str(e["_id"]),
                    "dataset_id": str(e.get("dataset_id")),
                    "status": e.get("status"),
                    "total_rows": e.get("total_rows", 0),
                    "processed_rows": e.get("processed_rows", 0),
                    "created_at": (
                        e.get("created_at").isoformat() if e.get("created_at") else None
                    ),
                }
                for e in active_enrichments
            ],
            "summary": {
                "active_exports": len(active_exports),
                "active_scans": len(active_scans),
                "active_enrichments": len(active_enrichments),
            },
        }
