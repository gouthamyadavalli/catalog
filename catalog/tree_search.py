"""
Search operations for phylogenetic trees.
Handles ancestry queries, descendant traversal, and tree similarity search.
"""
from typing import List, Optional, Dict, Any
from collections import deque

from .models import (
    TreeNode, PhyloTree, TreeNodeResponse, PhyloTreeResponse,
    AncestryResponse, DescendantsResponse, TreeSearchResult
)
from .tree_db import (
    get_node_by_id, get_tree_by_id, get_nodes_by_tree_id,
    get_root_node, get_children, search_similar_trees
)
from .tree_embeddings import phylo2vec_encode, pad_embedding
from .tree_parser import parse_newick


# Default embedding dimension for tree search
TREE_EMBEDDING_DIM = 256


def get_ancestors(
    node_id: str,
    tree_id: str,
    max_depth: Optional[int] = None,
    include_self: bool = False
) -> AncestryResponse:
    """
    Get all ancestors of a node by traversing up the tree.
    
    Args:
        node_id: The starting node ID
        tree_id: The tree ID
        max_depth: Maximum number of ancestors to return (None = all)
        include_self: Whether to include the starting node
    
    Returns:
        AncestryResponse with list of ancestors from node to root
    """
    # Get all nodes for this tree (cached lookup is more efficient)
    all_nodes = get_nodes_by_tree_id(tree_id)
    nodes_by_id = {n.id: n for n in all_nodes}
    
    if node_id not in nodes_by_id:
        return AncestryResponse(node_id=node_id, ancestors=[], path_length=0)
    
    ancestors = []
    current = nodes_by_id[node_id]
    
    if include_self:
        ancestors.append(_node_to_response(current, nodes_by_id))
    
    # Traverse up to root
    while current.parent_id:
        if max_depth is not None and len(ancestors) >= max_depth:
            break
        
        parent = nodes_by_id.get(current.parent_id)
        if not parent:
            break
        
        ancestors.append(_node_to_response(parent, nodes_by_id))
        current = parent
    
    return AncestryResponse(
        node_id=node_id,
        ancestors=ancestors,
        path_length=len(ancestors)
    )


def get_descendants(
    node_id: str,
    tree_id: str,
    max_depth: Optional[int] = None,
    leaves_only: bool = False
) -> DescendantsResponse:
    """
    Get all descendants of a node using BFS traversal.
    
    Args:
        node_id: The starting node ID
        tree_id: The tree ID
        max_depth: Maximum depth to traverse (None = all)
        leaves_only: If True, only return leaf nodes
    
    Returns:
        DescendantsResponse with list of descendants
    """
    # Get all nodes for this tree
    all_nodes = get_nodes_by_tree_id(tree_id)
    nodes_by_id = {n.id: n for n in all_nodes}
    
    if node_id not in nodes_by_id:
        return DescendantsResponse(node_id=node_id, descendants=[], total_count=0)
    
    start_node = nodes_by_id[node_id]
    start_depth = start_node.depth
    
    descendants = []
    
    # BFS traversal
    queue = deque([(node_id, 0)])  # (node_id, relative_depth)
    visited = {node_id}
    
    while queue:
        current_id, rel_depth = queue.popleft()
        current = nodes_by_id.get(current_id)
        
        if not current:
            continue
        
        # Skip the starting node itself
        if current_id != node_id:
            if not leaves_only or current.is_leaf:
                descendants.append(_node_to_response(current, nodes_by_id))
        
        # Check depth limit
        if max_depth is not None and rel_depth >= max_depth:
            continue
        
        # Add children to queue
        for child_id in [current.left_child_id, current.right_child_id]:
            if child_id and child_id not in visited:
                visited.add(child_id)
                queue.append((child_id, rel_depth + 1))
    
    return DescendantsResponse(
        node_id=node_id,
        descendants=descendants,
        total_count=len(descendants)
    )


def find_common_ancestor(
    node_id_1: str,
    node_id_2: str,
    tree_id: str
) -> Optional[TreeNodeResponse]:
    """
    Find the lowest common ancestor (LCA) of two nodes.
    
    Args:
        node_id_1: First node ID
        node_id_2: Second node ID
        tree_id: The tree ID
    
    Returns:
        The LCA node or None if not found
    """
    # Get ancestors of both nodes
    ancestors_1 = get_ancestors(node_id_1, tree_id, include_self=True)
    ancestors_2 = get_ancestors(node_id_2, tree_id, include_self=True)
    
    # Create set of ancestor IDs for node 1
    ancestor_ids_1 = {a.id for a in ancestors_1.ancestors}
    
    # Find first common ancestor (going from node 2 towards root)
    for ancestor in ancestors_2.ancestors:
        if ancestor.id in ancestor_ids_1:
            return ancestor
    
    return None


def search_trees_by_structure(
    query_newick: str,
    limit: int = 10
) -> List[TreeSearchResult]:
    """
    Search for trees with similar topology to the query tree.
    
    Args:
        query_newick: Newick format string of query tree
        limit: Maximum results
    
    Returns:
        List of TreeSearchResult with similarity scores
    """
    # Encode the query tree
    query_embedding = phylo2vec_encode(query_newick, normalize=True)
    query_embedding = pad_embedding(query_embedding, TREE_EMBEDDING_DIM)
    
    # Search in database
    results = search_similar_trees(query_embedding, limit)
    
    return [
        TreeSearchResult(
            tree=r['tree'],
            score=r['score']
        )
        for r in results
    ]


def find_related_sequences(
    node_id: str,
    tree_id: str,
    max_distance: int = 3
) -> List[Dict[str, Any]]:
    """
    Find sequences that are evolutionarily close to a given node.
    
    "Close" means within max_distance edges in the tree.
    
    Args:
        node_id: Starting node ID
        tree_id: The tree ID
        max_distance: Maximum edge distance
    
    Returns:
        List of related sequences with distance info
    """
    # Get all nodes
    all_nodes = get_nodes_by_tree_id(tree_id)
    nodes_by_id = {n.id: n for n in all_nodes}
    
    if node_id not in nodes_by_id:
        return []
    
    related = []
    
    # BFS from starting node (both up and down)
    queue = deque([(node_id, 0)])  # (node_id, distance)
    visited = {node_id}
    
    while queue:
        current_id, distance = queue.popleft()
        current = nodes_by_id.get(current_id)
        
        if not current:
            continue
        
        # Add leaf nodes with sequences
        if current.is_leaf and current.sequence_id and current_id != node_id:
            related.append({
                'node_id': current_id,
                'sequence_id': current.sequence_id,
                'name': current.name,
                'distance': distance,
                'branch_length_sum': _compute_branch_distance(
                    node_id, current_id, nodes_by_id
                )
            })
        
        # Don't expand beyond max distance
        if distance >= max_distance:
            continue
        
        # Add neighbors (parent and children)
        neighbors = []
        if current.parent_id:
            neighbors.append(current.parent_id)
        if current.left_child_id:
            neighbors.append(current.left_child_id)
        if current.right_child_id:
            neighbors.append(current.right_child_id)
        
        for neighbor_id in neighbors:
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                queue.append((neighbor_id, distance + 1))
    
    # Sort by distance
    related.sort(key=lambda x: (x['distance'], x.get('branch_length_sum', 0)))
    
    return related


def get_subtree(
    node_id: str,
    tree_id: str
) -> Dict[str, Any]:
    """
    Get a subtree rooted at the given node.
    
    Returns:
        Dict with subtree structure for visualization
    """
    all_nodes = get_nodes_by_tree_id(tree_id)
    nodes_by_id = {n.id: n for n in all_nodes}
    
    if node_id not in nodes_by_id:
        return {}
    
    def build_subtree(nid: str) -> Dict[str, Any]:
        node = nodes_by_id.get(nid)
        if not node:
            return {}
        
        result = {
            'id': node.id,
            'name': node.name,
            'depth': node.depth,
            'branch_length': node.branch_length,
            'is_leaf': node.is_leaf,
            'sequence_id': node.sequence_id,
            'children': []
        }
        
        if node.left_child_id:
            result['children'].append(build_subtree(node.left_child_id))
        if node.right_child_id:
            result['children'].append(build_subtree(node.right_child_id))
        
        return result
    
    return build_subtree(node_id)


def get_tree_structure(tree_id: str) -> Dict[str, Any]:
    """
    Get the full tree structure for visualization.
    
    Args:
        tree_id: The tree ID
    
    Returns:
        Dict with complete tree structure
    """
    tree = get_tree_by_id(tree_id)
    if not tree:
        return {}
    
    root = get_root_node(tree_id)
    if not root:
        return {}
    
    subtree = get_subtree(root.id, tree_id)
    
    return {
        'tree_id': tree_id,
        'name': tree.name,
        'num_leaves': tree.num_leaves,
        'num_nodes': tree.num_nodes,
        'root': subtree
    }


def _node_to_response(node: TreeNode, nodes_by_id: Dict[str, TreeNode]) -> TreeNodeResponse:
    """Convert TreeNode to TreeNodeResponse."""
    children_count = 0
    if node.left_child_id:
        children_count += 1
    if node.right_child_id:
        children_count += 1
    
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


def _compute_branch_distance(
    node_id_1: str,
    node_id_2: str,
    nodes_by_id: Dict[str, TreeNode]
) -> float:
    """
    Compute total branch length between two nodes.
    This is simplified - for accurate distance, we'd need to find LCA.
    """
    # Get path lengths to root for both
    def branch_to_root(nid: str) -> float:
        total = 0.0
        current = nodes_by_id.get(nid)
        while current:
            total += current.branch_length
            if current.parent_id:
                current = nodes_by_id.get(current.parent_id)
            else:
                break
        return total
    
    # This is an approximation; exact would require LCA computation
    return branch_to_root(node_id_1) + branch_to_root(node_id_2)


def subtree_to_newick(
    node_id: str,
    tree_id: str,
    include_branch_lengths: bool = True
) -> str:
    """
    Convert a subtree rooted at node_id back to Newick format.
    
    This enables interactive search: user selects a subtree in the UI,
    we extract its Newick representation, and search for similar trees.
    
    Args:
        node_id: Root node of the subtree
        tree_id: The tree ID
        include_branch_lengths: Whether to include branch lengths in output
    
    Returns:
        Newick format string representing the subtree
    """
    all_nodes = get_nodes_by_tree_id(tree_id)
    nodes_by_id = {n.id: n for n in all_nodes}
    
    if node_id not in nodes_by_id:
        return ""
    
    def _build_newick(nid: str) -> str:
        node = nodes_by_id.get(nid)
        if not node:
            return ""
        
        # Get children
        children = []
        if node.left_child_id:
            children.append(node.left_child_id)
        if node.right_child_id:
            children.append(node.right_child_id)
        
        # Leaf node
        if not children:
            name = node.name or ""
            # Clean name for Newick format (no spaces or special chars)
            name = name.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "").replace(";", "")
            if include_branch_lengths and node.branch_length > 0:
                return f"{name}:{node.branch_length:.4f}"
            return name
        
        # Internal node with children
        child_newicks = [_build_newick(cid) for cid in children]
        subtree = "(" + ",".join(child_newicks) + ")"
        
        # Add name if exists
        if node.name:
            name = node.name.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "").replace(";", "")
            subtree += name
        
        # Add branch length
        if include_branch_lengths and node.branch_length > 0:
            subtree += f":{node.branch_length:.4f}"
        
        return subtree
    
    return _build_newick(node_id) + ";"


def get_subtree_node_ids(
    node_id: str,
    tree_id: str
) -> List[str]:
    """
    Get all node IDs in a subtree (including the root node).
    
    Used for highlighting the subtree in the UI.
    
    Args:
        node_id: Root node of the subtree
        tree_id: The tree ID
    
    Returns:
        List of all node IDs in the subtree
    """
    all_nodes = get_nodes_by_tree_id(tree_id)
    nodes_by_id = {n.id: n for n in all_nodes}
    
    if node_id not in nodes_by_id:
        return []
    
    node_ids = []
    queue = deque([node_id])
    
    while queue:
        current_id = queue.popleft()
        node_ids.append(current_id)
        
        current = nodes_by_id.get(current_id)
        if current:
            if current.left_child_id:
                queue.append(current.left_child_id)
            if current.right_child_id:
                queue.append(current.right_child_id)
    
    return node_ids

