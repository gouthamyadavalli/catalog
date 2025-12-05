import lancedb
import os
from typing import Optional

DB_PATH = os.getenv("LANCEDB_PATH", "data/lancedb")

def get_db():
    """
    Connect to LanceDB.
    """
    os.makedirs(DB_PATH, exist_ok=True)
    return lancedb.connect(DB_PATH)

def init_db():
    """
    Initialize the database and create tables if they don't exist.
    """
    db = get_db()
    
    # We'll define the schema dynamically or via Pydantic models in the ingestion step,
    # but we can ensure the table exists here if we want a fixed schema start.
    # For this POC, we'll let the first ingestion create the table to demonstrate schema evolution.
    print(f"Connected to LanceDB at {DB_PATH}")
    return db
