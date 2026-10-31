from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MatrixFieldProvenance(BaseModel):
    page: Optional[int] = None
    quote: Optional[str] = None
    confidence: Optional[float] = 1.0


class MatrixEvidenceRow(BaseModel):
    id: Optional[int] = None
    project_id: int
    paper_id: int
    title: str
    doi: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[str] = None
    venue: Optional[str] = None
    access_status: str = "metadata_only"
    has_pdf: bool = False

    # Structured Matrix Dimensions
    objective: Optional[str] = None
    methodology: Optional[str] = None
    datasets: Optional[str] = None
    findings: Optional[str] = None
    limitations: Optional[str] = None

    provenance: Dict[str, Any] = Field(default_factory=dict)
    is_custom_edited: bool = False
    status: str = "pending"  # pending, extracting, completed, failed
    error_message: Optional[str] = None
    updated_at: Optional[str] = None


class MatrixEvidenceUpdate(BaseModel):
    objective: Optional[str] = None
    methodology: Optional[str] = None
    datasets: Optional[str] = None
    findings: Optional[str] = None
    limitations: Optional[str] = None


class ProjectMatrixResponse(BaseModel):
    project_id: int
    project_name: str
    total_papers: int
    extracted_papers: int
    rows: List[MatrixEvidenceRow]


class MatrixExtractRequest(BaseModel):
    paper_ids: Optional[List[int]] = None
    force_reextract: bool = False


class MatrixExtractResponse(BaseModel):
    project_id: int
    total_requested: int
    extracted_count: int
    failed_count: int
    rows: List[MatrixEvidenceRow]
    message: str
