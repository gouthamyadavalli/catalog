import asyncio
import os
from catalog.db import init_db
from catalog.ingest import ingest_fasta
from catalog.search import search_sequences

# Create a dummy FASTA file
TEST_FASTA = "test_data.fasta"

def create_test_data():
    with open(TEST_FASTA, "w") as f:
        f.write(">seq1 original_id=1 description=Alpha variant\n")
        f.write("ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAG\n")
        f.write(">seq2 original_id=2 description=Beta variant\n")
        f.write("ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAA\n") # 1 base difference
        f.write(">seq3 original_id=3 description=Gamma variant\n")
        f.write("GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG\n")

async def main():
    print("--- Genomic Catalog POC Demo ---")
    
    # 1. Initialize DB
    print("\n1. Initializing Database...")
    init_db()
    
    # 2. Create Data
    print("\n2. Creating dummy FASTA file...")
    create_test_data()
    
    # 3. Ingest
    print("\n3. Ingesting Data...")
    await ingest_fasta(TEST_FASTA)
    
    # 4. Search
    print("\n4. Performing Hybrid Search...")
    # Search for something similar to seq1
    query_seq = "ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAG"
    print(f"Query Sequence: {query_seq}")
    
    results = search_sequences(query_sequence=query_seq, limit=2)
    print("\nSearch Results (Vector Similarity):")
    for res in results:
        print(f"ID: {res.id}, Score: {res.score:.4f}, Metadata: {res.metadata}")
        
    # 5. Metadata Filter
    print("\n5. Metadata Filtering...")
    results = search_sequences(metadata_filter="metadata.description LIKE '%Beta%'")
    print("\nFiltered Results:")
    for res in results:
        print(f"ID: {res.id}, Metadata: {res.metadata}")

    # Cleanup
    if os.path.exists(TEST_FASTA):
        os.remove(TEST_FASTA)
    print("\nDemo Complete.")

if __name__ == "__main__":
    asyncio.run(main())
