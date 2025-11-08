"""Analytics helpers to power dashboard endpoints (MongoDB)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from pymongo.database import Database

RiskCounts = Dict[str, int]


def _risk_level(build: Dict[str, Any]) -> str:
    risk = build.get("risk_assessment") or {}
    return risk.get("risk_level", "low")


def _risk_score(build: Dict[str, Any]) -> float:
    risk = build.get("risk_assessment") or {}
    return float(risk.get("risk_score", 0.0))


def _same_day(a: datetime, b: datetime) -> bool:
    return a.date() == b.date()


def _ensure_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _serialize_high_risk(build: Dict[str, Any]) -> Dict[str, Any]:
    started_at = _ensure_datetime(build.get("started_at"))
    completed_at = _ensure_datetime(build.get("completed_at"))
    return {
        "id": build["_id"],
        "repository": build.get("repository"),
        "branch": build.get("branch"),
        "workflow_name": build.get("workflow_name"),
        "risk_level": _risk_level(build),
        "risk_score": _risk_score(build),
        "conclusion": build.get("conclusion"),
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
    }


def compute_dashboard_summary(db: Database) -> Dict[str, object]:
    builds = list(db.builds.find())
    total_builds = len(builds)

    if total_builds == 0:
        return {
            "metrics": {
                "total_builds": 0,
                "average_risk_score": 0.0,
                "success_rate": 0.0,
                "average_duration_minutes": 0.0,
                "risk_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            },
            "trends": [],
            "repo_distribution": [],
            "risk_heatmap": [],
            "high_risk_builds": [],
        }

    risk_distribution: RiskCounts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    total_duration = 0
    duration_count = 0
    completed_builds = 0
    successful_builds = 0

    for build in builds:
        level = _risk_level(build)
        risk_distribution[level] = risk_distribution.get(level, 0) + 1

        duration_seconds = build.get("duration_seconds")
        if duration_seconds:
            total_duration += duration_seconds
            duration_count += 1

        if build.get("status") == "completed":
            completed_builds += 1
            if build.get("conclusion") == "success":
                successful_builds += 1

    average_risk_score = sum(_risk_score(build) for build in builds) / max(total_builds, 1)
    average_duration_minutes = (total_duration / duration_count / 60) if duration_count else 0.0
    success_rate = (successful_builds / completed_builds) * 100 if completed_builds else 0.0

    today = datetime.now(timezone.utc)
    trend_days = [today - timedelta(days=offset) for offset in range(9, -1, -1)]

    trends = []
    for day in trend_days:
        day_builds = []
        for build in builds:
            completed_at = _ensure_datetime(build.get("completed_at"))
            if completed_at and _same_day(completed_at, day):
                day_builds.append(build)

        trend = {
            "date": day.strftime("%d/%m"),
            "builds": len(day_builds),
            "risk_score": round(
                sum(_risk_score(build) for build in day_builds) / max(len(day_builds), 1), 2
            )
            if day_builds
            else 0.0,
            "failures": sum(1 for build in day_builds if build.get("conclusion") == "failure"),
        }
        trends.append(trend)

    repo_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {"builds": 0, "high_risk": 0})
    for build in builds:
        repo = build.get("repository", "unknown")
        stats = repo_map[repo]
        stats["builds"] += 1
        if _risk_level(build) in {"high", "critical"}:
            stats["high_risk"] += 1

    repo_distribution = [
        {"repository": repo, "builds": stats["builds"], "highRisk": stats["high_risk"]}
        for repo, stats in repo_map.items()
    ]

    heatmap_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    heatmap = []
    for day in heatmap_days:
        row = {"day": day.strftime("%a"), "low": 0, "medium": 0, "high": 0, "critical": 0}
        for build in builds:
            completed_at = _ensure_datetime(build.get("completed_at"))
            if completed_at and _same_day(completed_at, day):
                level = _risk_level(build)
                row[level] = row.get(level, 0) + 1
        heatmap.append(row)

    high_risk_builds = [
        _serialize_high_risk(build)
        for build in builds
        if _risk_level(build) in {"high", "critical"}
    ]
    high_risk_builds.sort(key=lambda item: item["risk_score"], reverse=True)
    high_risk_builds = high_risk_builds[:6]

    return {
        "metrics": {
            "total_builds": total_builds,
            "average_risk_score": round(average_risk_score, 2),
            "success_rate": round(success_rate, 1),
            "average_duration_minutes": round(average_duration_minutes, 1),
            "risk_distribution": risk_distribution,
        },
        "trends": trends,
        "repo_distribution": repo_distribution,
        "risk_heatmap": heatmap,
        "high_risk_builds": high_risk_builds,
    }
