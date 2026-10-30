from typing import Optional, List
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


class PaperUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    authors: Optional[str] = None
    year: Optional[int] = Field(None, ge=1800, le=2100)
    venue: Optional[str] = None
    abstract: Optional[str] = None


class PaperPageResponse(BaseModel):
    id: int
    paper_version_id: int
    page_number: int
    content: str
    character_count: int
    created_at: datetime


class PaperVersionResponse(BaseModel):
    id: int
    paper_id: int
    file_path: str
    file_checksum: str
    file_size_bytes: int
    page_count: int
    extraction_status: str
    error_message: Optional[str] = None
    created_at: datetime


class PaperResponse(PaperCreate):
    id: int
    normalized_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[PaperVersionResponse] = None


class PaperUploadResponse(BaseModel):
    paper: PaperResponse
    version: PaperVersionResponse
    pages_extracted: int
    is_duplicate: bool
    message: str
