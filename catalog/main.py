from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
import shutil
import os
import tempfile
from .models import SearchResult, SearchQuery
from .ingest import ingest_fasta
from .search import search_sequences, get_sequence_by_id
from .export import export_search_results
from .db import init_db

app = FastAPI(title="Genomic Catalog POC")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/ingest/fasta")
async def ingest_fasta_endpoint(file: UploadFile = File(...)):
    """
    Upload and ingest a FASTA file.
    """
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".fasta") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    try:
        await ingest_fasta(tmp_path)
        return {"message": f"Successfully ingested {file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(tmp_path)

@app.post("/search", response_model=List[SearchResult])
async def search_endpoint(query: SearchQuery):
    """
    Hybrid search endpoint.
    """
    results = search_sequences(
        query_text=query.query_text,
        query_sequence=query.query_sequence,
        metadata_filter=query.metadata_filter,
        limit=query.limit,
        include_sequence=query.include_sequence
    )
    return results

@app.get("/sequence/{seq_id}", response_model=SearchResult)
async def get_sequence_endpoint(seq_id: str):
    """
    Get a specific sequence by ID.
    """
    result = get_sequence_by_id(seq_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return result

@app.get("/lineage/{seq_id}/ancestors")
async def get_ancestors(seq_id: str):
    """
    Get ancestors of a sequence (mock implementation for POC).
    In a real system, this would traverse the 'parent_ids' recursively.
    """
    # For POC, we just return the immediate parents if they exist in the DB
    seq = get_sequence_by_id(seq_id)
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    parents = seq.metadata.get("parent_ids", [])
    # If parent_ids is not in metadata, check if we added it to the model explicitly (we did in SequenceRecord but maybe not ingested from FASTA)
    # For this POC, we assume parent_ids might be in metadata or we'd need to ingest it specifically.
    
    return {"id": seq_id, "parents": parents}

@app.post("/export/parquet")
async def export_endpoint(query: SearchQuery):
    """
    Export search results to Parquet file.
    """
    output_path = f"temp_export_{os.getpid()}.parquet"
    try:
        export_search_results(
            output_path,
            query_text=query.query_text,
            query_sequence=query.query_sequence,
            metadata_filter=query.metadata_filter,
            limit=query.limit
        )
        return FileResponse(
            output_path,
            media_type="application/octet-stream",
            filename=f"genomic_export.parquet"
        )
    finally:
        # Cleanup happens after response is sent
        if os.path.exists(output_path):
            os.remove(output_path)
