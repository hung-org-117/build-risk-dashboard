"""Risk assessment endpoints powered by MongoDB."""
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.database.mongo import get_db
from app.models.schemas import RiskExplanationResponse, RiskScoreResponse
from app.services.risk_engine import compute_risk_explanation

router = APIRouter()


def _default_risk_assessment() -> Dict[str, Any]:
    return {
        "risk_score": 0.35,
        "uncertainty": 0.12,
        "risk_level": "medium",
        "model_version": "mock-0.1.0",
        "calculated_at": datetime.utcnow(),
    }


def _format_response(build_id: int, assessment: Dict[str, Any]) -> Dict[str, Any]:
    calculated_at = assessment.get("calculated_at") or datetime.utcnow()
    if isinstance(calculated_at, str):
        calculated_at_iso = calculated_at
    elif isinstance(calculated_at, datetime):
        calculated_at_iso = calculated_at.isoformat()
    else:
        calculated_at_iso = str(calculated_at)

    return {
        "build_id": build_id,
        "risk_score": assessment.get("risk_score", 0.0),
        "uncertainty": assessment.get("uncertainty", 0.0),
        "risk_level": assessment.get("risk_level", "low"),
        "calculated_at": calculated_at_iso,
    }


@router.get("/{build_id}", response_model=RiskScoreResponse)
async def get_risk_score(build_id: int, db: Database = Depends(get_db)):
    build = db.builds.find_one({"_id": build_id})
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    risk_assessment = build.get("risk_assessment")
    if not risk_assessment:
        risk_assessment = _default_risk_assessment()
        db.builds.update_one(
            {"_id": build_id},
            {"$set": {"risk_assessment": risk_assessment}},
        )

    return _format_response(build_id, risk_assessment)


@router.get("/{build_id}/explanation", response_model=RiskExplanationResponse)
async def get_risk_explanation(build_id: int, db: Database = Depends(get_db)):
    build = db.builds.find_one({"_id": build_id})
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    return compute_risk_explanation(build)


@router.post("/{build_id}/recalculate")
async def recalculate_risk_score(build_id: int, db: Database = Depends(get_db)):
    build = db.builds.find_one({"_id": build_id})
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    # TODO: Replace with real Bayesian CNN inference
    new_assessment = {
        "risk_score": 0.42,
        "uncertainty": 0.15,
        "risk_level": "medium",
        "model_version": "mock-0.1.0",
        "calculated_at": datetime.utcnow(),
    }

    db.builds.update_one(
        {"_id": build_id},
        {"$set": {"risk_assessment": new_assessment}},
    )

    return {
        "message": "Risk score recalculated",
        "build_id": build_id,
        "risk_score": new_assessment["risk_score"],
        "uncertainty": new_assessment["uncertainty"],
        "risk_level": new_assessment["risk_level"],
    }
