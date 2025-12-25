"""
Monitoring Service - Gathers system stats from Celery, Redis, MongoDB.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis
from bson import ObjectId
from pymongo.database import Database

from app.celery_app import celery_app
from app.config import settings
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.system_log import SystemLogRepository

logger = logging.getLogger(__name__)


class MonitoringService:
    """Service to gather system monitoring stats."""

    def __init__(self, db: Database):
        self.db = db
        self._redis_client: Optional[redis.Redis] = None
        self._raw_build_run_repo = RawBuildRunRepository(db)
        self._raw_repo_repo = RawRepositoryRepository(db)
        self._system_log_repo = SystemLogRepository(db)

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
            "trivy": self._get_trivy_stats(),
            "sonarqube": self._get_sonarqube_stats(),
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
                    "available": server_status.get("connections", {}).get("available", 0),
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

    def _get_trivy_stats(self) -> Dict[str, Any]:
        """Get Trivy tool health status."""
        try:
            from app.integrations.tools.trivy import TrivyTool

            tool = TrivyTool()
            return tool.get_health_status()
        except Exception as e:
            logger.error(f"Failed to get Trivy stats: {e}")
            return {
                "connected": False,
                "error": str(e),
            }

    def _get_sonarqube_stats(self) -> Dict[str, Any]:
        """Get SonarQube tool health status."""
        try:
            from app.integrations.tools.sonarqube import SonarQubeTool

            tool = SonarQubeTool()
            return tool.get_health_status()
        except Exception as e:
            logger.error(f"Failed to get SonarQube stats: {e}")
            return {
                "connected": False,
                "error": str(e),
            }

    def get_feature_audit_logs(
        self,
        limit: int = 50,
        skip: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recent feature extraction audit logs."""
        from app.repositories.feature_audit_log import FeatureAuditLogRepository

        audit_log_repo = FeatureAuditLogRepository(self.db)

        logs, total = audit_log_repo.find_recent(
            limit=limit,
            skip=skip,
            status=status,
        )

        return {
            "logs": [
                {
                    "id": str(log.id),
                    "category": log.category,
                    "raw_repo_id": str(log.raw_repo_id),
                    "raw_build_run_id": str(log.raw_build_run_id),
                    "status": log.status,
                    "started_at": (log.started_at.isoformat() if log.started_at else None),
                    "completed_at": (log.completed_at.isoformat() if log.completed_at else None),
                    "duration_ms": log.duration_ms,
                    "feature_count": log.feature_count,
                    "nodes_executed": log.nodes_executed,
                    "nodes_succeeded": log.nodes_succeeded,
                    "nodes_failed": log.nodes_failed,
                    "errors": log.errors[:3] if log.errors else [],
                }
                for log in logs
            ],
            "total": total,
        }

    def get_feature_audit_logs_cursor(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get audit logs with cursor-based pagination for infinite scroll."""

        from app.repositories.feature_audit_log import FeatureAuditLogRepository

        audit_log_repo = FeatureAuditLogRepository(self.db)

        logs, next_cursor, has_more = audit_log_repo.find_recent_cursor(
            limit=limit,
            cursor=cursor,
            status=status,
        )

        # Collect unique repo_ids and build_run_ids to batch lookup
        repo_ids = set()
        build_ids = set()
        for log in logs:
            repo_ids.add(log.raw_repo_id)
            build_ids.add(log.raw_build_run_id)

        # Batch lookup repositories using repository
        repo_map: Dict[str, Dict[str, Any]] = {}
        if repo_ids:
            repo_object_ids = [ObjectId(str(rid)) for rid in repo_ids]
            repos = self._raw_repo_repo.find_by_ids(repo_object_ids)
            for repo in repos:
                name = repo.full_name.split("/")[-1] if repo.full_name else ""
                repo_map[str(repo.id)] = {
                    "full_name": repo.full_name,
                    "name": name,
                }

        # Batch lookup build runs using repository
        build_map: Dict[str, Dict[str, Any]] = {}
        if build_ids:
            build_object_ids = [ObjectId(str(bid)) for bid in build_ids]
            build_map = self._raw_build_run_repo.find_metadata_by_ids(build_object_ids)

        return {
            "logs": [
                {
                    "id": str(log.id),
                    "category": log.category,
                    "raw_repo_id": str(log.raw_repo_id),
                    "raw_build_run_id": str(log.raw_build_run_id),
                    "repo": repo_map.get(str(log.raw_repo_id), {}),
                    "build": build_map.get(str(log.raw_build_run_id), {}),
                    "status": log.status,
                    "started_at": (log.started_at.isoformat() if log.started_at else None),
                    "completed_at": (log.completed_at.isoformat() if log.completed_at else None),
                    "duration_ms": log.duration_ms,
                    "feature_count": log.feature_count,
                    "nodes_executed": log.nodes_executed,
                    "nodes_succeeded": log.nodes_succeeded,
                    "nodes_failed": log.nodes_failed,
                    "errors": log.errors[:3] if log.errors else [],
                }
                for log in logs
            ],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def get_feature_audit_logs_by_dataset_cursor(
        self,
        dataset_id: str,
        limit: int = 20,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get audit logs for a specific dataset with cursor-based pagination."""

        from app.repositories.feature_audit_log import FeatureAuditLogRepository

        audit_log_repo = FeatureAuditLogRepository(self.db)

        logs, next_cursor, has_more = audit_log_repo.find_by_dataset_cursor(
            dataset_id=dataset_id,
            limit=limit,
            cursor=cursor,
            status=status,
            version_id=version_id,
        )

        # Collect unique repo_ids and build_run_ids to batch lookup
        repo_ids = set()
        build_ids = set()
        for log in logs:
            repo_ids.add(log.raw_repo_id)
            build_ids.add(log.raw_build_run_id)

        # Batch lookup repositories using repository
        repo_map: Dict[str, Dict[str, Any]] = {}
        if repo_ids:
            repo_object_ids = [ObjectId(str(rid)) for rid in repo_ids]
            repos = self._raw_repo_repo.find_by_ids(repo_object_ids)
            for repo in repos:
                name = repo.full_name.split("/")[-1] if repo.full_name else ""
                repo_map[str(repo.id)] = {
                    "full_name": repo.full_name,
                    "name": name,
                }

        # Batch lookup build runs using repository
        build_map: Dict[str, Dict[str, Any]] = {}
        if build_ids:
            build_object_ids = [ObjectId(str(bid)) for bid in build_ids]
            build_map = self._raw_build_run_repo.find_metadata_by_ids(build_object_ids)

        return {
            "logs": [
                {
                    "id": str(log.id),
                    "category": log.category,
                    "raw_repo_id": str(log.raw_repo_id),
                    "raw_build_run_id": str(log.raw_build_run_id),
                    "repo": repo_map.get(str(log.raw_repo_id), {}),
                    "build": build_map.get(str(log.raw_build_run_id), {}),
                    "status": log.status,
                    "started_at": (log.started_at.isoformat() if log.started_at else None),
                    "completed_at": (log.completed_at.isoformat() if log.completed_at else None),
                    "duration_ms": log.duration_ms,
                    "feature_count": log.feature_count,
                    "nodes_executed": log.nodes_executed,
                    "nodes_succeeded": log.nodes_succeeded,
                    "nodes_failed": log.nodes_failed,
                    "errors": log.errors[:3] if log.errors else [],
                }
                for log in logs
            ],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def get_feature_audit_logs_by_dataset_page(
        self,
        dataset_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get audit logs for a specific dataset with page-based pagination."""

        from app.repositories.feature_audit_log import FeatureAuditLogRepository

        audit_log_repo = FeatureAuditLogRepository(self.db)

        logs, total = audit_log_repo.find_by_dataset_page(
            dataset_id=dataset_id,
            page=page,
            page_size=page_size,
            status=status,
            version_id=version_id,
        )

        # Collect unique repo_ids and build_ids to batch lookup
        repo_ids = set()
        build_ids = set()
        for log in logs:
            repo_ids.add(log.raw_repo_id)
            build_ids.add(log.raw_build_run_id)

        # Batch lookup repositories
        repo_map: Dict[str, Dict[str, Any]] = {}
        if repo_ids:
            repo_object_ids = [ObjectId(str(rid)) for rid in repo_ids]
            repos = self._raw_repo_repo.find_by_ids(repo_object_ids)
            for repo in repos:
                name = repo.full_name.split("/")[-1] if repo.full_name else ""
                repo_map[str(repo.id)] = {
                    "full_name": repo.full_name,
                    "name": name,
                }

        # Batch lookup build runs
        build_map: Dict[str, Dict[str, Any]] = {}
        if build_ids:
            build_object_ids = [ObjectId(str(bid)) for bid in build_ids]
            build_map = self._raw_build_run_repo.find_metadata_by_ids(build_object_ids)

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "logs": [
                {
                    "id": str(log.id),
                    "category": log.category,
                    "raw_repo_id": str(log.raw_repo_id),
                    "raw_build_run_id": str(log.raw_build_run_id),
                    "repo": repo_map.get(str(log.raw_repo_id), {}),
                    "build": build_map.get(str(log.raw_build_run_id), {}),
                    "status": log.status,
                    "started_at": (log.started_at.isoformat() if log.started_at else None),
                    "completed_at": (log.completed_at.isoformat() if log.completed_at else None),
                    "duration_ms": log.duration_ms,
                    "feature_count": log.feature_count,
                    "nodes_executed": log.nodes_executed,
                    "nodes_succeeded": log.nodes_succeeded,
                    "nodes_failed": log.nodes_failed,
                    "errors": log.errors[:3] if log.errors else [],
                }
                for log in logs
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    def get_audit_log_detail(
        self,
        log_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get full audit log detail with node execution results."""

        from app.repositories.feature_audit_log import FeatureAuditLogRepository

        audit_log_repo = FeatureAuditLogRepository(self.db)
        log = audit_log_repo.find_by_id(log_id)

        if not log:
            return None

        # Lookup repo and build info
        repo_info = {}
        build_info = {}

        if log.raw_repo_id:
            repo = self._raw_repo_repo.find_by_id(log.raw_repo_id)
            if repo:
                name = repo.full_name.split("/")[-1] if repo.full_name else ""
                repo_info = {"full_name": repo.full_name, "name": name}

        if log.raw_build_run_id:
            build_map = self._raw_build_run_repo.find_metadata_by_ids(
                [ObjectId(str(log.raw_build_run_id))]
            )
            build_info = build_map.get(str(log.raw_build_run_id), {})

        return {
            "id": str(log.id),
            "correlation_id": log.correlation_id,
            "category": log.category,
            "raw_repo_id": str(log.raw_repo_id),
            "raw_build_run_id": str(log.raw_build_run_id),
            "repo": repo_info,
            "build": build_info,
            "status": log.status,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            "duration_ms": log.duration_ms,
            # Full node results
            "node_results": [
                {
                    "node_name": nr.node_name,
                    "status": nr.status,
                    "started_at": nr.started_at.isoformat() if nr.started_at else None,
                    "completed_at": nr.completed_at.isoformat() if nr.completed_at else None,
                    "duration_ms": nr.duration_ms,
                    "features_extracted": nr.features_extracted,
                    "resources_used": nr.resources_used,
                    "error": nr.error,
                    "warning": nr.warning,
                    "skip_reason": nr.skip_reason,
                }
                for nr in (log.node_results or [])
            ],
            "feature_count": log.feature_count,
            "features_extracted": log.features_extracted,
            "errors": log.errors,
            "warnings": log.warnings,
            "nodes_executed": log.nodes_executed,
            "nodes_succeeded": log.nodes_succeeded,
            "nodes_failed": log.nodes_failed,
            "nodes_skipped": log.nodes_skipped,
            "total_retries": log.total_retries,
        }

    def get_system_logs(
        self,
        limit: int = 100,
        skip: int = 0,
        level: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get system logs from MongoDB 'system_logs' collection.

        Args:
            limit: Max number of logs to return
            skip: Pagination offset
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
            source: Filter by source/component
        """
        logs, total = self._system_log_repo.find_recent(
            skip=skip,
            limit=limit,
            level=level,
            source=source,
        )

        return {
            "logs": [
                {
                    "id": str(log.id),
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "level": log.level,
                    "source": log.source,
                    "message": log.message,
                    "details": log.details,
                }
                for log in logs
            ],
            "total": total,
            "has_more": skip + limit < total,
        }

    def get_logs_for_export(
        self,
        level: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Dict[str, Any]]:
        """
        Get logs for export with optional date filtering.
        """
        logs = self._system_log_repo.find_for_export(
            level=level,
            source=source,
            start_date=start_date,
            end_date=end_date,
        )

        return [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "source": log.source,
                "message": log.message,
                "details": log.details,
            }
            for log in logs
        ]

    def stream_logs_export(
        self,
        format: str = "csv",
        level: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """
        Stream logs export as CSV or JSON.

        Args:
            format: "csv" or "json"
            level: Filter by log level
            source: Filter by source/component
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date

        Returns:
            Generator yielding CSV/JSON chunks
        """
        from app.utils.export_utils import format_log_row, stream_csv, stream_json

        cursor = self._system_log_repo.get_cursor_for_export(
            level=level,
            source=source,
            start_date=start_date,
            end_date=end_date,
        )

        if format == "csv":
            return stream_csv(cursor, format_log_row)
        else:
            return stream_json(cursor, format_log_row)

    def get_log_metrics(
        self,
        hours: int = 24,
        bucket_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Get log count metrics aggregated by time bucket and level.

        Used for metrics charts on the monitoring dashboard.

        Args:
            hours: Number of hours to look back (default 24)
            bucket_minutes: Size of each time bucket in minutes (default 60)

        Returns:
            Dict with time_buckets array and level_counts
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours)

        # Aggregation pipeline to bucket logs by time and level
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_time}}},
            {
                "$group": {
                    "_id": {
                        "bucket": {
                            "$dateTrunc": {
                                "date": "$timestamp",
                                "unit": "minute",
                                "binSize": bucket_minutes,
                            }
                        },
                        "level": "$level",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.bucket": 1}},
        ]

        results = list(self._system_log_repo.aggregate(pipeline))

        # Transform results into chart-friendly format
        buckets_dict: Dict[str, Dict[str, int]] = {}
        for r in results:
            bucket_time = r["_id"]["bucket"].isoformat()
            level = r["_id"]["level"]
            count = r["count"]

            if bucket_time not in buckets_dict:
                buckets_dict[bucket_time] = {
                    "timestamp": bucket_time,
                    "ERROR": 0,
                    "WARNING": 0,
                    "INFO": 0,
                    "DEBUG": 0,
                }
            buckets_dict[bucket_time][level] = count

        # Sort by timestamp and return as array
        time_buckets = sorted(buckets_dict.values(), key=lambda x: x["timestamp"])

        # Calculate totals
        level_totals = {"ERROR": 0, "WARNING": 0, "INFO": 0, "DEBUG": 0}
        for bucket in time_buckets:
            for level in level_totals:
                level_totals[level] += bucket.get(level, 0)

        return {
            "time_buckets": time_buckets,
            "level_totals": level_totals,
            "hours": hours,
            "bucket_minutes": bucket_minutes,
        }
