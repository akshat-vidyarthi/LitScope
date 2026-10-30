from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


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
    member_count: Optional[int] = 0
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


class ProjectMemberAdd(BaseModel):
    email: EmailStr = Field(..., description="Email of the user to invite/add")
    role: str = Field("viewer", description="Role to assign: editor or viewer")


class ProjectMemberUpdate(BaseModel):
    role: str = Field(..., description="Role to assign: editor or viewer")


class ProjectMemberResponse(BaseModel):
    membership_id: int
    project_id: int
    user_id: int
    email: str
    full_name: Optional[str] = None
    role: str
    created_at: datetime


class RetrievalQuery(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="Research question or topic to search")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of relevant chunks to retrieve")


class RetrievedChunkResponse(BaseModel):
    chunk_id: int
    paper_id: int
    paper_title: str
    paper_authors: Optional[str] = None
    paper_year: Optional[int] = None
    page_number: int
    content: str
    score: float
    citation: str


class ProjectAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000, description="Research question to ask about project papers")
    top_k: int = Field(default=5, ge=1, le=15, description="Number of supporting passages to retrieve")


class ProjectQueryResponse(BaseModel):
    id: int
    project_id: int
    question: str
    answer: str
    citations: list[str]
    retrieved_chunks: list[RetrievedChunkResponse]
    created_at: datetime
