from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    category: str = Field(..., max_length=50)
    fabric: str = Field(..., max_length=200)
    notes: str | None = Field(None, max_length=1000)


class ProductResponse(BaseModel):
    id: UUID
    name: str
    category: str
    fabric: str
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
