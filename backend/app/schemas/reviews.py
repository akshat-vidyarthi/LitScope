from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ReviewReference(BaseModel):
    ref_index: int
    paper_id: int
    title: str
    authors: Optional[str] = None
    year: Optional[int] = None
    citation_label: str
    doi: Optional[str] = None


class LiteratureReviewGenerateRequest(BaseModel):
    target_word_count: int = Field(
        default=350,
        ge=100,
        le=2500,
        description="Target word count for the continuous literature review narrative"
    )


class LiteratureReviewResponse(BaseModel):
    id: int
    project_id: int
    target_word_count: int
    actual_word_count: int
    review_text: str
    paper_references: List[ReviewReference]
    created_at: datetime


class LiteratureReviewListResponse(BaseModel):
    current_review: Optional[LiteratureReviewResponse] = None
    history: List[LiteratureReviewResponse] = []
    papers_count: int = 0
