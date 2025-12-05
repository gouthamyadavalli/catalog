# Genomic Catalog - System Design Document

## Executive Summary

This document presents a production-ready architecture for a genomic sequence catalog capable of scaling to **300+ million sequences** while supporting:
- Sub-10ms search latency at scale
- Schema evolution without downtime
- Incremental updates without full reindexing
- Multi-modal search (exact, similarity, metadata, hybrid)
- Phylogenetic relationship queries

## Problem Statement

### Core Requirements

**Scale**: 300M+ genomic sequences, growing daily
**Storage**: ~500GB raw data, ~83GB optimized (with quantization)
**Query Types**:
- Exact match (hash-based deduplication)
- Similarity search (k-mer/embedding-based)
- Metadata filtering (dynamic schema)
- Hybrid queries (vector + metadata)
- Lineage traversal (phylogenetic trees)

**Non-Functional Requirements**:
- Search latency: < 10ms p99
- Ingestion throughput: 10k+ sequences/sec
- Zero-downtime schema evolution
- Horizontal scalability
- Cost efficiency

### Key Technical Challenges

1. **Elasticsearch Limitations**:
   - Reindexing hell on schema changes
   - Poor vector search performance at scale
   - Memory explosion with dense vectors
   - Expensive horizontal scaling

2. **Schema Evolution**:
   - Metadata varies by source/lab
   - New fields appear over time
   - Cannot predict schema upfront

3. **Phylogenetic Complexity**:
   - Trees are massive and dynamic
   - Probabilistic ancestry relationships
   - Expensive to query and update

## Proposed Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway / Load Balancer              │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌───────▼────────┐   ┌───────▼────────┐
│  Ingestion     │   │  Search/Query  │   │  Export        │
│  Service       │   │  Service       │   │  Service       │
└───────┬────────┘   └───────┬────────┘   └───────┬────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
┌───────▼────────┐                         ┌───────▼────────┐
│   LanceDB      │                         │   Metadata     │
│   (Vector +    │◄────────────────────────┤   Cache        │
│    Data)       │                         │   (Redis)      │
└───────┬────────┘                         └────────────────┘
        │
        │ (S3-backed storage)
        │
┌───────▼────────────────────────────────────────────────────┐
│              Object Storage (S3 / MinIO)                    │
│  - Lance files (columnar, versioned)                       │
│  - IVF-PQ indices (quantized vectors)                      │
│  - Raw FASTA files (optional archival)                     │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack Justification

#### 1. LanceDB (Core Storage Engine)

**Why LanceDB over Elasticsearch?**

| Requirement | LanceDB | Elasticsearch |
|-------------|---------|---------------|
| Schema Evolution | Native support, no reindex | Requires full reindex |
| Vector Search | Native IVF-PQ, GPU-accelerated | Plugin-based, memory-heavy |
| Storage Format | Columnar (Lance/Arrow) | Row-based JSON |
| Versioning | Zero-copy, Git-like | Not supported |
| Object Storage | Native S3 support | Requires snapshots |
| Cost at 300M | ~$50/month (S3) | ~$5000/month (cluster) |

**Key LanceDB Features**:
- **Append-only architecture**: No rewrite on updates
- **Columnar storage**: 10x compression vs row-based
- **IVF-PQ indexing**: 16x memory reduction with <5% recall loss
- **Zero-copy reads**: Direct S3 reads without ETL
- **ACID transactions**: Consistent reads during writes

#### 2. Embedding Strategy

**Model Selection**:
- **Production**: ESM-2 (650M params) or ProtBERT for protein sequences
- **DNA**: Custom k-mer embedding or fine-tuned DNABERT
- **Dimension**: 384-768 (balance between accuracy and storage)

**Quantization**:
- **Method**: Product Quantization (PQ) with 96 subvectors
- **Compression**: 384 float32 → 96 uint8 (16x reduction)
- **Accuracy**: 95%+ recall@10 maintained

**Inference**:
- **Batching**: Process 1000 sequences/batch
- **GPU**: NVIDIA T4/A10 for 10k seq/sec throughput
- **Caching**: Cache embeddings for frequently accessed sequences

#### 3. Indexing Strategy

**IVF-PQ Parameters** (for 300M sequences):
```python
num_partitions = 65536      # sqrt(300M) ≈ 17k, round up to 64k
num_sub_vectors = 96        # 384 dims / 4 = 96
distance_metric = "cosine"  # Normalized for biological similarity
```

**Index Build**:
- **Initial**: 2-3 hours on 16-core machine
- **Incremental**: Rebuild nightly for new data (<1M sequences)
- **Strategy**: Dual-index pattern (hot + cold)

**Search Flow**:
```
Query → Embed → IVF (coarse search) → PQ (fine search) → Rerank (optional)
  1ms     2ms         1ms                  1ms              2ms
```

### Data Model

#### Sequence Record Schema

```python
{
    "id": "sha256_hash",              # Deterministic, collision-resistant
    "sequence": "ATGC...",            # Raw sequence or S3 pointer
    "embedding": [float] * 384,       # Vector representation
    "metadata": {                     # Flexible, nested structure
        "source": "NCBI",
        "organism": "Homo sapiens",
        "collection_date": "2024-01-15",
        "lab": "Stanford",
        "custom_fields": {...}        # Extensible
    },
    "parent_ids": ["hash1", "hash2"], # Lineage links
    "created_at": "2024-01-15T10:00:00Z",
    "version": 1
}
```

#### Partitioning Strategy

**Horizontal Partitioning** (for >1B sequences):
```
Partition Key: hash(sequence_id) % num_partitions
Partition Size: 10M sequences per partition
Total Partitions: 30 (for 300M)
```

**Benefits**:
- Parallel ingestion across partitions
- Independent index builds
- Fault isolation
- Easy to add partitions

### Phylogenetic Lineage Design

**Challenge**: Representing and querying probabilistic ancestry in massive, dynamic trees.

**Solution**: Hybrid approach

1. **Adjacency List** (in LanceDB):
```python
{
    "sequence_id": "abc123",
    "parent_ids": ["def456", "ghi789"],
    "parent_probabilities": [0.85, 0.15],
    "clade": "B.1.1.7",
    "lineage_path": ["root", "A", "B.1", "B.1.1.7"]
}
```

2. **Graph Database** (Neo4j/DGraph) for complex traversals:
   - Store only topology, not sequence data
   - Optimized for path queries
   - Sync from LanceDB via CDC

3. **Materialized Paths** for common queries:
   - Pre-compute ancestor/descendant sets
   - Store as bitsets for fast intersection
   - Update incrementally

**Query Examples**:
```sql
-- Find all descendants of a sequence
SELECT * WHERE lineage_path LIKE 'root/A/B.1/%'

-- Find common ancestor
SELECT * WHERE id IN (
    SELECT INTERSECT(ancestors(seq1), ancestors(seq2))
)
```

## Scalability Analysis

### Storage Scaling

**300M Sequences**:
```
Raw Vectors:     300M × 384 × 4 bytes = 461 GB
Quantized (PQ):  300M × 96 × 1 byte  = 27 GB
Metadata:        300M × 200 bytes    = 57 GB
Sequences:       300M × 100 bytes    = 29 GB (if stored)
─────────────────────────────────────────────
Total (optimized): ~113 GB
Total (with raw):  ~574 GB
```

**S3 Costs** (us-east-1):
- Storage: $113 × $0.023/GB = **$2.60/month**
- Requests: ~1M GET/month = **$0.40/month**
- **Total: ~$3/month** (vs $5000/month for ES)

### Compute Scaling

**Ingestion** (10k seq/sec target):
```
Bottleneck: Embedding generation
GPU: NVIDIA A10 (24GB VRAM)
Throughput: 10k seq/sec
Cost: $0.75/hour on-demand
Daily ingestion (1M new): 100 seconds = $0.02
```

**Search** (p99 < 10ms):
```
CPU: 16-core server
RAM: 32 GB (for index cache)
Concurrent queries: 1000 QPS
Cost: ~$200/month (reserved instance)
```

### Horizontal Scaling Strategy

**Read Scaling**:
1. Replicate LanceDB tables across regions
2. Use CDN for static index files
3. Cache hot queries in Redis (5-minute TTL)

**Write Scaling**:
1. Partition by hash (30 partitions for 300M)
2. Parallel ingestion workers (1 per partition)
3. Async index updates (batch every 1 hour)

**Scaling Limits**:
- Single LanceDB instance: 1B sequences
- With partitioning: 10B+ sequences
- Search latency: Constant (O(log n) with IVF)

## Schema Evolution Strategy

### Problem
Labs add new metadata fields unpredictably. Traditional databases require:
1. Schema migration
2. Full reindex
3. Downtime

### Solution: LanceDB Schema-on-Read

**Approach**:
```python
# New field appears in data
new_record = {
    "id": "xyz",
    "metadata": {
        "existing_field": "value",
        "new_field": "new_value"  # ← New field
    }
}

# LanceDB handles automatically
table.add([new_record])  # No migration needed!

# Query with new field
table.search().where("metadata.new_field = 'new_value'")
```

**How it works**:
1. Lance uses Arrow schema with nested structs
2. New fields added as nullable columns
3. Old records have NULL for new fields
4. No reindex required (columnar storage)

**Migration Pattern**:
```python
# Optional: Backfill old records
def backfill_new_field():
    for batch in table.to_batches(batch_size=10000):
        # Compute new field from existing data
        batch['metadata']['new_field'] = compute_fn(batch)
        table.update(batch)
```

## Performance Optimizations

### 1. Caching Strategy

**Multi-Level Cache**:
```
L1: In-memory LRU (1GB)  → Hot embeddings
L2: Redis (10GB)         → Query results
L3: S3 (unlimited)       → Cold storage
```

**Cache Keys**:
```python
embedding_cache_key = f"emb:{hash(sequence)}"
query_cache_key = f"query:{hash(query_params)}"
```

### 2. Batch Processing

**Ingestion Pipeline**:
```
FASTA → Parse (1k/batch) → Embed (GPU) → Write (10k/batch) → Index (async)
```

**Search Pipeline**:
```
Query → Embed → IVF (batch 100 queries) → PQ → Rerank
```

### 3. Index Optimization

**Dual-Index Pattern**:
```
Hot Index:  Last 7 days (1M sequences)  → In-memory
Cold Index: Historical (299M sequences) → S3-backed
```

**Query Strategy**:
```python
results = []
results += hot_index.search(query, limit=k)
if len(results) < k:
    results += cold_index.search(query, limit=k - len(results))
return results[:k]
```

## Operational Considerations

### Monitoring

**Key Metrics**:
```
- Ingestion rate (seq/sec)
- Search latency (p50, p95, p99)
- Index freshness (time since last build)
- Cache hit rate
- Error rate by endpoint
```

**Alerting**:
```
- Search p99 > 20ms
- Ingestion rate < 5k/sec
- Index age > 24 hours
- Error rate > 1%
```

### Disaster Recovery

**Backup Strategy**:
1. S3 versioning enabled (30-day retention)
2. Daily snapshots to separate bucket
3. Cross-region replication for critical data

**Recovery Time Objectives**:
- RTO: 1 hour (restore from S3)
- RPO: 1 hour (last index build)

### Cost Analysis

**Monthly Costs** (300M sequences):
```
Storage (S3):           $3
Compute (search):       $200
GPU (ingestion):        $50 (100 hours/month)
Redis (cache):          $30
Monitoring:             $20
─────────────────────────────
Total:                  $303/month
```

**vs Elasticsearch**:
```
3-node cluster (i3.2xlarge): $4,500/month
Snapshot storage:            $500/month
─────────────────────────────
Total:                       $5,000/month
```

**Savings: 94%**

## Production Deployment

### Infrastructure as Code

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: genomic-catalog-search
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: genomic-catalog:latest
        resources:
          requests:
            memory: "32Gi"
            cpu: "8"
        env:
        - name: LANCEDB_URI
          value: "s3://genomic-catalog/lancedb"
        - name: REDIS_URL
          value: "redis://cache:6379"
```

### CI/CD Pipeline

```
Code → Test → Build → Deploy (Blue/Green) → Smoke Test → Switch Traffic
```

**Zero-Downtime Deployment**:
1. Deploy new version to "green" environment
2. Run smoke tests
3. Gradually shift traffic (10% → 50% → 100%)
4. Monitor error rates
5. Rollback if needed (instant)

## Future Enhancements

### 1. Federated Search
- Query across multiple catalogs (NCBI, EBI, private)
- Unified API with source attribution

### 2. Real-time Ingestion
- Kafka/Kinesis for streaming updates
- Sub-second indexing latency

### 3. ML-Powered Features
- Anomaly detection (novel sequences)
- Auto-classification (organism prediction)
- Similarity clustering

### 4. Multi-Region Deployment
- Global read replicas
- Active-active writes with conflict resolution

## Conclusion

This architecture demonstrates:

✅ **Scale**: Handles 300M+ sequences efficiently
✅ **Performance**: Sub-10ms search latency
✅ **Flexibility**: Schema evolution without downtime
✅ **Cost**: 94% cheaper than Elasticsearch
✅ **Reliability**: ACID guarantees, disaster recovery
✅ **Extensibility**: Clear path to 1B+ sequences

The POC implementation validates core assumptions and provides a working reference for production deployment.

## Appendix: Technical Discussion Points

### Trade-offs Made

1. **LanceDB vs Pinecone/Weaviate**:
   - Chose LanceDB for cost and S3 integration
   - Trade-off: Less mature ecosystem

2. **Quantization**:
   - 16x compression with 5% recall loss
   - Acceptable for genomic similarity (not exact match)

3. **Lineage Storage**:
   - Hybrid approach (LanceDB + optional graph DB)
   - Trade-off: Complexity vs query performance

### Alternative Approaches Considered

1. **PostgreSQL + pgvector**:
   - Pros: Mature, ACID, familiar
   - Cons: Poor scaling beyond 10M vectors

2. **Milvus**:
   - Pros: Purpose-built for vectors
   - Cons: Operational complexity, cost

3. **Custom Solution**:
   - Pros: Full control
   - Cons: Engineering effort, maintenance burden

### Open Questions for Discussion

1. What is the expected query pattern distribution?
2. Are there compliance requirements (HIPAA, GDPR)?
3. What is the acceptable staleness for search results?
4. Should we support versioning of sequences?
5. What is the budget for infrastructure?
