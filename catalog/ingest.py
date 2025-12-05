import asyncio
from typing import List, Dict, Any
from Bio import SeqIO
from sentence_transformers import SentenceTransformer
import pandas as pd
import numpy as np
from .db import get_db
from .models import SequenceRecord
from .utils import generate_sequence_id, canonicalize_sequence
from .embeddings import get_embedding_model

def generate_embedding(text: str) -> List[float]:
    # Use the shared embedding model
    model = get_embedding_model()
    # Batch encoding is more efficient, but for single items we wrap in list
    return model.encode([text[:512]])[0]

async def ingest_fasta(file_path: str, table_name: str = "sequences"):
    """
    Ingest a FASTA file into LanceDB.
    """
    db = get_db()
    records = []
    
    print(f"Parsing {file_path}...")
    for record in SeqIO.parse(file_path, "fasta"):
        seq_str = str(record.seq)
        canonical_seq = canonicalize_sequence(seq_str)
        seq_id = generate_sequence_id(canonical_seq)
        
        # Extract metadata from header
        # FASTA headers are often "id description"
        metadata = {
            "description": record.description,
            "original_id": record.id,
            "length": len(seq_str)
        }
        
        embedding = generate_embedding(canonical_seq)
        
        seq_record = SequenceRecord(
            id=seq_id,
            sequence=canonical_seq,
            metadata=metadata,
            embedding=embedding
        )
        records.append(seq_record.model_dump())
        
        if len(records) >= 100:
            _batch_insert(db, table_name, records)
            records = []
            
    if records:
        _batch_insert(db, table_name, records)
    
    print(f"Ingestion complete for {file_path}")

def _batch_insert(db, table_name, records: List[Dict[str, Any]]):
    df = pd.DataFrame(records)
    
    # Flatten metadata for LanceDB querying if desired, or keep as struct.
    # LanceDB handles nested structs well.
    
    if table_name in db.table_names():
        tbl = db.open_table(table_name)
        tbl.add(records)
    else:
        # Create table with the first batch
        db.create_table(table_name, data=records)
    print(f"Inserted batch of {len(records)} records.")
