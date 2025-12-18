# Phylogenetic Tree Search Guide

This guide explains how to use the phylogenetic tree search features, how the embeddings work, and best practices for searching evolutionary relationships.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding Phylogenetic Trees](#understanding-phylogenetic-trees)
3. [How Embeddings Work](#how-embeddings-work)
4. [Search Strategies](#search-strategies)
5. [Query Format Reference](#query-format-reference)
6. [API Reference](#api-reference)
7. [Example Use Cases](#example-use-cases)

---

## Quick Start

### Adding a Tree

```bash
# Via API
curl -X POST http://localhost:8000/trees/ingest \
  -H "Content-Type: application/json" \
  -d '{"newick": "((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);", "name": "My Tree"}'

# Via Web UI
# 1. Navigate to http://localhost:8000
# 2. Click "Phylogenetic Trees" tab
# 3. Paste Newick string and enter a name
# 4. Click "Add Tree"
```

### Searching for Similar Trees

```bash
curl -X POST http://localhost:8000/trees/search/similar \
  -H "Content-Type: application/json" \
  -d '{"newick": "((A:0.1,B:0.2):0.3,C:0.5);", "limit": 5}'
```

### Finding Ancestors

```bash
curl "http://localhost:8000/trees/{tree_id}/ancestors/{node_id}"
```

---

## Understanding Phylogenetic Trees

### What is a Phylogenetic Tree?

A phylogenetic tree represents evolutionary relationships between biological entities (species, genes, proteins, etc.). Key concepts:

```
        (Root) ─────── Common ancestor
       /      \
    (node)   (node) ── Internal nodes (hypothetical ancestors)
    /    \    /    \
   A     B   C      D ── Leaves (observed species/sequences)
```

### Newick Format

The **Newick format** is the standard way to represent trees as text:

```
((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);
```

Breaking it down:
- **Parentheses** `()` group related nodes (siblings)
- **Commas** `,` separate siblings
- **Colons** `:` precede branch lengths
- **Semicolon** `;` ends the tree

**Examples:**

| Newick | Description |
|--------|-------------|
| `(A,B);` | Simple tree: A and B share a parent |
| `(A:0.1,B:0.2);` | With branch lengths |
| `((A,B),(C,D));` | Nested: (A,B) and (C,D) are sister groups |
| `((A,B)X,(C,D)Y)Z;` | With internal node labels |

### Tree Types in This System

| Tree Type | Example | Use Case |
|-----------|---------|----------|
| **Species trees** | Great Apes, Mammals | Evolutionary relationships |
| **Variant trees** | SARS-CoV-2, Influenza | Tracking pathogen evolution |
| **Gene trees** | 16S rRNA | Molecular phylogenetics |
| **Haplogroup trees** | Human mtDNA | Population genetics |

---

## How Embeddings Work

### Overview

We use two types of embeddings to enable similarity search:

```
┌─────────────────────────────────────────────────────────────┐
│                    TREE EMBEDDING                            │
│   (Phylo2Vec: Captures overall tree topology)                │
│   Dimension: 256                                             │
│   Used for: Finding trees with similar structure             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   NODE EMBEDDINGS                            │
│   (Position Encoding: Captures location in tree)             │
│   Dimension: 64                                              │
│   Used for: Finding nodes at similar positions               │
└─────────────────────────────────────────────────────────────┘
```

### 1. Tree-Level Embedding (Phylo2Vec)

**Purpose**: Encode the entire tree structure into a fixed-size vector for similarity comparison.

**How it works**:
```
Input Tree: ((A,B),(C,D));

1. Parse tree structure
2. For each internal node (post-order traversal):
   - Encode the subtree topology
   - Record minimum leaf index in each subtree
3. Normalize to unit vector

Output: [0.23, 0.45, 0.12, ...] (256 dimensions)
```

**What it captures**:
- Tree topology (branching pattern)
- Relative positions of leaves
- Structural symmetry

**Similarity metric**: Cosine similarity
```
similarity = dot(tree1_embedding, tree2_embedding)
             ─────────────────────────────────────
             ||tree1_embedding|| × ||tree2_embedding||
```

### 2. Node-Level Embedding (Position Encoding)

**Purpose**: Encode each node's position for finding similar nodes across trees.

**Components**:
```
Node Embedding (64 dims) = [
    Depth Encoding (16 dims)     # Distance from root
  + Path Encoding (32 dims)      # Left/right decisions from root
  + Branch Length Encoding (16 dims)  # Evolutionary distance
]
```

**Depth Encoding** (Sinusoidal):
```python
for i in range(16):
    encoding[i] = sin(depth * exp(-i * log(10000) / 16))
    encoding[i+1] = cos(depth * exp(-i * log(10000) / 16))
```

**Path Encoding**:
```
Root → Left → Right → Left = [0, 1, 0]
Hashed and spread across 32 dimensions
```

### Embedding Visualization

```
Tree: ((Human,Chimp),(Gorilla,Orangutan));

Tree Embedding (captures topology):
[████████████████░░░░░░░░░░░░░░░░] → Similar to other 4-leaf binary trees

Node Embeddings:
  Root:       [░░░░░░░░░░] depth=0, path=[]
  ├─ Node1:   [██░░░░░░░░] depth=1, path=[L]
  │  ├─ Human:    [████░░░░░░] depth=2, path=[L,L]
  │  └─ Chimp:    [████░░░░░░] depth=2, path=[L,R]
  └─ Node2:   [██░░░░░░░░] depth=1, path=[R]
     ├─ Gorilla:  [████░░░░░░] depth=2, path=[R,L]
     └─ Orangutan:[████░░░░░░] depth=2, path=[R,R]
```

---

## Search Strategies

### 1. Find Similar Trees by Topology

**Use case**: "Find trees with a similar branching pattern"

**Method**: Search using Phylo2Vec embeddings

```bash
# Search by providing a query tree
curl -X POST http://localhost:8000/trees/search/similar \
  -H "Content-Type: application/json" \
  -d '{"newick": "((A,B),(C,D));", "limit": 10}'

# Or by referencing an existing tree
curl -X POST http://localhost:8000/trees/search/similar \
  -H "Content-Type: application/json" \
  -d '{"tree_id": "existing-tree-uuid", "limit": 10}'
```

**How it works**:
1. Query tree → Phylo2Vec embedding
2. Vector similarity search in LanceDB
3. Return top-k most similar trees

### 2. Traverse Ancestry

**Use case**: "Find all ancestors of a species back to the root"

```bash
# Get all ancestors
curl "http://localhost:8000/trees/{tree_id}/ancestors/{node_id}"

# Limit depth (e.g., only 2 generations)
curl "http://localhost:8000/trees/{tree_id}/ancestors/{node_id}?max_depth=2"
```

### 3. Find Descendants

**Use case**: "Find all species that descended from this ancestor"

```bash
# Get all descendants
curl "http://localhost:8000/trees/{tree_id}/descendants/{node_id}"

# Only leaf nodes (actual species, not internal ancestors)
curl "http://localhost:8000/trees/{tree_id}/descendants/{node_id}?leaves_only=true"
```

### 4. Find Common Ancestor

**Use case**: "When did Human and Gorilla diverge?"

```bash
curl "http://localhost:8000/trees/{tree_id}/lca?node1={human_id}&node2={gorilla_id}"
```

**Returns**: The Lowest Common Ancestor (LCA) - the most recent ancestor shared by both.

### 5. Find Related Sequences

**Use case**: "Find sequences evolutionarily close to this node"

```bash
# Within 3 edges
curl "http://localhost:8000/trees/{tree_id}/related-sequences/{node_id}?max_distance=3"
```

---

## Query Format Reference

### User Query → System Query Mapping

Since phylogenetic queries are often expressed in natural language, here's how to translate them:

| Natural Language Query | API Endpoint | Parameters |
|----------------------|--------------|------------|
| "Trees similar to my virus phylogeny" | `POST /trees/search/similar` | `{"newick": "...", "limit": 10}` |
| "Ancestors of species X" | `GET /trees/{tree_id}/ancestors/{node_id}` | `max_depth` (optional) |
| "All descendants of clade Y" | `GET /trees/{tree_id}/descendants/{node_id}` | `leaves_only`, `max_depth` |
| "Common ancestor of A and B" | `GET /trees/{tree_id}/lca` | `node1`, `node2` |
| "Species related to X" | `GET /trees/{tree_id}/related-sequences/{node_id}` | `max_distance` |
| "Full tree structure" | `GET /trees/{tree_id}/structure` | None |

### Converting Newick from Other Formats

**From NEXUS**:
```
#NEXUS
BEGIN TREES;
TREE tree1 = ((A,B),(C,D));
END;

→ Extract: ((A,B),(C,D));
```

**From phyloXML** (use BioPython):
```python
from Bio import Phylo
tree = Phylo.read("tree.xml", "phyloxml")
Phylo.write(tree, "tree.nwk", "newick")
```

---

## API Reference

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/trees/ingest` | Add a new tree |
| `POST` | `/trees/ingest/file` | Upload Newick file |
| `GET` | `/trees` | List all trees |
| `GET` | `/trees/{tree_id}` | Get tree details |
| `GET` | `/trees/{tree_id}/structure` | Get nested structure (for visualization) |
| `GET` | `/trees/{tree_id}/node/{node_id}` | Get node details |
| `GET` | `/trees/{tree_id}/ancestors/{node_id}` | Get ancestors |
| `GET` | `/trees/{tree_id}/descendants/{node_id}` | Get descendants |
| `GET` | `/trees/{tree_id}/lca` | Find lowest common ancestor |
| `POST` | `/trees/search/similar` | Find similar trees |
| `GET` | `/trees/{tree_id}/related-sequences/{node_id}` | Find related sequences |
| `DELETE` | `/trees/{tree_id}` | Delete a tree |

### Response Formats

**Tree Response**:
```json
{
  "id": "uuid",
  "name": "Great Apes Evolution",
  "num_leaves": 6,
  "num_nodes": 11,
  "metadata": {},
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Ancestry Response**:
```json
{
  "node_id": "leaf-uuid",
  "ancestors": [
    {"id": "parent-uuid", "name": null, "depth": 1, ...},
    {"id": "root-uuid", "name": null, "depth": 0, ...}
  ],
  "path_length": 2
}
```

---

## Example Use Cases

### 1. Track Viral Variant Evolution

```bash
# Add SARS-CoV-2 variant tree
curl -X POST http://localhost:8000/trees/ingest \
  -d '{"newick": "((Alpha,Beta),(Delta,Omicron));", "name": "COVID Variants"}'

# Find which variants descended from a specific lineage
curl "http://localhost:8000/trees/{tree_id}/descendants/{delta_node_id}?leaves_only=true"
```

### 2. Compare Species Relationships

```bash
# Find the common ancestor of Human and Chimp
curl "http://localhost:8000/trees/{primate_tree_id}/lca?node1={human_id}&node2={chimp_id}"

# Result: Their immediate parent (most recent common ancestor)
```

### 3. Find Similar Research

```bash
# "I have a bacterial phylogeny - are there similar trees in the database?"
curl -X POST http://localhost:8000/trees/search/similar \
  -d '{"newick": "((E_coli,Salmonella),Bacillus);", "limit": 5}'

# Returns trees with similar topology (e.g., bacterial 16S rRNA trees)
```

### 4. Explore Haplogroup Ancestry

```bash
# "Show me the ancestry of haplogroup H (European mtDNA)"
curl "http://localhost:8000/trees/{mtdna_tree_id}/ancestors/{H_node_id}"

# Returns: H → (parent) → ... → L3 (African origin)
```

---

## Best Practices

### 1. Tree Naming
- Use descriptive names: "SARS-CoV-2 Variants (2020-2024)"
- Include domain: "Bacterial 16S rRNA - Proteobacteria"

### 2. Embedding Considerations
- **Similar topology ≠ same species**: Two (A,B),(C,D) trees will be similar even if species differ
- **Branch lengths matter**: They're encoded in node embeddings
- **Large trees**: More unique embeddings, better discrimination

### 3. Search Tips
- Start with `limit=10` for similarity search
- Use `leaves_only=true` when you want actual species, not ancestors
- For deep trees, set `max_depth` to avoid huge result sets

---

## Troubleshooting

### "Tree not found"
- Check the tree_id is correct (use `GET /trees` to list all)

### "Node not found"  
- Node IDs are UUIDs generated at ingestion
- Use `GET /trees/{id}/structure` to see all node IDs

### "Failed to parse tree"
- Ensure Newick ends with semicolon `;`
- Check balanced parentheses
- Avoid special characters in node names (use underscores)

### Low similarity scores
- Very different tree sizes produce lower scores
- Binary vs non-binary trees may not compare well

