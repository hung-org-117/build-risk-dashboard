"""Utility helpers to describe mock risk explanations for builds."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Tuple


def _hash_to_range(seed: str, min_value: float, max_value: float) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    scale = int(digest[:8], 16) / 0xFFFFFFFF
    return min_value + (max_value - min_value) * scale


def _default_risk_assessment() -> Dict[str, Any]:
    return {
        "risk_score": 0.35,
        "uncertainty": 0.12,
        "risk_level": "medium",
        "model_version": "mock-0.1.0",
    }


def _normalize_weights(values: Dict[str, float]) -> Dict[str, float]:
    total = sum(value for value in values.values() if value > 0)
    if total == 0:
        return {key: 0.0 for key in values}
    return {key: value / total for key, value in values.items()}


def _confidence_label(uncertainty: float) -> str:
    if uncertainty < 0.1:
        return "Cao"
    if uncertainty < 0.2:
        return "Trung bình"
    return "Thấp"


def _summary_text(repository: str, branch: str, risk_level: str, top_factor: str) -> str:
    level_map = {
        "low": "an toàn",
        "medium": "cần theo dõi",
        "high": "rủi ro cao",
        "critical": "rủi ro nghiêm trọng",
    }
    level_label = level_map.get(risk_level, risk_level)
    return (
        f"Build tại {repository} ({branch}) được đánh giá {level_label}; "
        f"yếu tố nổi bật là {top_factor.lower()}."
    )


def _recommendations(risk_level: str) -> Tuple[str, str, str]:
    if risk_level in {"high", "critical"}:
        return (
            "Tạm dừng triển khai và yêu cầu DevSecOps review thay đổi có churn cao.",
            "Ưu tiên chạy lại các bộ integration test và kiểm tra SonarQube findings mới.",
            "Bật chế độ canary hoặc blue/green nếu vẫn cần deploy build này.",
        )
    if risk_level == "medium":
        return (
            "Theo dõi sát các thông số test flakiness trước khi phát hành.",
            "Đảm bảo quality gate đạt yêu cầu (>80% coverage, không có bug blocker).",
            "Cân nhắc thêm reviewer có kinh nghiệm domain vào pull request.",
        )
    return (
        "Build ổn định, vẫn nên chạy smoke test hậu triển khai.",
        "Lên lịch đồng bộ dữ liệu bổ sung để giữ mô hình cập nhật.",
        "Giữ lại artifacts & logs để phục vụ phân tích nếu có sự cố.",
    )


def compute_risk_explanation(build: Dict[str, Any]) -> Dict[str, Any]:
    """Construct a descriptive explanation for the current build risk score."""
    risk = build.get("risk_assessment") or _default_risk_assessment()
    sonar = build.get("sonarqube_result") or {}

    commit_sha = build.get("commit_sha") or str(build.get("_id"))
    repository = build.get("repository", "unknown")
    branch = build.get("branch", "main")
    conclusion = build.get("conclusion") or "unknown"
    duration = int(build.get("duration_seconds") or 0)
    coverage = float(sonar.get("coverage") or 0.0)
    code_smells = int(sonar.get("code_smells") or 0)
    vulnerabilities = int(sonar.get("vulnerabilities") or 0)

    files_changed = int(_hash_to_range(commit_sha, 4, 32))
    lines_changed = int(files_changed * _hash_to_range(repository, 18, 64))
    flaky_tests = int(_hash_to_range(branch, 0, 4))
    if conclusion == "failure":
        flaky_tests += 2

    churn_weight = (files_changed * 0.6 + lines_changed * 0.4) / 100.0
    quality_weight = ((max(0.0, 75 - coverage) / 75) + (code_smells / 150)) / 2
    test_weight = (flaky_tests + (1 if conclusion == "failure" else 0)) / 6
    history_weight = _hash_to_range(f"{repository}:{branch}", 0.2, 0.8)
    delivery_weight = (duration / 1800) if duration else 0.1

    raw_weights = {
        "churn": churn_weight,
        "quality": quality_weight,
        "tests": test_weight,
        "history": history_weight,
        "delivery": delivery_weight,
    }
    normalized = _normalize_weights(raw_weights)

    drivers = [
        {
            "key": "code_churn",
            "label": "Code churn & phạm vi thay đổi",
            "impact": "increase",
            "contribution": round(normalized["churn"], 2),
            "description": "Số file/line thay đổi cao làm tăng nguy cơ bỏ sót lỗi.",
            "metrics": {
                "files_changed": files_changed,
                "lines_changed": lines_changed,
            },
        },
        {
            "key": "quality_gate",
            "label": "Chất lượng & bảo mật",
            "impact": "increase" if coverage < 80 or vulnerabilities > 0 else "decrease",
            "contribution": round(normalized["quality"], 2),
            "description": "Coverage thấp hoặc technical debt cao ảnh hưởng đến độ an toàn.",
            "metrics": {
                "coverage": round(coverage, 1),
                "code_smells": code_smells,
                "vulnerabilities": vulnerabilities,
            },
        },
        {
            "key": "test_health",
            "label": "Độ ổn định test",
            "impact": "increase" if flaky_tests else "decrease",
            "contribution": round(normalized["tests"], 2),
            "description": "Flaky tests hoặc kết luận thất bại khiến mô hình giảm niềm tin.",
            "metrics": {
                "flaky_suites": flaky_tests,
                "last_conclusion": conclusion,
            },
        },
        {
            "key": "history",
            "label": "Tiền sử deploy của branch",
            "impact": "increase" if normalized["history"] > 0.25 else "decrease",
            "contribution": round(normalized["history"], 2),
            "description": "Nhánh có lịch sử thất bại hoặc thay đổi lớn cần review kỹ hơn.",
            "metrics": {
                "volatility_index": round(history_weight, 2),
            },
        },
        {
            "key": "delivery_pressure",
            "label": "Áp lực thời gian build",
            "impact": "increase" if duration and duration > 1200 else "decrease",
            "contribution": round(normalized["delivery"], 2),
            "description": "Thời gian build kéo dài/đột biến là dấu hiệu pipeline quá tải.",
            "metrics": {
                "duration_seconds": duration,
                "status": build.get("status"),
            },
        },
    ]

    feature_breakdown = {
        "Code churn": round(normalized["churn"] * 100, 1),
        "Quality": round(normalized["quality"] * 100, 1),
        "Tests": round(normalized["tests"] * 100, 1),
        "History": round(normalized["history"] * 100, 1),
        "Delivery": round(normalized["delivery"] * 100, 1),
    }

    top_factor = max(drivers, key=lambda item: item["contribution"])
    summary = _summary_text(repository, branch, risk.get("risk_level", "medium"), top_factor["label"])

    recs = list(_recommendations(risk.get("risk_level", "medium")))

    return {
        "build_id": build.get("_id"),
        "risk_score": float(risk.get("risk_score", 0.35)),
        "uncertainty": float(risk.get("uncertainty", 0.15)),
        "risk_level": risk.get("risk_level", "medium"),
        "summary": summary,
        "confidence": _confidence_label(float(risk.get("uncertainty", 0.15))),
        "model_version": risk.get("model_version"),
        "updated_at": datetime.now(timezone.utc),
        "drivers": drivers,
        "feature_breakdown": feature_breakdown,
        "recommended_actions": recs,
    }
