from pydantic import BaseModel

from app.modules.generation.domain.models import ArtifactType


class GenerateRequest(BaseModel):
    type: ArtifactType
    variant: str | None = None  # dành cho mở rộng; brand_voice tự sinh nhiều variant
