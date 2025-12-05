from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class SequenceMetadata(BaseModel):
    source: str
    collection_date: Optional[str] = None
    organism: Optional[str] = None
    # Allow extra fields for schema evolution
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"

class SequenceRecord(BaseModel):
    id: str
    sequence: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    parent_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

class SearchQuery(BaseModel):
    query_text: Optional[str] = None
    query_sequence: Optional[str] = None
    metadata_filter: Optional[str] = None # SQL-like filter string
    limit: int = 10
    include_sequence: bool = False

class SearchResult(BaseModel):
    id: str
    score: float
    metadata: Dict[str, Any]
    sequence: Optional[str] = None
