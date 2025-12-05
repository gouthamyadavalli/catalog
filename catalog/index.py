import lancedb
from catalog.db import get_db

def create_index(table_name: str = "sequences", metric: str = "cosine"):
    """
    Create an IVF-PQ index on the vector column.
    IVF (Inverted File Index) partitions the space.
    PQ (Product Quantization) compresses the vectors.
    """
    db = get_db()
    if table_name not in db.table_names():
        print(f"Table {table_name} does not exist.")
        return

    tbl = db.open_table(table_name)
    print(f"Creating IVF-PQ index on {table_name}...")
    
    # num_partitions: usually sqrt(num_rows)
    # num_sub_vectors: for PQ, usually dimension / 16 or similar.
    # For POC with small data, we use small defaults.
    # For scale, these should be tuned.
    tbl.create_index(
        metric=metric,
        vector_column_name="embedding",
        num_partitions=256, # Good for up to ~100k-1M rows
        num_sub_vectors=96  # 384 dim / 4 = 96 sub-vectors (4 dims per sub-vector)
    )
    print("Index created successfully.")

if __name__ == "__main__":
    create_index()
