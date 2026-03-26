from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    type: str
    original_url: str | None
    processed_url: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
