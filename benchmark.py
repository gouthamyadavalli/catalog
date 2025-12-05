import asyncio
import time
import random
import string
import os
import argparse
import numpy as np
from catalog.db import get_db, init_db
from catalog.ingest import ingest_fasta
from catalog.search import search_sequences
from catalog.index import create_index
from catalog.embeddings import get_embedding_model
from catalog.export import export_search_results

# Configuration
SEQ_LENGTH = 100

def generate_random_sequence(length: int) -> str:
    return ''.join(random.choices('ACGT', k=length))

def create_synthetic_fasta(filename: str, num_sequences: int):
    print(f"Generating {num_sequences} sequences into {filename}...")
    with open(filename, "w") as f:
        for i in range(num_sequences):
            seq = generate_random_sequence(SEQ_LENGTH)
            f.write(f">seq_{i} synthetic sequence {i}\n")
            f.write(f"{seq}\n")

def estimate_requirements(num_sequences: int, dim: int = 384):
    print(f"\n--- Feasibility Estimate for {num_sequences:,} Sequences ---")
    
    # Storage
    # 1. Raw Vectors (Float32)
    raw_vec_size_gb = (num_sequences * dim * 4) / (1024**3)
    
    # 2. Quantized Vectors (IVF-PQ, assuming 16x compression roughly, or 1 byte/dim/subvec)
    # LanceDB PQ usually reduces to uint8 per subvector.
    # If we use 96 subvectors (384/4), it's 96 bytes per vector.
    pq_vec_size_gb = (num_sequences * 96) / (1024**3)
    
    # 3. Data Storage (Sequence + Metadata)
    # Assume ~200 bytes per record compressed (Lance is efficient)
    data_size_gb = (num_sequences * 200) / (1024**3)
    
    total_disk_gb = pq_vec_size_gb + data_size_gb # We mostly query PQ, raw might be kept or not depending on config
    
    print(f"Embedding Dimension: {dim}")
    print(f"Estimated Raw Vector Size: {raw_vec_size_gb:.2f} GB")
    print(f"Estimated Quantized Index Size: {pq_vec_size_gb:.2f} GB")
    print(f"Estimated Data Storage (Seq+Meta): {data_size_gb:.2f} GB")
    print(f"Total Disk Required (approx): {total_disk_gb:.2f} GB")
    
    # Memory
    # LanceDB is disk-based, but index cache helps.
    # Minimum RAM: Enough to hold the IVF centroids + some buffer.
    # Recommended RAM: ~10-20% of index size for fast search.
    print(f"Recommended RAM: {pq_vec_size_gb * 0.2:.2f} GB - {pq_vec_size_gb:.2f} GB")
    print("------------------------------------------------")

async def benchmark(num_sequences: int):
    print(f"--- Genomic Catalog Scale Benchmark ({num_sequences} seqs) ---")
    
    # Use Mock model for speed in benchmark
    get_embedding_model("mock")
    
    init_db()
    
    # 1. Ingestion
    fasta_file = "benchmark_data.fasta"
    create_synthetic_fasta(fasta_file, num_sequences)
    
    start_time = time.time()
    await ingest_fasta(fasta_file, table_name="benchmark_sequences")
    end_time = time.time()
    
    duration = end_time - start_time
    print(f"\nIngestion Time: {duration:.2f}s")
    print(f"Throughput: {num_sequences / duration:.2f} seq/sec")
    
    # 2. Indexing (Quantization)
    print("\nCreating IVF-PQ Index...")
    start_time = time.time()
    create_index("benchmark_sequences")
    end_time = time.time()
    print(f"Indexing Time: {end_time - start_time:.2f}s")
    
    # 3. Search
    print("\nBenchmarking Search (100 queries)...")
    queries = [generate_random_sequence(SEQ_LENGTH) for _ in range(100)]
    
    db = get_db()
    tbl = db.open_table("benchmark_sequences")
    model = get_embedding_model()
    
    latencies = []
    for q in queries:
        q_start = time.time()
        vec = model.encode([q])[0]
        tbl.search(vec).limit(10).to_pandas()
        latencies.append(time.time() - q_start)
        
    avg_latency = sum(latencies) / len(latencies) * 1000
    print(f"Average Search Latency: {avg_latency:.2f} ms")
    
    # 4. Export Benchmark
    print("\nBenchmarking Bulk Export (10,000 records)...")
    export_file = "benchmark_export.parquet"
    start_time = time.time()
    # Export all records (limit=NUM_SEQUENCES)
    # We use a dummy query vector (all zeros or random) just to get results, or just filter everything
    # For simplicity, we'll just search with a random vector and high limit
    export_search_results(export_file, query_sequence=generate_random_sequence(SEQ_LENGTH), limit=10000)
    end_time = time.time()
    print(f"Export Time: {end_time - start_time:.2f}s")
    
    # Cleanup
    import os
    if os.path.exists(fasta_file):
        os.remove(fasta_file)
    if os.path.exists(export_file):
        os.remove(export_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10000, help="Number of sequences to benchmark")
    parser.add_argument("--estimate", action="store_true", help="Estimate requirements for --count instead of running")
    args = parser.parse_args()
    
    if args.estimate:
        estimate_requirements(args.count)
    else:
        asyncio.run(benchmark(args.count))
