"""
Phylogenetic tree parser using BioPython.
Parses Newick format trees and extracts node relationships.
"""
from typing import List, Tuple, Optional, Dict, Any
from Bio import Phylo
from io import StringIO
import uuid

from .models import PhyloTree, TreeNode


def parse_newick(newick_string: str) -> Phylo.BaseTree.Tree:
    """
    Parse a Newick format string into a BioPython tree object.
    
    Args:
        newick_string: Newick format tree string (e.g., "(A:0.1,B:0.2,(C:0.3,D:0.4):0.5);")
    
    Returns:
        BioPython Tree object
    """
    handle = StringIO(newick_string)
    tree = Phylo.read(handle, "newick")
    return tree


def generate_node_id() -> str:
    """Generate a unique node ID."""
    return str(uuid.uuid4())


def extract_nodes(
    tree: Phylo.BaseTree.Tree,
    tree_id: str
) -> Tuple[List[TreeNode], Dict[str, str]]:
    """
    Extract all nodes from a BioPython tree with parent-child relationships.
    
    Args:
        tree: BioPython Tree object
        tree_id: ID of the parent PhyloTree
    
    Returns:
        Tuple of (list of TreeNode objects, mapping of clade to node_id)
    """
    nodes = []
    clade_to_id: Dict[int, str] = {}  # Maps clade id() to node_id
    
    def process_clade(
        clade: Phylo.BaseTree.Clade,
        parent_id: Optional[str],
        depth: int
    ) -> str:
        """Recursively process a clade and its children."""
        node_id = generate_node_id()
        clade_to_id[id(clade)] = node_id
        
        # Determine if this is a leaf
        is_leaf = clade.is_terminal()
        
        # Get children (for binary trees, should be 0 or 2)
        children = list(clade.clades) if hasattr(clade, 'clades') else []
        
        left_child_id = None
        right_child_id = None
        
        # Process children first to get their IDs
        if len(children) >= 1:
            left_child_id = process_clade(children[0], node_id, depth + 1)
        if len(children) >= 2:
            right_child_id = process_clade(children[1], node_id, depth + 1)
        
        # Create the node
        node = TreeNode(
            id=node_id,
            tree_id=tree_id,
            name=clade.name if clade.name else None,
            sequence_id=None,  # Will be linked later if needed
            parent_id=parent_id,
            left_child_id=left_child_id,
            right_child_id=right_child_id,
            depth=depth,
            branch_length=clade.branch_length if clade.branch_length else 0.0,
            is_leaf=is_leaf,
            position_embedding=None,  # Will be computed by tree_embeddings
            metadata={
                "confidence": clade.confidence if hasattr(clade, 'confidence') and clade.confidence else None
            }
        )
        
        nodes.append(node)
        return node_id
    
    # Start from root
    root = tree.root
    process_clade(root, None, 0)
    
    return nodes, {str(k): v for k, v in clade_to_id.items()}


def count_tree_stats(tree: Phylo.BaseTree.Tree) -> Tuple[int, int]:
    """
    Count leaves and total nodes in a tree.
    
    Returns:
        Tuple of (num_leaves, num_nodes)
    """
    num_leaves = tree.count_terminals()
    num_nodes = len(list(tree.find_clades()))
    return num_leaves, num_nodes


def parse_tree_file(file_path: str) -> Phylo.BaseTree.Tree:
    """
    Parse a Newick tree from a file.
    
    Args:
        file_path: Path to Newick format file
    
    Returns:
        BioPython Tree object
    """
    return Phylo.read(file_path, "newick")


def tree_to_newick(tree: Phylo.BaseTree.Tree) -> str:
    """
    Convert a BioPython tree back to Newick format string.
    
    Args:
        tree: BioPython Tree object
    
    Returns:
        Newick format string
    """
    output = StringIO()
    Phylo.write(tree, output, "newick")
    return output.getvalue().strip()


def create_phylo_tree(
    newick_string: str,
    name: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[PhyloTree, List[TreeNode]]:
    """
    Create a PhyloTree and its nodes from a Newick string.
    
    This is the main entry point for tree ingestion.
    
    Args:
        newick_string: Newick format tree string
        name: Name for the tree
        metadata: Optional metadata dictionary
    
    Returns:
        Tuple of (PhyloTree object, list of TreeNode objects)
    """
    # Parse the Newick string
    bio_tree = parse_newick(newick_string)
    
    # Generate tree ID
    tree_id = str(uuid.uuid4())
    
    # Count stats
    num_leaves, num_nodes = count_tree_stats(bio_tree)
    
    # Extract all nodes
    nodes, _ = extract_nodes(bio_tree, tree_id)
    
    # Create the PhyloTree object
    phylo_tree = PhyloTree(
        id=tree_id,
        name=name,
        newick=newick_string,
        embedding=None,  # Will be computed by tree_embeddings
        num_leaves=num_leaves,
        num_nodes=num_nodes,
        metadata=metadata or {}
    )
    
    return phylo_tree, nodes


def get_leaf_names(tree: Phylo.BaseTree.Tree) -> List[str]:
    """
    Get all leaf names from a tree.
    
    Args:
        tree: BioPython Tree object
    
    Returns:
        List of leaf names
    """
    return [terminal.name for terminal in tree.get_terminals() if terminal.name]


def validate_binary_tree(tree: Phylo.BaseTree.Tree) -> bool:
    """
    Check if a tree is strictly binary (each internal node has exactly 2 children).
    
    Args:
        tree: BioPython Tree object
    
    Returns:
        True if binary, False otherwise
    """
    for clade in tree.find_clades():
        if not clade.is_terminal():
            num_children = len(clade.clades) if hasattr(clade, 'clades') else 0
            if num_children != 2:
                return False
    return True

