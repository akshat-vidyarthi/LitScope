from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class DiscoveredPaper(BaseModel):
    id: str
    source: Literal["openalex", "arxiv", "crossref", "scopus"] = "openalex"
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    citation_count: int = 0
    landing_page_url: Optional[str] = None
    pdf_url: Optional[str] = None
    is_open_access: bool = False
    in_library: bool = False


class DiscoverySearchResponse(BaseModel):
    query: str
    provider: str
    total_results: int
    results: List[DiscoveredPaper]


class DiscoveryImportRequest(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    source_url: Optional[str] = None
    pdf_url: Optional[str] = None
    project_id: Optional[int] = None


class DiscoveryImportResponse(BaseModel):
    paper_id: int
    title: str
    doi: Optional[str] = None
    pdf_downloaded: bool
    page_count: int = 0
    chunks_created: int = 0
    project_linked: bool = False
    message: str
