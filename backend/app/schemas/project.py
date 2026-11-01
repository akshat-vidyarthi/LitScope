from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the research project")
    description: Optional[str] = Field(None, description="Overview of the project")
    research_question: Optional[str] = Field(None, description="Primary research question")
    scope: Optional[str] = Field(None, description="Scope boundaries, e.g. 2018-2025 data analytics")
    inclusion_criteria: Optional[str] = Field(None, description="Inclusion criteria for papers")
    exclusion_criteria: Optional[str] = Field(None, description="Exclusion criteria for papers")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Name of the research project")
    description: Optional[str] = Field(None, description="Overview of the project")
    research_question: Optional[str] = Field(None, description="Primary research question")
    scope: Optional[str] = Field(None, description="Scope boundaries")
    inclusion_criteria: Optional[str] = Field(None, description="Inclusion criteria for papers")
    exclusion_criteria: Optional[str] = Field(None, description="Exclusion criteria for papers")


class ProjectResponse(ProjectCreate):
    id: int
    owner_id: Optional[int] = None
    member_count: Optional[int] = 0
    current_user_role: Optional[str] = None
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
    username: Optional[str] = Field(None, description="Username of the user to invite/add")
    email: Optional[str] = Field(None, description="Email of the user to invite/add (alternative)")
    role: str = Field("viewer", description="Role to assign: editor or viewer")

    @model_validator(mode="after")
    def ensure_member_ident(self):
        if not self.username and not self.email:
            raise ValueError("Either username or email must be provided.")
        if not self.username and self.email:
            self.username = self.email
        return self


class ProjectMemberUpdate(BaseModel):
    role: str = Field(..., description="Role to assign: editor or viewer")


class ProjectMemberResponse(BaseModel):
    membership_id: int
    project_id: int
    user_id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    created_at: datetime


class RetrievalQuery(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="Research question or topic to search")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of relevant chunks to retrieve")
    paper_id: Optional[int] = Field(default=None, description="Optional paper ID to restrict retrieval to a single paper")


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
    limit: Optional[int] = Field(default=None, description="Alias for top_k")
    paper_id: Optional[int] = Field(default=None, description="Optional paper ID to restrict retrieval to a single paper")

    @model_validator(mode="before")
    @classmethod
    def resolve_top_k(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "top_k" not in values and "limit" in values and values["limit"] is not None:
                values["top_k"] = values["limit"]
        return values


class ProjectQueryResponse(BaseModel):
    id: int
    project_id: int
    question: str
    answer: str
    citations: list[str]
    retrieved_chunks: list[RetrievedChunkResponse]
    created_at: datetime
