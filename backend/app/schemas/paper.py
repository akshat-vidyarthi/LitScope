from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class PaperCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Full title of the paper")
    doi: Optional[str] = Field(None, max_length=255, description="Digital Object Identifier")
    authors: Optional[str] = Field(None, description="Comma-separated authors or string")
    year: Optional[int] = Field(None, ge=1800, le=2100, description="Publication year")
    venue: Optional[str] = Field(None, description="Journal or conference name")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    source_url: Optional[str] = Field(None, description="URL or source repository")
    access_status: str = Field("metadata_only", description="metadata_only, abstract_only, full_text_available")


class PaperResponse(PaperCreate):
    id: int
    normalized_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
