from app.tasks.pipeline.resource_dag.dag import (
    get_ingestion_tasks,
    get_ingestion_tasks_by_level,
    get_resource_dag_runner,
    ResourceDAGRunner,
    TASK_DEPENDENCIES,
)

INGESTION_TASK_TO_CELERY = {
    "clone_repo": "app.tasks.shared.clone_repo",
    "fetch_and_save_builds": "app.tasks.model_ingestion.fetch_and_save_builds",
    "download_build_logs": "app.tasks.shared.download_build_logs",
    "create_worktrees_batch": "app.tasks.shared.create_worktrees_batch",
}

__all__ = [
    "get_ingestion_tasks",
    "get_ingestion_tasks_by_level",
    "get_resource_dag_runner",
    "ResourceDAGRunner",
    "INGESTION_TASK_TO_CELERY",
    "TASK_DEPENDENCIES",
]
