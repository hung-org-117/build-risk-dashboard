from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.api.auth import get_current_user
from app.database.mongo import get_db
from app.dtos.preprocessing import (
    NormalizationPreviewRequest,
    NormalizationPreviewResponse,
)
from app.services.preprocessing_service import PreprocessingService

router = APIRouter(
    prefix="/datasets/{dataset_id}/versions/{version_id}/preprocess", tags=["preprocessing"]
)


@router.post("/preview", response_model=NormalizationPreviewResponse)
async def preview_normalization(
    dataset_id: str,
    version_id: str,
    request: NormalizationPreviewRequest,
    db: Database = Depends(get_db),
    current_user=Depends(get_current_user),
) -> NormalizationPreviewResponse:
    """
    Preview normalization transformation on selected features.

    Returns before/after samples and statistics for each feature.
    """
    service = PreprocessingService(db)
    return service.preview_normalization(
        dataset_id=dataset_id,
        version_id=version_id,
        method=request.method,
        features=request.features,
        sample_size=request.sample_size,
    )
