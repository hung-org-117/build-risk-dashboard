"""
Dataset Scan Service

Orchestrates scanning datasets using integration tools (SonarQube, Trivy).
"""

import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.dataset_scan import DatasetScan, DatasetScanStatus
from app.entities.dataset_scan_result import DatasetScanResult
from app.repositories.dataset_scan import DatasetScanRepository
from app.repositories.dataset_scan_result import DatasetScanResultRepository
from app.repositories.dataset_build_repository import DatasetBuildRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.integrations import get_tool, get_available_tools

logger = logging.getLogger(__name__)


class DatasetScanService:
    """Service for managing dataset scans."""

    def __init__(self, db: Database):
        self.db = db
        self.scan_repo = DatasetScanRepository(db)
        self.result_repo = DatasetScanResultRepository(db)
        self.build_repo = DatasetBuildRepository(db)
        self.run_repo = RawBuildRunRepository(db)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available integration tools with their info."""
        return [tool.to_info_dict() for tool in get_available_tools()]

    def get_commits_from_builds(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Get commits from validated dataset builds.

        Queries dataset_builds with status=FOUND and joins with
        raw_build_runs to get commit SHA and repo info.

        Returns list of:
        {
            "sha": "abc123...",
            "repo_full_name": "owner/repo",
            "build_id": "123456",
            "workflow_run_id": ObjectId,
        }
        """
        # Get validated builds with workflow_run_id
        builds = self.build_repo.find_builds_with_run_ids(dataset_id)
        if not builds:
            return []

        commits = []
        seen_commits = set()  # Deduplicate by commit_sha

        for build in builds:
            if not build.workflow_run_id:
                continue

            # Get the RawBuildRun to get commit info
            run = self.run_repo.find_by_id(str(build.workflow_run_id))
            if not run:
                logger.warning(
                    f"RawBuildRun not found for workflow_run_id: {build.workflow_run_id}"
                )
                continue

            # commit_sha = original commit for scan result identification
            # effective_sha = for worktree checkout (replayed fork commits)
            commit_sha = run.commit_sha
            effective_sha = run.effective_sha  # May be None if not a fork

            if not commit_sha:
                continue

            # Deduplicate by original commit_sha (for scan result identification)
            if commit_sha in seen_commits:
                continue
            seen_commits.add(commit_sha)

            commits.append(
                {
                    "sha": commit_sha,  # Primary ID for scan results
                    "effective_sha": effective_sha,  # For worktree checkout (if fork)
                    "repo_full_name": run.repo_name,
                    "build_id": build.build_id_from_csv,
                    "workflow_run_id": str(build.workflow_run_id),
                    "row_indices": [],  # Not used anymore but kept for compatibility
                }
            )

        logger.info(
            f"Found {len(commits)} unique commits from {len(builds)} validated builds"
        )
        return commits

    def start_scan(
        self,
        dataset_id: str,
        user_id: str,
        tool_type: str,
        scan_config: Optional[str] = None,
    ) -> DatasetScan:
        """
        Start a scan job for a dataset.

        Scans all validated builds (status=FOUND) for the dataset.

        Args:
            dataset_id: Dataset to scan
            user_id: User initiating the scan
            tool_type: Tool to use (sonarqube or trivy)
            scan_config: Default config content for all commits

        Returns:
            Created DatasetScan entity
        """
        # Validate tool
        tool = get_tool(tool_type)
        if not tool:
            raise ValueError(f"Unknown tool type: {tool_type}")
        if not tool.is_available():
            raise ValueError(f"Tool {tool_type} is not configured or available")

        # Get commits from validated builds
        commits = self.get_commits_from_builds(dataset_id)
        if not commits:
            raise ValueError("No validated builds with commits found in dataset")

        # Create scan record
        scan = DatasetScan(
            dataset_id=ObjectId(dataset_id),
            user_id=ObjectId(user_id),
            tool_type=tool_type,
            commits=commits,
            scan_config=scan_config,
            total_commits=len(commits),
        )
        scan = self.scan_repo.insert_one(scan)

        # Create result records for each commit
        results = []
        for commit in commits:
            result = DatasetScanResult(
                scan_id=scan.id,
                dataset_id=ObjectId(dataset_id),
                commit_sha=commit["sha"],
                effective_sha=commit.get("effective_sha"),  # For worktree checkout
                repo_full_name=commit["repo_full_name"],
                row_indices=commit.get("row_indices", []),
            )
            results.append(result)

        if results:
            self.result_repo.bulk_insert(results)

        # Dispatch Celery task
        self._dispatch_scan_task(scan)

        return scan

    def _dispatch_scan_task(self, scan: DatasetScan) -> str:
        """Dispatch Celery task for the scan."""
        from app.tasks.integration_scan import run_dataset_scan

        task = run_dataset_scan.delay(str(scan.id))

        # Update scan with task ID
        self.scan_repo.update_one(str(scan.id), {"task_id": task.id})

        return task.id

    def get_scan(self, scan_id: str) -> Optional[DatasetScan]:
        """Get a scan by ID."""
        return self.scan_repo.find_by_id(scan_id)

    def list_scans(
        self, dataset_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[List[DatasetScan], int]:
        """List scans for a dataset with pagination."""
        return self.scan_repo.find_by_dataset(dataset_id, skip=skip, limit=limit)

    def get_active_scans(self, dataset_id: str) -> List[DatasetScan]:
        """Get currently active scans for a dataset."""
        return self.scan_repo.find_active_by_dataset(dataset_id)

    def cancel_scan(self, scan_id: str) -> bool:
        """Cancel a running scan."""
        scan = self.scan_repo.find_by_id(scan_id)
        if not scan:
            return False

        if scan.status not in (
            DatasetScanStatus.PENDING,
            DatasetScanStatus.RUNNING,
            DatasetScanStatus.PARTIAL,
        ):
            return False

        # Revoke Celery task if exists
        if scan.task_id:
            from app.celery_app import celery_app

            celery_app.control.revoke(scan.task_id, terminate=True)

        self.scan_repo.mark_status(scan_id, DatasetScanStatus.CANCELLED)
        return True

    def get_scan_results(
        self, scan_id: str, skip: int = 0, limit: int = 50
    ) -> tuple[List[DatasetScanResult], int]:
        """Get results for a scan with pagination."""
        return self.result_repo.find_by_scan_paginated(scan_id, skip=skip, limit=limit)

    def get_scan_summary(self, scan_id: str) -> Dict[str, Any]:
        """Get aggregated summary of scan results."""
        scan = self.scan_repo.find_by_id(scan_id)
        if not scan:
            return {}

        status_counts = self.result_repo.count_by_scan_status(scan_id)
        aggregated = self.result_repo.get_aggregated_results(scan_id)

        return {
            "scan_id": scan_id,
            "tool_type": scan.tool_type,
            "status": scan.status.value,
            "progress": scan.progress_percentage,
            "total_commits": scan.total_commits,
            "status_counts": status_counts,
            "aggregated_metrics": aggregated,
        }

    def handle_sonar_webhook(
        self, component_key: str, metrics: Dict[str, Any]
    ) -> Optional[DatasetScanResult]:
        """
        Handle SonarQube webhook callback.

        Called when SonarQube finishes analysis and sends webhook.
        Updates the corresponding result and checks if scan is complete.
        """
        result = self.result_repo.find_by_component_key(component_key)
        if not result:
            logger.warning(
                f"No pending result found for component_key: {component_key}"
            )
            return None

        # Update result with metrics
        self.result_repo.mark_completed(str(result.id), metrics)

        # Check if all results for this scan are done
        self._check_scan_completion(str(result.scan_id))

        return result

    def _check_scan_completion(self, scan_id: str) -> None:
        """Check if a scan is complete and update status."""
        pending = self.result_repo.find_pending_by_scan(scan_id)

        if not pending:
            # All done
            status_counts = self.result_repo.count_by_scan_status(scan_id)
            aggregated = self.result_repo.get_aggregated_results(scan_id)

            self.scan_repo.mark_status(
                scan_id,
                DatasetScanStatus.COMPLETED,
                results_summary=aggregated,
            )
            self.scan_repo.update_progress(
                scan_id,
                scanned=status_counts.get("completed", 0),
                failed=status_counts.get("failed", 0),
                pending=0,
            )
        else:
            # Still pending
            status_counts = self.result_repo.count_by_scan_status(scan_id)
            self.scan_repo.update_progress(
                scan_id,
                scanned=status_counts.get("completed", 0),
                failed=status_counts.get("failed", 0),
                pending=len(pending),
            )

    def get_failed_results(self, scan_id: str) -> List[DatasetScanResult]:
        """Get all failed results for a scan (for retry UI)."""
        return self.result_repo.find_failed_by_scan(scan_id)

    def retry_failed_result(
        self,
        result_id: str,
        override_config: Optional[str] = None,
    ) -> Optional[DatasetScanResult]:
        """
        Retry a failed scan result with optional custom config.

        Args:
            result_id: ID of the failed result to retry
            override_config: Optional config override for this commit

        Returns:
            Updated result entity or None if not found/not failed
        """
        # Reset the result for retry
        success = self.result_repo.reset_for_retry(result_id, override_config)
        if not success:
            return None

        # Get the updated result
        result = self.result_repo.find_by_id(result_id)
        if not result:
            return None

        # Get the parent scan
        scan = self.scan_repo.find_by_id(str(result.scan_id))
        if not scan:
            return None

        # Dispatch single result scan task
        self._dispatch_single_result_task(result, scan)

        return result

    def _dispatch_single_result_task(
        self, result: DatasetScanResult, scan: DatasetScan
    ) -> str:
        """Dispatch Celery task for a single result retry."""
        from app.tasks.integration_scan import retry_scan_result

        task = retry_scan_result.delay(str(result.id), str(scan.id))
        return task.id
