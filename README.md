# Genomic Catalog - Phylogenetic Tree Search

> **📖 Start Here**: Read the [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) for the high-level narrative: Problem → Architecture → Validation → Scale.

A scalable genomic sequence catalog with **phylogenetic tree search** capabilities. Search across evolutionary trees by structural similarity using vector embeddings.

## 🌳 Live Demo

**Try it now**: [Deploy to Vercel](#-vercel-deployment) and explore phylogenetic tree search!

## 📋 Overview

This POC demonstrates a complete architecture for a genomic catalog system with phylogenetic tree capabilities:

- **Tree Search**: Find evolutionarily similar trees by topology
- **Interactive Visualization**: Click nodes to explore ancestry and descendants
- **Subtree Selection**: Extract and search by subtree patterns
- **Interpretable Results**: Understand *why* trees are similar
- **Scale**: 300M+ sequences with efficient storage and indexing
- **Performance**: Sub-10ms search latency using IVF-PQ quantization

## 🎯 Key Features

### Phylogenetic Tree Capabilities (NEW!)
- **Tree Similarity Search**: Find trees with similar branching patterns
- **Side-by-Side Comparison**: Visualize query vs result trees
- **Interpretability**: Feature-by-feature similarity breakdown
- **Interactive Selection**: Click nodes to select subtrees for search
- **Ancestry Queries**: Find ancestors and descendants of any node

### Core Capabilities
- **FASTA/FASTQ Ingestion**: Parse and store genomic sequences
- **Vector Search**: Similarity search using embeddings (10k+ seq/sec)
- **Metadata Filtering**: SQL-like queries on dynamic metadata
- **Hybrid Search**: Combine vector similarity + metadata filters
- **Bulk Export**: Zero-copy export to Parquet format

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone <repo-url>
cd catalog

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Populate sample data
python scripts/populate_trees.py

# Start the server
uvicorn catalog.main:app --reload

# Open browser to http://127.0.0.1:8000
```

### 🌐 Vercel Deployment

Deploy your own instance in minutes:

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel --prod
   ```

   Or use the deployment script:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

3. **Visit your deployment** - Sample data is automatically populated on first visit!

### Environment Variables (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `LANCEDB_PATH` | Database storage path | `./lancedb_data` |

## 📊 Tree Embedding: How It Works

Trees are encoded as 256-dimensional vectors capturing:

| Feature Group | Dimensions | What It Captures |
|--------------|------------|------------------|
| **Tree Statistics** | 0-31 | Leaf count, node count, depth stats |
| **Depth Histogram** | 32-63 | Distribution of leaves by depth |
| **Subtree Balance** | 64-95 | How evenly the tree splits |
| **Split Patterns** | 96-159 | Branching decisions at each level |
| **Topology Hash** | 160-223 | Canonical structure fingerprint |
| **Branch Lengths** | 224-255 | Evolutionary distance stats |

## 🔬 API Examples

### Search for Similar Trees
```bash
curl -X POST http://localhost:8000/trees/search/similar \
  -H "Content-Type: application/json" \
  -d '{"newick": "((Human,Chimp),(Gorilla,Orangutan));", "limit": 5}'
```

### Get Tree Structure
```bash
curl http://localhost:8000/trees/{tree_id}/structure
```

### Extract Subtree as Newick
```bash
curl http://localhost:8000/trees/{tree_id}/subtree/{node_id}/newick
```

### Explain Similarity
```bash
curl -X POST http://localhost:8000/trees/explain-similarity \
  -H "Content-Type: application/json" \
  -d '{"query_newick": "((A,B),C);", "result_tree_id": "..."}'
```

## 🏗️ Architecture

### Technology Stack

- **Storage**: LanceDB (columnar, vector-native)
- **Vector Search**: Cosine similarity with IVF-PQ indexing
- **API**: FastAPI with async support
- **Frontend**: Vanilla HTML/CSS/JS (modern, responsive)
- **Tree Parsing**: BioPython for Newick format
- **Deployment**: Vercel (serverless Python)

### Project Structure

```
catalog/
├── api/
│   └── index.py          # Vercel serverless entry point
├── catalog/
│   ├── main.py           # FastAPI application
│   ├── tree_embeddings.py # Phylo2Vec encoding
│   ├── tree_search.py    # Tree search algorithms
│   └── tree_db.py        # LanceDB operations
├── static/
│   ├── index.html        # Web UI
│   ├── styles.css        # Styling
│   └── app.js            # Interactive frontend
├── public/               # Vercel static files
├── scripts/
│   └── populate_trees.py # Sample data generator
├── vercel.json           # Vercel configuration
└── requirements.txt      # Python dependencies
```

## 📈 Performance

| Metric | Performance |
|--------|-------------|
| Tree Search (10 results) | ~50ms |
| Tree Ingestion | ~100 trees/sec |
| Embedding Computation | ~10ms/tree |

## 📂 Documentation

- **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)**: High-level narrative
- **[SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)**: Technical deep dive
- **[docs/PHYLOGENETIC_TREE_GUIDE.md](docs/PHYLOGENETIC_TREE_GUIDE.md)**: Tree feature guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details
