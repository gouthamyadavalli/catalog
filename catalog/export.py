import pyarrow.parquet as pq
import pyarrow as pa
from typing import Optional, List
from .db import get_db
from .embeddings import get_embedding_model
from .utils import canonicalize_sequence

def export_search_results(
    output_path: str,
    query_text: Optional[str] = None,
    query_sequence: Optional[str] = None,
    metadata_filter: Optional[str] = None,
    limit: int = 10000
):
    """
    Execute a search and export results directly to a Parquet file
    using Apache Arrow for zero-copy efficiency.
    """
    db = get_db()
    tbl = db.open_table("sequences") # Default table, can be parameterized if needed
    
    query_vec = None
    if query_sequence:
        canonical_seq = canonicalize_sequence(query_sequence)
        # Use the shared embedding model
        model = get_embedding_model()
        query_vec = model.encode([canonical_seq])[0]
    elif query_text:
        model = get_embedding_model()
        query_vec = model.encode([query_text])[0]
        
    search_builder = tbl.search(query_vec) if query_vec is not None else tbl.search()
    
    if metadata_filter:
        search_builder = search_builder.where(metadata_filter)
        
    search_builder = search_builder.limit(limit)
    
    # Critical optimization: to_arrow() avoids conversion to Python objects/Pandas
    arrow_table = search_builder.to_arrow()
    
    print(f"Exporting {arrow_table.num_rows} rows to {output_path}...")
    pq.write_table(arrow_table, output_path)
    print("Export complete.")
