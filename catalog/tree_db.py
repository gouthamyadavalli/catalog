"""
LanceDB operations for phylogenetic tree storage.
Handles two tables: trees (whole tree metadata) and tree_nodes (individual nodes).
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd

from .db import get_db
from .models import PhyloTree, TreeNode, PhyloTreeResponse, TreeNodeResponse


def _parse_datetime(value) -> datetime:
    """
    Parse a datetime value that may be a string or datetime object.
    Handles ISO format strings stored in the database.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    # Fallback for pandas Timestamp or other types
    return datetime.now()


# Table names
TREES_TABLE = "phylo_trees"
NODES_TABLE = "tree_nodes"


def init_tree_tables():
    """
    Initialize tree tables if they don't exist.
    Tables are created on first insert (LanceDB pattern).
    """
    db = get_db()
    print(f"Tree tables will be created on first ingestion: {TREES_TABLE}, {NODES_TABLE}")
    return db


def insert_tree(tree: PhyloTree) -> str:
    """
    Insert a PhyloTree into the trees table.
    
    Args:
        tree: PhyloTree object to insert
    
    Returns:
        The tree ID
    """
    db = get_db()
    
    record = tree.model_dump()
    # Convert datetime to string for storage
    record['created_at'] = record['created_at'].isoformat()
    
    if TREES_TABLE in db.table_names():
        tbl = db.open_table(TREES_TABLE)
        tbl.add([record])
    else:
        db.create_table(TREES_TABLE, data=[record])
    
    print(f"Inserted tree: {tree.id} ({tree.name})")
    return tree.id


def insert_nodes(nodes: List[TreeNode]) -> int:
    """
    Insert tree nodes into the nodes table.
    
    Args:
        nodes: List of TreeNode objects
    
    Returns:
        Number of nodes inserted
    """
    if not nodes:
        return 0
    
    db = get_db()
    records = [node.model_dump() for node in nodes]
    
    if NODES_TABLE in db.table_names():
        tbl = db.open_table(NODES_TABLE)
        tbl.add(records)
    else:
        db.create_table(NODES_TABLE, data=records)
    
    print(f"Inserted {len(records)} tree nodes")
    return len(records)


def get_tree_by_id(tree_id: str) -> Optional[PhyloTree]:
    """
    Retrieve a tree by its ID.
    
    Args:
        tree_id: The tree ID
    
    Returns:
        PhyloTree object or None if not found
    """
    db = get_db()
    
    if TREES_TABLE not in db.table_names():
        return None
    
    tbl = db.open_table(TREES_TABLE)
    results = tbl.search().where(f"id = '{tree_id}'").limit(1).to_pandas()
    
    if results.empty:
        return None
    
    row = results.iloc[0]
    return PhyloTree(
        id=row['id'],
        name=row['name'],
        newick=row['newick'],
        embedding=row.get('embedding'),
        num_leaves=row['num_leaves'],
        num_nodes=row['num_nodes'],
        metadata=row.get('metadata', {}),
        created_at=_parse_datetime(row['created_at'])
    )


def get_node_by_id(node_id: str) -> Optional[TreeNode]:
    """
    Retrieve a node by its ID.
    
    Args:
        node_id: The node ID
    
    Returns:
        TreeNode object or None if not found
    """
    db = get_db()
    
    if NODES_TABLE not in db.table_names():
        return None
    
    tbl = db.open_table(NODES_TABLE)
    results = tbl.search().where(f"id = '{node_id}'").limit(1).to_pandas()
    
    if results.empty:
        return None
    
    return _row_to_tree_node(results.iloc[0])


def get_nodes_by_tree_id(tree_id: str) -> List[TreeNode]:
    """
    Get all nodes belonging to a tree.
    
    Args:
        tree_id: The tree ID
    
    Returns:
        List of TreeNode objects
    """
    db = get_db()
    
    if NODES_TABLE not in db.table_names():
        return []
    
    tbl = db.open_table(NODES_TABLE)
    results = tbl.search().where(f"tree_id = '{tree_id}'").limit(100000).to_pandas()
    
    return [_row_to_tree_node(row) for _, row in results.iterrows()]


def get_root_node(tree_id: str) -> Optional[TreeNode]:
    """
    Get the root node of a tree (node with no parent).
    
    Args:
        tree_id: The tree ID
    
    Returns:
        Root TreeNode or None
    """
    db = get_db()
    
    if NODES_TABLE not in db.table_names():
        return None
    
    tbl = db.open_table(NODES_TABLE)
    # Root has parent_id = None, but in LanceDB we might store it as empty string or null
    # Try both approaches
    results = tbl.search().where(f"tree_id = '{tree_id}' AND depth = 0").limit(1).to_pandas()
    
    if results.empty:
        return None
    
    return _row_to_tree_node(results.iloc[0])


def get_leaf_nodes(tree_id: str) -> List[TreeNode]:
    """
    Get all leaf nodes of a tree.
    
    Args:
        tree_id: The tree ID
    
    Returns:
        List of leaf TreeNode objects
    """
    db = get_db()
    
    if NODES_TABLE not in db.table_names():
        return []
    
    tbl = db.open_table(NODES_TABLE)
    results = tbl.search().where(f"tree_id = '{tree_id}' AND is_leaf = true").limit(100000).to_pandas()
    
    return [_row_to_tree_node(row) for _, row in results.iterrows()]


def get_children(node_id: str) -> List[TreeNode]:
    """
    Get direct children of a node.
    
    Args:
        node_id: The parent node ID
    
    Returns:
        List of child TreeNode objects
    """
    db = get_db()
    
    if NODES_TABLE not in db.table_names():
        return []
    
    tbl = db.open_table(NODES_TABLE)
    results = tbl.search().where(f"parent_id = '{node_id}'").limit(2).to_pandas()
    
    return [_row_to_tree_node(row) for _, row in results.iterrows()]


def list_trees(limit: int = 100) -> List[PhyloTreeResponse]:
    """
    List all trees in the database.
    
    Args:
        limit: Maximum number of trees to return
    
    Returns:
        List of PhyloTreeResponse objects
    """
    db = get_db()
    
    if TREES_TABLE not in db.table_names():
        return []
    
    tbl = db.open_table(TREES_TABLE)
    results = tbl.search().limit(limit).to_pandas()
    
    return [
        PhyloTreeResponse(
            id=row['id'],
            name=row['name'],
            num_leaves=row['num_leaves'],
            num_nodes=row['num_nodes'],
            metadata=row.get('metadata', {}),
            created_at=_parse_datetime(row['created_at'])
        )
        for _, row in results.iterrows()
    ]


def update_tree_embedding(tree_id: str, embedding: List[float]):
    """
    Update the embedding for a tree.
    
    Args:
        tree_id: The tree ID
        embedding: The Phylo2Vec embedding
    """
    db = get_db()
    
    if TREES_TABLE not in db.table_names():
        return
    
    tbl = db.open_table(TREES_TABLE)
    # LanceDB update pattern - get, modify, replace
    tree = get_tree_by_id(tree_id)
    if tree:
        tree.embedding = embedding
        # For now, we'll use a delete + insert pattern
        # LanceDB's update API might vary by version
        tbl.delete(f"id = '{tree_id}'")
        record = tree.model_dump()
        record['created_at'] = record['created_at'].isoformat() if hasattr(record['created_at'], 'isoformat') else record['created_at']
        tbl.add([record])


def update_node_embeddings(node_embeddings: Dict[str, List[float]]):
    """
    Update position embeddings for multiple nodes.
    
    Args:
        node_embeddings: Dict mapping node_id to embedding
    """
    db = get_db()
    
    if NODES_TABLE not in db.table_names():
        return
    
    tbl = db.open_table(NODES_TABLE)
    
    for node_id, embedding in node_embeddings.items():
        node = get_node_by_id(node_id)
        if node:
            node.position_embedding = embedding
            tbl.delete(f"id = '{node_id}'")
            tbl.add([node.model_dump()])


def search_similar_trees(query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for trees similar to the query embedding using cosine similarity.
    
    Args:
        query_embedding: The Phylo2Vec embedding to search with
        limit: Maximum results
    
    Returns:
        List of dicts with tree info and similarity scores
    """
    import numpy as np
    
    db = get_db()
    
    if TREES_TABLE not in db.table_names():
        return []
    
    tbl = db.open_table(TREES_TABLE)
    
    # Use cosine distance metric for better similarity matching
    # Cosine distance = 1 - cosine_similarity, so similarity = 1 - distance
    results = tbl.search(query_embedding).metric("cosine").limit(limit).to_pandas()
    
    # Convert query to numpy for manual similarity calculation as backup
    query_arr = np.array(query_embedding)
    query_norm = np.linalg.norm(query_arr)
    
    output = []
    for _, row in results.iterrows():
        # Get distance from LanceDB (cosine distance = 1 - similarity)
        distance = row.get('_distance', 1.0)
        
        # Cosine similarity = 1 - cosine_distance
        # But let's also compute it manually for verification
        tree_emb = np.array(row['embedding'])
        tree_norm = np.linalg.norm(tree_emb)
        
        if query_norm > 0 and tree_norm > 0:
            cosine_sim = np.dot(query_arr, tree_emb) / (query_norm * tree_norm)
        else:
            cosine_sim = 0.0
        
        # Use the computed cosine similarity (more reliable)
        score = float(cosine_sim)
        
        output.append({
            'tree': PhyloTreeResponse(
                id=row['id'],
                name=row['name'],
                num_leaves=row['num_leaves'],
                num_nodes=row['num_nodes'],
                metadata=row.get('metadata', {}),
                created_at=_parse_datetime(row['created_at'])
            ),
            'score': score
        })
    
    # Sort by similarity score (highest first)
    output.sort(key=lambda x: x['score'], reverse=True)
    
    return output


def delete_tree(tree_id: str) -> bool:
    """
    Delete a tree and all its nodes.
    
    Args:
        tree_id: The tree ID to delete
    
    Returns:
        True if deleted, False if not found
    """
    db = get_db()
    
    deleted = False
    
    if TREES_TABLE in db.table_names():
        tbl = db.open_table(TREES_TABLE)
        tbl.delete(f"id = '{tree_id}'")
        deleted = True
    
    if NODES_TABLE in db.table_names():
        tbl = db.open_table(NODES_TABLE)
        tbl.delete(f"tree_id = '{tree_id}'")
    
    return deleted


def _row_to_tree_node(row) -> TreeNode:
    """Convert a pandas row to TreeNode."""
    return TreeNode(
        id=row['id'],
        tree_id=row['tree_id'],
        name=row.get('name'),
        sequence_id=row.get('sequence_id'),
        parent_id=row.get('parent_id'),
        left_child_id=row.get('left_child_id'),
        right_child_id=row.get('right_child_id'),
        depth=row.get('depth', 0),
        branch_length=row.get('branch_length', 0.0),
        is_leaf=row.get('is_leaf', False),
        position_embedding=row.get('position_embedding'),
        metadata=row.get('metadata', {})
    )

