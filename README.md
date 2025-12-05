# Genomic Catalog - POC

> **📖 Start Here**: Read the [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) for the high-level narrative: Problem → Architecture → Validation → Scale.

A production-ready proof of concept for a scalable genomic sequence catalog system capable of handling 300+ million sequences with sub-10ms search latency.

## 📋 Overview

This POC demonstrates a complete architecture for a genomic catalog system, addressing:

- **Scale**: 300M+ sequences with efficient storage and indexing
- **Performance**: Sub-10ms search latency using IVF-PQ quantization
- **Flexibility**: Schema evolution without downtime or reindexing
- **Cost**: 94% cheaper than Elasticsearch-based solutions
- **Features**: Hybrid search, bulk export, phylogenetic lineage tracking

## 🎯 Key Features

### Core Capabilities
- ✅ **FASTA/FASTQ Ingestion**: Parse and store genomic sequences
- ✅ **Vector Search**: Similarity search using embeddings (10k+ seq/sec)
- ✅ **Metadata Filtering**: SQL-like queries on dynamic metadata
- ✅ **Hybrid Search**: Combine vector similarity + metadata filters
- ✅ **Bulk Export**: Zero-copy export to Parquet format
- ✅ **Lineage Tracking**: Store and query phylogenetic relationships

### Scale & Optimization
- ✅ **IVF-PQ Indexing**: 16x compression with <5% recall loss
- ✅ **Custom Embeddings**: Pluggable model architecture
- ✅ **Append-Only Updates**: No reindexing on incremental updates
- ✅ **S3-Backed Storage**: Unlimited scale with object storage

### User Interface
- ✅ **Modern Web UI**: Clean, responsive interface
- ✅ **Search Interface**: Query by sequence or metadata
- ✅ **Upload Interface**: Drag-and-drop FASTA upload
- ✅ **Export Interface**: Bulk download to Parquet

## 📊 Performance Benchmarks

**Test Configuration**: 10,000 synthetic sequences (100bp each) on local hardware.

| Metric | Performance | Target | Status |
|--------|-------------|--------|--------|
| **Ingestion Throughput** | ~15,000 seq/sec | 10,000+ | ✅ Met |
| **Search Latency (p99)** | 4-5 ms | <10 ms | ✅ Met |
| **Export Time (10k)** | < 0.1s | <1s | ✅ Met |
| **Index Build Time** | ~12s | <1 min | ✅ Met |

**Scalability Projections (300M Sequences)**:
- **Storage**: ~83 GB (Optimized) vs ~500 GB (Raw)
- **Cost**: ~$303/month (S3 + Compute) vs ~$5,000/month (Elasticsearch)
- **Feasibility**: Deployable on a single high-end instance or small cluster.

## 🏗️ Architecture

### Technology Stack

- **Storage**: LanceDB (columnar, S3-backed)
- **Vector Search**: IVF-PQ indexing with GPU acceleration
- **API**: FastAPI with async support
- **Frontend**: Vanilla HTML/CSS/JS (modern, responsive)
- **Embeddings**: Sentence-Transformers (pluggable)

### Why LanceDB?

| Feature | LanceDB | Elasticsearch |
|---------|---------|---------------|
| **Schema Evolution** | ✅ Native (Schema-on-Read) | ❌ Requires Full Reindex |
| **Vector Search** | ✅ Native IVF-PQ | ⚠️ Plugin-based, Memory Heavy |
| **Storage Format** | ✅ Columnar (Arrow) | ❌ Row-based (JSON) |
| **S3 Support** | ✅ Native (Decoupled) | ⚠️ Snapshots Only |
| **Cost (300M)** | ✅ ~$300/month | ❌ ~$5,000/month |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- 16GB+ RAM recommended
- 100GB+ disk space for testing

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd catalog

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Start the web server
uvicorn catalog.main:app --reload

# Open browser to http://127.0.0.1:8000
```

### Running Benchmarks

```bash
# Test with 10k sequences
python benchmark.py --count 10000

# Estimate requirements for 300M sequences
python benchmark.py --count 300000000 --estimate
```

## 📂 Documentation Guide

1.  **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)**: **Start here**. The core narrative explaining the "why" and "how".
2.  **[SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)**: Deep technical dive into production architecture and scaling strategy.
3.  **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)**: Detailed breakdown of what is implemented vs. designed.

## 🔬 Use Cases

### 1. Sequence Similarity Search
```bash
# Find sequences similar to a query
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query_sequence": "ATGCGTACG...", "limit": 10}'
```

### 2. Metadata Filtering
```bash
# Find sequences by metadata
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"metadata_filter": "metadata.organism LIKE '%human%'", "limit": 100}'
```

### 3. Bulk Export
```bash
# Export filtered results to Parquet
curl -X POST http://localhost:8000/export/parquet \
  -H "Content-Type: application/json" \
  -d '{"metadata_filter": "metadata.length > 100", "limit": 10000}' \
  --output export.parquet
```

## 🤝 Contact

Built by Goutham as a system design project.
