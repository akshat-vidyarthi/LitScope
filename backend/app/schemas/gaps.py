from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    paper_id: int
    paper_title: str
    quote: str
    page_number: Optional[int] = None
    section: Optional[str] = None


class CounterEvidenceItem(BaseModel):
    paper_id: int
    paper_title: str
    quote: str
    page_number: Optional[int] = None
    explanation: Optional[str] = None


class ResearchGapResponse(BaseModel):
    id: int
    project_id: int
    paper_id: Optional[int] = None
    paper_title: Optional[str] = None
    gap_title: str
    gap_type: str  # methodological, dataset_context, contradiction, author_stated_limitation
    description: str
    confidence_status: str  # supported_within_collection, tentative_candidate, insufficient_evidence
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    counterevidence: List[CounterEvidenceItem] = Field(default_factory=list)
    review_status: str  # pending, validated, dismissed, refined
    researcher_notes: Optional[str] = None
    refined_question: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ResearchGapUpdate(BaseModel):
    review_status: Optional[str] = None
    researcher_notes: Optional[str] = None
    refined_question: Optional[str] = None


class ResearchGapCreate(BaseModel):
    paper_id: int
    gap_title: str
    gap_type: str
    description: Optional[str] = ""
    confidence_status: Optional[str] = "supported_within_collection"
    supporting_evidence: Optional[List[EvidenceItem]] = Field(default_factory=list)
    counterevidence: Optional[List[CounterEvidenceItem]] = Field(default_factory=list)
    researcher_notes: Optional[str] = None
    refined_question: Optional[str] = None


class GapAnalysisSummaryResponse(BaseModel):
    project_id: int
    papers_count: int
    pages_count: int
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    gaps: List[ResearchGapResponse] = Field(default_factory=list)
    total_gaps: int
    validated_count: int
    pending_count: int
    dismissed_count: int
