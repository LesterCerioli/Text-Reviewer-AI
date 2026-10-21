from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class ComparisonSource(str, Enum):
    
    PUBLIC = "public"
    CUSTOM = "custom"


class SentenceResult(BaseModel):
    
    sentence_id: int = Field(..., description="Unique sentence identifier")
    original_text: str = Field(..., description="Original sentence text")
    is_plagiarized: bool = Field(False, description="Whether plagiarism was detected")
    similarity_score: float = Field(0.0, ge=0.0, le=1.0, description="Similarity score 0-1")
    source_urls: List[str] = Field(default_factory=list, description="Matched source URLs")
    rephrased_text: Optional[str] = Field(None, description="AI-generated rephrased version")
    acceptance_status: bool = Field(
        False, description="Whether user accepted the rephrased version"
    )
    timestamp: Optional[float] = Field(None, description="Processing timestamp")


class DocumentInfo(BaseModel):
    
    filename: str = Field(..., description="Original filename")
    word_count: int = Field(..., description="Approximate word count")
    sentences_extracted: int = Field(
        ..., description="Number of sentences extracted"
    )
    file_path: str = Field(..., description="Temporary file path")


class PlagiarismBatch(BaseModel):
    
    task_id: str = Field(..., description="Unique batch task identifier")
    status: str = Field("processing", description="Current batch status")
    progress: float = Field(0.0, ge=0.0, le=100.0, description="Progress percentage")
    documents_processed: int = Field(
        0, ge=0, description="Number of documents processed"
    )
    total_sentences: int = Field(0, ge=0, description="Total sentences analyzed")
    results: List[SentenceResult] = Field(
        default_factory=list, description="Individual sentence results"
    )
    created_at: Optional[float] = Field(
        None, description="Batch creation timestamp"
    )
    completed_at: Optional[float] = Field(
        None, description="Batch completion timestamp"
    )


class UploadResponse(BaseModel):
    
    task_id: str = Field(..., description="Batch task ID")
    status: str = Field("processing", description="Initial status")
    message: str = Field("", description="Status message")


class BatchStatus(BaseModel):
    
    task_id: str = Field(..., description="Unique batch task identifier")
    status: str = Field("processing", description="Current batch status")
    progress: float = Field(0.0, ge=0.0, le=100.0, description="Progress percentage")
    message: str = Field("", description="Status message")


class BatchExportRequest(BaseModel):
    
    task_id: str = Field(..., description="Batch task ID")
    include_accepted: bool = Field(
        True, description="Include accepted rephrases in export"
    )


class UserCreate(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")
    full_name: Optional[str] = Field(None, description="Full name")


class UserLogin(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: bool = Field(True, description="Whether user is active")