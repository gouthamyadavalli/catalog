from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import shutil
import os
import tempfile
from .models import (
    SearchResult, SearchQuery, 
    PhyloTreeResponse, TreeNodeResponse, AncestryResponse, 
    DescendantsResponse, TreeSearchQuery, TreeSearchResult
)
from .ingest import ingest_fasta
from .search import search_sequences, get_sequence_by_id
from .export import export_search_results
from .db import init_db
from .tree_parser import create_phylo_tree, validate_binary_tree, parse_newick
from .tree_db import (
    insert_tree, insert_nodes, get_tree_by_id, get_node_by_id,
    list_trees, update_tree_embedding, update_node_embeddings, delete_tree
)
from .tree_embeddings import phylo2vec_encode, compute_all_node_embeddings, pad_embedding, explain_similarity
from .tree_search import (
    get_ancestors as tree_get_ancestors, 
    get_descendants as tree_get_descendants,
    find_common_ancestor, search_trees_by_structure,
    find_related_sequences, get_tree_structure,
    subtree_to_newick, get_subtree_node_ids
)

app = FastAPI(title="Genomic Catalog POC")

@app.on_event("startup")
def on_startup():
    init_db()

# Serve static files at root level (same as Vercel)
@app.get("/")
async def root():
    return FileResponse("public/index.html")

@app.get("/index.html")
async def index_html():
    return FileResponse("public/index.html")

@app.get("/styles.css")
async def styles_css():
    return FileResponse("public/styles.css", media_type="text/css")

@app.get("/app.js")
async def app_js():
    return FileResponse("public/app.js", media_type="application/javascript")

# Also mount at /static for backwards compatibility
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.post("/ingest/fasta")
async def ingest_fasta_endpoint(file: UploadFile = File(...)):
    """
    Upload and ingest a FASTA file.
    """
    tmp_path = None
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".fasta") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        await ingest_fasta(tmp_path)
        return {"message": f"Successfully ingested {file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
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


# ============== Phylogenetic Tree Endpoints ==============

class TreeIngestRequest(BaseModel):
    """Request model for tree ingestion."""
    newick: str
    name: str
    metadata: Optional[Dict[str, Any]] = None


@app.post("/trees/ingest", response_model=PhyloTreeResponse)
async def ingest_tree_endpoint(request: TreeIngestRequest):
    """
    Ingest a phylogenetic tree from Newick format.
    
    The tree will be parsed, embedded with Phylo2Vec, and stored in the database.
    """
    try:
        # Validate the Newick string
        bio_tree = parse_newick(request.newick)
        
        # Check if binary (optional - we can handle non-binary trees too)
        is_binary = validate_binary_tree(bio_tree)
        if not is_binary:
            print("Warning: Tree is not strictly binary. Some features may be limited.")
        
        # Create tree and nodes
        phylo_tree, nodes = create_phylo_tree(
            request.newick, 
            request.name, 
            request.metadata
        )
        
        # Compute tree embedding (Phylo2Vec)
        tree_embedding = phylo2vec_encode(request.newick, normalize=True)
        tree_embedding = pad_embedding(tree_embedding, 256)  # Consistent dimension
        phylo_tree.embedding = tree_embedding
        
        # Compute node position embeddings
        node_embeddings = compute_all_node_embeddings(nodes, dimension=64)
        for node in nodes:
            node.position_embedding = node_embeddings.get(node.id, [])
        
        # Insert into database
        insert_tree(phylo_tree)
        insert_nodes(nodes)
        
        return PhyloTreeResponse(
            id=phylo_tree.id,
            name=phylo_tree.name,
            num_leaves=phylo_tree.num_leaves,
            num_nodes=phylo_tree.num_nodes,
            metadata=phylo_tree.metadata,
            created_at=phylo_tree.created_at
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse tree: {str(e)}")


@app.post("/trees/ingest/file", response_model=PhyloTreeResponse)
async def ingest_tree_file_endpoint(
    file: UploadFile = File(...),
    name: str = Query(..., description="Name for the tree")
):
    """
    Upload and ingest a Newick tree file.
    """
    tmp_path = None
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".nwk") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        # Read the Newick content
        with open(tmp_path, 'r') as f:
            newick_content = f.read().strip()
        
        # Use the string ingest endpoint logic
        request = TreeIngestRequest(newick=newick_content, name=name)
        return await ingest_tree_endpoint(request)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/trees", response_model=List[PhyloTreeResponse])
async def list_trees_endpoint(limit: int = Query(100, le=1000)):
    """
    List all phylogenetic trees in the database.
    """
    return list_trees(limit)


@app.get("/trees/{tree_id}", response_model=PhyloTreeResponse)
async def get_tree_endpoint(tree_id: str):
    """
    Get a specific tree by ID.
    """
    tree = get_tree_by_id(tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    
    return PhyloTreeResponse(
        id=tree.id,
        name=tree.name,
        num_leaves=tree.num_leaves,
        num_nodes=tree.num_nodes,
        metadata=tree.metadata,
        created_at=tree.created_at
    )


@app.get("/trees/{tree_id}/structure")
async def get_tree_structure_endpoint(tree_id: str):
    """
    Get the full tree structure for visualization.
    
    Returns a nested JSON structure suitable for rendering tree diagrams.
    """
    structure = get_tree_structure(tree_id)
    if not structure:
        raise HTTPException(status_code=404, detail="Tree not found")
    return structure


@app.get("/trees/{tree_id}/node/{node_id}", response_model=TreeNodeResponse)
async def get_node_endpoint(tree_id: str, node_id: str):
    """
    Get a specific node by ID.
    """
    node = get_node_by_id(node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(status_code=404, detail="Node not found")
    
    children_count = sum(1 for c in [node.left_child_id, node.right_child_id] if c)
    
    return TreeNodeResponse(
        id=node.id,
        name=node.name,
        depth=node.depth,
        branch_length=node.branch_length,
        is_leaf=node.is_leaf,
        sequence_id=node.sequence_id,
        children_count=children_count,
        metadata=node.metadata
    )


@app.get("/trees/{tree_id}/ancestors/{node_id}", response_model=AncestryResponse)
async def get_tree_ancestors_endpoint(
    tree_id: str,
    node_id: str,
    max_depth: Optional[int] = Query(None, description="Maximum ancestors to return")
):
    """
    Get all ancestors of a node, from the node up to the root.
    """
    result = tree_get_ancestors(node_id, tree_id, max_depth)
    if not result.ancestors and max_depth != 0:
        # Check if node exists
        node = get_node_by_id(node_id)
        if not node or node.tree_id != tree_id:
            raise HTTPException(status_code=404, detail="Node not found")
    return result


@app.get("/trees/{tree_id}/descendants/{node_id}", response_model=DescendantsResponse)
async def get_tree_descendants_endpoint(
    tree_id: str,
    node_id: str,
    max_depth: Optional[int] = Query(None, description="Maximum depth to traverse"),
    leaves_only: bool = Query(False, description="Return only leaf nodes")
):
    """
    Get all descendants of a node using BFS traversal.
    """
    result = tree_get_descendants(node_id, tree_id, max_depth, leaves_only)
    if not result.descendants:
        # Check if node exists and is not a leaf
        node = get_node_by_id(node_id)
        if not node or node.tree_id != tree_id:
            raise HTTPException(status_code=404, detail="Node not found")
    return result


@app.get("/trees/{tree_id}/lca")
async def get_lca_endpoint(
    tree_id: str,
    node1: str = Query(..., description="First node ID"),
    node2: str = Query(..., description="Second node ID")
):
    """
    Find the Lowest Common Ancestor (LCA) of two nodes.
    """
    lca = find_common_ancestor(node1, node2, tree_id)
    if not lca:
        raise HTTPException(status_code=404, detail="Could not find common ancestor")
    return lca


@app.post("/trees/search/similar", response_model=List[TreeSearchResult])
async def search_similar_trees_endpoint(query: TreeSearchQuery):
    """
    Search for trees with similar topology.
    
    Provide either a Newick string or an existing tree_id to find similar trees.
    """
    if query.newick:
        results = search_trees_by_structure(query.newick, query.limit)
    elif query.tree_id:
        tree = get_tree_by_id(query.tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Reference tree not found")
        results = search_trees_by_structure(tree.newick, query.limit)
    else:
        raise HTTPException(status_code=400, detail="Provide either newick or tree_id")
    
    return results


@app.get("/trees/{tree_id}/related-sequences/{node_id}")
async def get_related_sequences_endpoint(
    tree_id: str,
    node_id: str,
    max_distance: int = Query(3, le=10, description="Maximum edge distance")
):
    """
    Find sequences that are evolutionarily close to a node.
    
    Returns sequences within max_distance edges in the tree.
    """
    related = find_related_sequences(node_id, tree_id, max_distance)
    return {"node_id": node_id, "related_sequences": related}


@app.get("/trees/{tree_id}/subtree/{node_id}/newick")
async def get_subtree_newick_endpoint(
    tree_id: str,
    node_id: str,
    include_branch_lengths: bool = Query(False, description="Include branch lengths in Newick output (default: False for better topology matching)")
):
    """
    Extract a subtree as Newick format string.
    
    This enables interactive search: select a subtree in the UI,
    get its Newick representation, and search for similar trees.
    """
    # Validate node exists
    node = get_node_by_id(node_id)
    if not node or node.tree_id != tree_id:
        raise HTTPException(status_code=404, detail="Node not found")
    
    newick = subtree_to_newick(node_id, tree_id, include_branch_lengths)
    if not newick:
        raise HTTPException(status_code=500, detail="Failed to extract subtree")
    
    # Also get the list of node IDs in the subtree (for UI highlighting)
    subtree_nodes = get_subtree_node_ids(node_id, tree_id)
    
    return {
        "newick": newick,
        "root_node_id": node_id,
        "node_count": len(subtree_nodes),
        "node_ids": subtree_nodes
    }


class ExplainSimilarityRequest(BaseModel):
    """Request model for similarity explanation."""
    query_newick: str
    result_tree_id: str


@app.post("/trees/explain-similarity")
async def explain_tree_similarity_endpoint(request: ExplainSimilarityRequest):
    """
    Explain why a query tree is similar to a result tree.
    
    Returns a detailed breakdown of similarity by feature category,
    helping users understand why certain trees appear in search results.
    """
    # Get the result tree
    result_tree = get_tree_by_id(request.result_tree_id)
    if not result_tree:
        raise HTTPException(status_code=404, detail="Result tree not found")
    
    try:
        explanation = explain_similarity(request.query_newick, result_tree.newick)
        explanation['result_tree_name'] = result_tree.name
        return explanation
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to explain similarity: {str(e)}")


@app.delete("/trees/{tree_id}")
async def delete_tree_endpoint(tree_id: str):
    """
    Delete a tree and all its nodes.
    """
    success = delete_tree(tree_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tree not found")
    return {"message": f"Tree {tree_id} deleted successfully"}
