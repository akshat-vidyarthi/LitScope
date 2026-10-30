from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the research project")
    description: Optional[str] = Field(None, description="Overview of the project")
    research_question: Optional[str] = Field(None, description="Primary research question")
    scope: Optional[str] = Field(None, description="Scope boundaries, e.g. 2018-2025 data analytics")
    inclusion_criteria: Optional[str] = Field(None, description="Inclusion criteria for papers")
    exclusion_criteria: Optional[str] = Field(None, description="Exclusion criteria for papers")


class ProjectResponse(ProjectCreate):
    id: int
    owner_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProjectPaperLink(BaseModel):
    paper_id: int
    inclusion_status: str = Field("included", description="Status: included, candidate, or excluded")
    notes: Optional[str] = Field(None, description="Researcher notes for this paper in this project")


class CuratedPaperResponse(BaseModel):
    link_id: int
    project_id: int
    paper_id: int
    title: str
    doi: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[str] = None
    inclusion_status: str
    notes: Optional[str] = None
    date_added: datetime
