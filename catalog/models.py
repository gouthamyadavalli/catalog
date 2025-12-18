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


# ============== Phylogenetic Tree Models ==============

class TreeNode(BaseModel):
    """Represents a node in a phylogenetic tree."""
    id: str
    tree_id: str
    name: Optional[str] = None  # Label for the node (often for leaves)
    sequence_id: Optional[str] = None  # Link to sequences table (for leaves)
    parent_id: Optional[str] = None  # Parent node ID (null for root)
    left_child_id: Optional[str] = None  # Left child (binary tree)
    right_child_id: Optional[str] = None  # Right child (binary tree)
    depth: int = 0  # Distance from root (in edges)
    branch_length: float = 0.0  # Evolutionary distance to parent
    is_leaf: bool = False
    position_embedding: Optional[List[float]] = None  # Encodes position in tree
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PhyloTree(BaseModel):
    """Represents a complete phylogenetic tree."""
    id: str
    name: str
    newick: str  # Original Newick format string
    embedding: Optional[List[float]] = None  # Phylo2Vec encoding
    num_leaves: int = 0
    num_nodes: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class TreeNodeResponse(BaseModel):
    """Response model for tree node queries."""
    id: str
    name: Optional[str] = None
    depth: int
    branch_length: float
    is_leaf: bool
    sequence_id: Optional[str] = None
    children_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PhyloTreeResponse(BaseModel):
    """Response model for tree queries."""
    id: str
    name: str
    num_leaves: int
    num_nodes: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AncestryResponse(BaseModel):
    """Response model for ancestry queries."""
    node_id: str
    ancestors: List[TreeNodeResponse]
    path_length: int  # Total edges from node to root


class DescendantsResponse(BaseModel):
    """Response model for descendant queries."""
    node_id: str
    descendants: List[TreeNodeResponse]
    total_count: int


class TreeSearchQuery(BaseModel):
    """Query model for tree similarity search."""
    newick: Optional[str] = None  # Search by tree structure
    tree_id: Optional[str] = None  # Find similar to existing tree
    limit: int = 10


class TreeSearchResult(BaseModel):
    """Result model for tree similarity search."""
    tree: PhyloTreeResponse
    score: float
