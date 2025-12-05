from typing import List, Optional
from .db import get_db
from .models import SearchResult
from .ingest import generate_embedding
from .utils import generate_sequence_id, canonicalize_sequence

def search_sequences(
    query_text: Optional[str] = None,
    query_sequence: Optional[str] = None,
    metadata_filter: Optional[str] = None,
    limit: int = 10,
    include_sequence: bool = False
) -> List[SearchResult]:
    """
    Perform a hybrid search:
    - If query_sequence is provided, use vector search.
    - If query_text is provided, we could use full-text search if enabled, 
      or just treat it as a metadata filter or embed it (if multi-modal).
      For this POC, we'll assume query_text might be a description to embed 
      OR just rely on metadata_filter.
    """
    db = get_db()
    tbl = db.open_table("sequences")
    
    query_vec = None
    if query_sequence:
        # Vector search
        canonical_seq = canonicalize_sequence(query_sequence)
        query_vec = generate_embedding(canonical_seq)
    elif query_text:
        # Text-to-vector search (if model supports it, e.g. CLIP-like, or just embed text)
        # For 'all-MiniLM-L6-v2', it embeds text well.
        query_vec = generate_embedding(query_text)
        
    search_builder = tbl.search(query_vec) if query_vec is not None else tbl.search()
    
    if metadata_filter:
        search_builder = search_builder.where(metadata_filter)
        
    search_builder = search_builder.limit(limit)
    
    if not include_sequence:
        search_builder = search_builder.select(["id", "metadata"])
        
    results = search_builder.to_pandas()
    
    output = []
    for _, row in results.iterrows():
        # LanceDB returns '_distance' usually for vector search
        score = 1.0 - row.get('_distance', 0.0) # Convert distance to similarity roughly
        
        output.append(SearchResult(
            id=row['id'],
            score=score,
            metadata=row['metadata'],
            sequence=row.get('sequence') if include_sequence else None
        ))
        
    return output

def get_sequence_by_id(seq_id: str) -> Optional[SearchResult]:
    db = get_db()
    tbl = db.open_table("sequences")
    # Exact lookup
    results = tbl.search().where(f"id = '{seq_id}'").limit(1).to_pandas()
    
    if results.empty:
        return None
        
    row = results.iloc[0]
    return SearchResult(
        id=row['id'],
        score=1.0,
        metadata=row['metadata'],
        sequence=row['sequence']
    )
