from typing import Dict, List

from pydantic import BaseModel


class BatchLanguageRequest(BaseModel):
    full_names: List[str]
