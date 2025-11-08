"""Utility helpers to seed the MongoDB database with deterministic mock data."""
from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
import random
from typing import Iterable, Tuple

from app.database.mongo import get_database

RiskLevel = Tuple[str, float, float]


def _create_mock_builds(count: int = 20) -> int:
    db = get_database()
    if db.builds.count_documents({}) > 0:
        return 0

    rng = random.Random(42)
    base_time = datetime.now(timezone.utc)

    repositories = [
        ("buildguard/core-platform", ["CI", "Security Scan", "Release"]),
        ("buildguard/ui-dashboard", ["CI", "Chromatic", "Release"]),
        ("buildguard/ml-pipeline", ["Model Training", "Data Sync", "CI"]),
    ]

    branches = ["main", "develop", "release/v1.6.0", "feature/github-sync"]
    statuses = ["completed", "in_progress", "queued"]
    conclusions = ["success", "failure", "neutral", "cancelled"]
    authors = [
        ("Lan Pham", "lan.pham@buildguard.dev"),
        ("An Nguyen", "an.nguyen@buildguard.dev"),
        ("Minh Do", "minh.do@buildguard.dev"),
        ("Linh Vu", "linh.vu@buildguard.dev"),
    ]
    risk_levels: Iterable[RiskLevel] = [
        ("low", 0.18, 0.05),
        ("medium", 0.47, 0.14),
        ("high", 0.73, 0.21),
        ("critical", 0.9, 0.28),
    ]

    builds_created = 0

    for idx in range(1, count + 1):
        repo, workflows = rng.choice(repositories)
        workflow = rng.choice(workflows)
        branch = rng.choice(branches)
        status = rng.choices(statuses, weights=[0.7, 0.2, 0.1], k=1)[0]
        conclusion = rng.choices(conclusions, weights=[0.75, 0.15, 0.05, 0.05], k=1)[0] if status == "completed" else None
        author_name, author_email = rng.choice(authors)
        risk_level, base_score, base_uncertainty = rng.choice(list(risk_levels))

        started_at = base_time - timedelta(hours=idx * rng.uniform(2.5, 6.5))
        duration_minutes = rng.randint(5, 45)
        completed_at = started_at + timedelta(minutes=duration_minutes) if status == "completed" else None

        sonarqube_result = {
            "id": idx,
            "build_id": idx,
            "bugs": rng.randint(0, 5),
            "vulnerabilities": rng.randint(0, 3),
            "code_smells": rng.randint(20, 150),
            "coverage": round(rng.uniform(42, 88), 1),
            "duplicated_lines_density": round(rng.uniform(0.5, 8.5), 1),
            "technical_debt_minutes": rng.randint(30, 360),
            "quality_gate_status": rng.choice(["OK", "WARN", "ERROR"]),
            "analyzed_at": (completed_at or started_at) + timedelta(minutes=5),
        }

        risk_assessment = {
            "build_id": idx,
            "risk_score": round(base_score + rng.uniform(-0.05, 0.05), 2),
            "uncertainty": round(base_uncertainty + rng.uniform(-0.03, 0.03), 2),
            "risk_level": risk_level,
            "model_version": "mock-0.1.0",
            "calculated_at": (completed_at or started_at) + timedelta(minutes=7),
        }

        build_document = {
            "_id": idx,
            "repository": repo,
            "branch": branch,
            "commit_sha": f"{rng.getrandbits(32):08x}",
            "build_number": f"{idx + 120}",
            "workflow_name": workflow,
            "status": status,
            "conclusion": conclusion,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": duration_minutes * 60 if completed_at else None,
            "author_name": author_name,
            "author_email": author_email,
            "url": f"https://github.com/{repo}/actions",
            "logs_url": f"https://github.com/{repo}/actions/runs/{rng.randint(10_000_000, 99_999_999)}",
            "created_at": started_at,
            "updated_at": completed_at,
            "sonarqube_result": sonarqube_result,
            "risk_assessment": risk_assessment,
        }

        db.builds.insert_one(build_document)
        builds_created += 1

    return builds_created


def _seed_system_settings() -> None:
    db = get_database()
    if db.system_settings.count_documents({}) == 0:
        db.system_settings.insert_one(
            {
                "_id": "primary",
                "model_version": "bayesian-cnn-v0.3.1",
                "risk_threshold_high": 0.72,
                "risk_threshold_medium": 0.48,
                "uncertainty_threshold": 0.22,
                "auto_rescan_enabled": True,
                "updated_at": datetime.now(timezone.utc),
                "updated_by": "system",
            }
        )


def _seed_activity_logs() -> None:
    db = get_database()
    if db.activity_logs.count_documents({}) > 0:
        return
    now = datetime.now(timezone.utc)
    entries = [
        {
            "_id": "log-import-1",
            "action": "repository_import",
            "actor": "admin",
            "scope": "repository",
            "message": "Import buildguard/core-platform hoàn tất.",
            "created_at": now - timedelta(minutes=25),
            "metadata": {"repository": "buildguard/core-platform"},
        },
        {
            "_id": "log-enrichment-1",
            "action": "data_enrichment",
            "actor": "admin",
            "scope": "pipeline",
            "message": "Pipeline enrichment chạy thành công (78% hoàn thành).",
            "created_at": now - timedelta(minutes=15),
            "metadata": {"stage": "normalization"},
        },
        {
            "_id": "log-notification-1",
            "action": "notification_sent",
            "actor": "system",
            "scope": "alerts",
            "message": "Alert gửi tới DevOps cho build #142 (High risk).",
            "created_at": now - timedelta(minutes=5),
            "metadata": {"build_id": "142"},
        },
    ]
    db.activity_logs.insert_many(entries)


def _seed_notification_data() -> None:
    db = get_database()
    if db.notification_policies.count_documents({}) == 0:
        db.notification_policies.insert_one(
            {
                "_id": "primary",
                "risk_threshold_high": 0.75,
                "uncertainty_threshold": 0.25,
                "channels": ["email", "slack"],
                "muted_repositories": [],
                "last_updated_at": datetime.now(timezone.utc),
                "last_updated_by": "system",
            }
        )
    if db.notification_events.count_documents({}) == 0:
        now = datetime.now(timezone.utc)
        db.notification_events.insert_many(
            [
                {
                    "_id": "notif-1",
                    "build_id": 141,
                    "repository": "buildguard/core-platform",
                    "branch": "main",
                    "risk_level": "high",
                    "risk_score": 0.78,
                    "uncertainty": 0.18,
                    "status": "sent",
                    "created_at": now - timedelta(minutes=7),
                    "message": "Build #141 được đánh giá High risk · đề nghị kiểm tra trước deploy.",
                },
                {
                    "_id": "notif-2",
                    "build_id": 138,
                    "repository": "buildguard/ui-dashboard",
                    "branch": "develop",
                    "risk_level": "medium",
                    "risk_score": 0.58,
                    "uncertainty": 0.27,
                    "status": "new",
                    "created_at": now - timedelta(minutes=2),
                    "message": "Độ bất định cao cho build #138 · xem lại unit test flakiness.",
                },
            ]
        )


def _seed_import_jobs() -> int:
    db = get_database()
    if db.github_import_jobs.count_documents({}) > 0:
        return 0

    now = datetime.now(timezone.utc)
    jobs = [
        {
            "_id": "job-core-platform",
            "repository": "buildguard/core-platform",
            "branch": "main",
            "status": "completed",
            "progress": 100,
            "builds_imported": 160,
            "commits_analyzed": 860,
            "tests_collected": 320,
            "initiated_by": "admin",
            "created_at": now - timedelta(hours=6),
            "started_at": now - timedelta(hours=5, minutes=50),
            "completed_at": now - timedelta(hours=5, minutes=20),
            "last_error": None,
            "notes": "Thu thập toàn bộ lịch sử workflow runs (GitHub Actions).",
        },
        {
            "_id": "job-ui-dashboard",
            "repository": "buildguard/ui-dashboard",
            "branch": "develop",
            "status": "running",
            "progress": 68,
            "builds_imported": 88,
            "commits_analyzed": 420,
            "tests_collected": 180,
            "initiated_by": "devops",
            "created_at": now - timedelta(hours=2),
            "started_at": now - timedelta(hours=1, minutes=35),
            "completed_at": None,
            "last_error": None,
            "notes": "Đang lấy logs Chromatic + SonarQube metrics.",
        },
        {
            "_id": "job-ml-pipeline",
            "repository": "buildguard/ml-pipeline",
            "branch": "feature/bayesian-normalizer",
            "status": "failed",
            "progress": 34,
            "builds_imported": 34,
            "commits_analyzed": 140,
            "tests_collected": 64,
            "initiated_by": "admin",
            "created_at": now - timedelta(hours=1, minutes=10),
            "started_at": now - timedelta(hours=1),
            "completed_at": now - timedelta(minutes=35),
            "last_error": "Timeout khi gọi GitHub Actions artifacts API.",
            "notes": "Tự động retry sau 15 phút.",
        },
    ]

    db.github_import_jobs.insert_many(jobs)
    return len(jobs)


def seed_database(force: bool = False, count: int = 20) -> int:
    db = get_database()
    if force:
        db.builds.delete_many({})
        db.github_connection.delete_many({})
        db.github_states.delete_many({})
        db.github_import_jobs.delete_many({})
        db.system_settings.delete_many({})
        db.activity_logs.delete_many({})
        db.notification_policies.delete_many({})
        db.notification_events.delete_many({})

    created = _create_mock_builds(count=count)
    _seed_import_jobs()
    _seed_system_settings()
    _seed_activity_logs()
    _seed_notification_data()
    return created


def cli() -> None:
    parser = ArgumentParser(description="Seed the BuildGuard database with mock data.")
    parser.add_argument("--force", action="store_true", help="Remove existing records before seeding.")
    parser.add_argument("--count", type=int, default=20, help="Number of builds to generate.")
    parser.add_argument("--seed-only", action="store_true", help="Alias for compatibility (no-op).")
    args = parser.parse_args()

    inserted = seed_database(force=args.force, count=args.count)
    print(f"Inserted {inserted} mock builds.")


if __name__ == "__main__":
    cli()
