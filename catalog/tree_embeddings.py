"""
Tree embedding methods for phylogenetic trees.
Implements Phylo2Vec encoding for binary trees and position embeddings for nodes.

Phylo2Vec encodes a binary tree with n leaves into a unique integer vector of length n-1.
This enables efficient tree comparison via vector distance operations.

Reference: https://arxiv.org/abs/2304.12693
"""
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
from Bio import Phylo
from io import StringIO

from .models import TreeNode, PhyloTree


def phylo2vec_encode(newick_string: str, normalize: bool = True) -> List[float]:
    """
    Encode a phylogenetic tree into a rich vector representation.
    
    This encoding captures:
    - Tree topology (branching structure)
    - Subtree sizes at each level
    - Depth distribution of leaves
    - Split patterns (how leaves are divided at each internal node)
    
    The result is a 256-dimensional vector that enables meaningful similarity search.
    
    Args:
        newick_string: Newick format tree string
        normalize: Whether to normalize the output to unit length
    
    Returns:
        List of floats representing the tree structure
    """
    # Parse the tree
    handle = StringIO(newick_string)
    tree = Phylo.read(handle, "newick")
    
    # Target dimension
    TARGET_DIM = 256
    
    # Initialize feature vectors
    embedding = np.zeros(TARGET_DIM)
    
    # Get all clades
    clades = list(tree.find_clades())
    leaves = list(tree.get_terminals())
    internal_nodes = [c for c in clades if not c.is_terminal()]
    
    n_leaves = len(leaves)
    n_internal = len(internal_nodes)
    n_total = len(clades)
    
    if n_leaves < 2:
        return [0.0] * TARGET_DIM
    
    # === Feature Group 1: Basic tree statistics (dims 0-31) ===
    embedding[0] = n_leaves / 50.0  # Normalized leaf count
    embedding[1] = n_internal / 50.0  # Normalized internal node count
    embedding[2] = n_total / 100.0  # Total nodes
    embedding[3] = n_internal / max(n_leaves - 1, 1)  # Ratio (1.0 for binary)
    
    # Tree depth statistics
    leaf_depths = [len(tree.get_path(leaf)) for leaf in leaves]
    max_depth = max(leaf_depths) if leaf_depths else 0
    min_depth = min(leaf_depths) if leaf_depths else 0
    avg_depth = sum(leaf_depths) / len(leaf_depths) if leaf_depths else 0
    
    embedding[4] = max_depth / 20.0
    embedding[5] = min_depth / 20.0
    embedding[6] = avg_depth / 20.0
    embedding[7] = (max_depth - min_depth) / 20.0  # Depth variance
    
    # === Feature Group 2: Depth histogram (dims 32-63) ===
    # How many leaves at each depth level
    depth_hist = np.zeros(32)
    for d in leaf_depths:
        if d < 32:
            depth_hist[d] += 1
    if n_leaves > 0:
        depth_hist = depth_hist / n_leaves  # Normalize
    embedding[32:64] = depth_hist
    
    # === Feature Group 3: Subtree size distribution (dims 64-127) ===
    # Encode the sizes of subtrees at each internal node
    subtree_sizes = []
    
    def get_subtree_size(clade):
        if clade.is_terminal():
            return 1
        return sum(get_subtree_size(c) for c in clade.clades)
    
    for node in internal_nodes:
        if hasattr(node, 'clades') and len(node.clades) >= 2:
            sizes = [get_subtree_size(c) for c in node.clades]
            sizes.sort()
            # Record the ratio of smaller to larger subtree (balance)
            balance = sizes[0] / max(sizes[-1], 1)
            subtree_sizes.append(balance)
    
    # Create histogram of balance ratios
    size_hist = np.zeros(32)
    for balance in subtree_sizes:
        bin_idx = min(int(balance * 31), 31)
        size_hist[bin_idx] += 1
    if subtree_sizes:
        size_hist = size_hist / len(subtree_sizes)
    embedding[64:96] = size_hist
    
    # === Feature Group 4: Split pattern encoding (dims 96-159) ===
    # Encode how the tree splits at each level
    split_patterns = np.zeros(64)
    
    def encode_splits(clade, depth=0):
        if clade.is_terminal() or depth >= 16:
            return
        
        if hasattr(clade, 'clades'):
            n_children = len(clade.clades)
            # Encode number of children at this depth
            idx = depth * 4
            if idx < 64:
                split_patterns[idx] += 1  # Node count at this depth
                split_patterns[idx + 1] += n_children / 10.0  # Children count
                
                # Child subtree sizes
                sizes = sorted([get_subtree_size(c) for c in clade.clades])
                if len(sizes) >= 2:
                    split_patterns[idx + 2] += sizes[0] / max(n_leaves, 1)
                    split_patterns[idx + 3] += sizes[-1] / max(n_leaves, 1)
            
            for child in clade.clades:
                encode_splits(child, depth + 1)
    
    encode_splits(tree.root)
    
    # Normalize split patterns
    max_val = np.max(split_patterns)
    if max_val > 0:
        split_patterns = split_patterns / max_val
    embedding[96:160] = split_patterns
    
    # === Feature Group 5: Topology hash (dims 160-223) ===
    # Create a hash-based encoding of the topology
    topo_hash = np.zeros(64)
    
    def topology_hash(clade, path=""):
        if clade.is_terminal():
            # Hash the path to this leaf
            h = hash(path) % 64
            topo_hash[h] += 1.0
            return "L"
        
        child_sigs = []
        for i, child in enumerate(clade.clades if hasattr(clade, 'clades') else []):
            sig = topology_hash(child, path + str(i))
            child_sigs.append(sig)
        
        # Sort child signatures for canonical form
        child_sigs.sort()
        sig = "(" + ",".join(child_sigs) + ")"
        
        # Hash this internal node signature
        h = hash(sig) % 64
        topo_hash[h] += 0.5
        
        return sig
    
    topology_hash(tree.root)
    
    # Normalize
    max_val = np.max(topo_hash)
    if max_val > 0:
        topo_hash = topo_hash / max_val
    embedding[160:224] = topo_hash
    
    # === Feature Group 6: Branch length statistics (dims 224-255) ===
    # NOTE: Branch lengths scaled down significantly to prevent them from 
    # dominating topology-based similarity. Topology features should be primary.
    branch_features = np.zeros(32)
    
    branch_lengths = []
    for clade in clades:
        if clade.branch_length:
            branch_lengths.append(clade.branch_length)
    
    if branch_lengths:
        branch_arr = np.array(branch_lengths)
        # Scale down all branch features by 0.1 to reduce their impact
        BRANCH_SCALE = 0.1
        branch_features[0] = np.mean(branch_arr) * BRANCH_SCALE
        branch_features[1] = (np.std(branch_arr) if len(branch_arr) > 1 else 0) * BRANCH_SCALE
        branch_features[2] = np.min(branch_arr) * BRANCH_SCALE
        branch_features[3] = np.max(branch_arr) * BRANCH_SCALE
        branch_features[4] = np.median(branch_arr) * BRANCH_SCALE
        branch_features[5] = np.sum(branch_arr) * BRANCH_SCALE * 0.01  # Total tree length (extra scaling)
        
        # Branch length histogram - also scaled down
        if np.max(branch_arr) > 0:
            normalized_branches = branch_arr / np.max(branch_arr)
            for bl in normalized_branches:
                bin_idx = min(int(bl * 25), 25)
                branch_features[6 + bin_idx] += BRANCH_SCALE
            branch_features[6:32] = branch_features[6:32] / len(branch_lengths)
    
    embedding[224:256] = branch_features
    
    # Normalize the entire embedding if requested
    if normalize:
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
    
    return embedding.tolist()


def compute_position_embedding(
    node: TreeNode,
    all_nodes: Dict[str, TreeNode],
    dimension: int = 64
) -> List[float]:
    """
    Compute a position embedding for a node based on its path from root.
    
    The embedding encodes:
    - Depth in tree
    - Path from root (left/right decisions)
    - Branch length accumulation
    
    Args:
        node: The TreeNode to embed
        all_nodes: Dict mapping node_id to TreeNode for traversal
        dimension: Output embedding dimension
    
    Returns:
        Position embedding as list of floats
    """
    # Initialize embedding
    embedding = np.zeros(dimension)
    
    # Encode depth (first few dimensions)
    depth_dims = min(16, dimension // 4)
    depth_encoding = _sinusoidal_encoding(node.depth, depth_dims)
    embedding[:depth_dims] = depth_encoding
    
    # Encode path from root (middle dimensions)
    path = _get_path_from_root(node, all_nodes)
    path_dims = min(32, dimension // 2)
    path_encoding = _encode_path(path, path_dims)
    embedding[depth_dims:depth_dims + path_dims] = path_encoding
    
    # Encode branch length info (remaining dimensions)
    branch_dims = dimension - depth_dims - path_dims
    if branch_dims > 0:
        total_branch_length = _get_total_branch_length(node, all_nodes)
        branch_encoding = _sinusoidal_encoding(total_branch_length * 10, branch_dims)
        embedding[depth_dims + path_dims:] = branch_encoding
    
    # Normalize
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    return embedding.tolist()


def _sinusoidal_encoding(value: float, dimension: int) -> np.ndarray:
    """
    Create sinusoidal position encoding (similar to Transformer positional encoding).
    """
    encoding = np.zeros(dimension)
    for i in range(0, dimension, 2):
        div_term = np.exp(i * (-np.log(10000.0) / dimension))
        encoding[i] = np.sin(value * div_term)
        if i + 1 < dimension:
            encoding[i + 1] = np.cos(value * div_term)
    return encoding


def _get_path_from_root(node: TreeNode, all_nodes: Dict[str, TreeNode]) -> List[int]:
    """
    Get the path from root to this node as a list of 0s and 1s.
    0 = left child, 1 = right child
    """
    path = []
    current = node
    
    while current.parent_id:
        parent = all_nodes.get(current.parent_id)
        if not parent:
            break
        
        # Determine if current is left or right child
        if parent.left_child_id == current.id:
            path.append(0)
        else:
            path.append(1)
        
        current = parent
    
    # Reverse to get root-to-node order
    return path[::-1]


def _encode_path(path: List[int], dimension: int) -> np.ndarray:
    """
    Encode a binary path into a fixed-dimension vector.
    Uses a hash-like encoding to handle variable length paths.
    """
    encoding = np.zeros(dimension)
    
    if not path:
        return encoding
    
    # Encode path bits with position weighting
    for i, bit in enumerate(path):
        # Use multiple hash functions to spread information
        for j in range(min(4, dimension)):
            idx = (i * 7 + j * 13 + bit * 17) % dimension
            weight = 1.0 / (i + 1)  # Closer to root = higher weight
            encoding[idx] += (bit * 2 - 1) * weight  # Map 0->-1, 1->1
    
    return encoding


def _get_total_branch_length(node: TreeNode, all_nodes: Dict[str, TreeNode]) -> float:
    """
    Get total branch length from root to this node.
    """
    total = 0.0
    current = node
    
    while current:
        total += current.branch_length
        if current.parent_id:
            current = all_nodes.get(current.parent_id)
        else:
            break
    
    return total


def compute_all_node_embeddings(
    nodes: List[TreeNode],
    dimension: int = 64
) -> Dict[str, List[float]]:
    """
    Compute position embeddings for all nodes in a tree.
    
    Args:
        nodes: List of TreeNode objects from a single tree
        dimension: Embedding dimension
    
    Returns:
        Dict mapping node_id to embedding
    """
    # Build lookup dict
    all_nodes = {node.id: node for node in nodes}
    
    # Compute embeddings
    embeddings = {}
    for node in nodes:
        embeddings[node.id] = compute_position_embedding(node, all_nodes, dimension)
    
    return embeddings


def tree_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Compute cosine similarity between two tree embeddings.
    
    Args:
        embedding1: First tree embedding
        embedding2: Second tree embedding
    
    Returns:
        Similarity score between 0 and 1
    """
    arr1 = np.array(embedding1)
    arr2 = np.array(embedding2)
    
    # Handle dimension mismatch by padding
    if len(arr1) != len(arr2):
        max_len = max(len(arr1), len(arr2))
        arr1 = np.pad(arr1, (0, max_len - len(arr1)))
        arr2 = np.pad(arr2, (0, max_len - len(arr2)))
    
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(np.dot(arr1, arr2) / (norm1 * norm2))


def pad_embedding(embedding: List[float], target_dim: int) -> List[float]:
    """
    Pad an embedding to a target dimension.
    
    Args:
        embedding: Original embedding
        target_dim: Target dimension
    
    Returns:
        Padded embedding
    """
    if len(embedding) >= target_dim:
        return embedding[:target_dim]
    
    return embedding + [0.0] * (target_dim - len(embedding))


def explain_similarity(newick1: str, newick2: str) -> Dict[str, Any]:
    """
    Explain why two trees are similar or different.
    
    Returns a detailed breakdown of similarity by feature category,
    making search results interpretable to users.
    
    Args:
        newick1: First tree in Newick format (query)
        newick2: Second tree in Newick format (result)
    
    Returns:
        Dict with similarity explanation including:
        - overall_score: Total similarity (0-1)
        - feature_scores: Breakdown by category
        - comparison: Side-by-side metrics
        - reasons: Human-readable explanations
    """
    from Bio import Phylo
    from io import StringIO
    
    # Parse both trees
    tree1 = Phylo.read(StringIO(newick1), "newick")
    tree2 = Phylo.read(StringIO(newick2), "newick")
    
    # Extract metrics from both trees
    metrics1 = _extract_tree_metrics(tree1)
    metrics2 = _extract_tree_metrics(tree2)
    
    # Calculate similarity scores for each feature category
    feature_scores = {}
    reasons = []
    
    # 1. Size similarity (number of leaves/nodes)
    size_sim = _calculate_size_similarity(metrics1, metrics2)
    feature_scores['size'] = {
        'score': size_sim,
        'label': 'Tree Size',
        'icon': '📊'
    }
    
    # 2. Depth similarity
    depth_sim = _calculate_depth_similarity(metrics1, metrics2)
    feature_scores['depth'] = {
        'score': depth_sim,
        'label': 'Depth Structure',
        'icon': '📏'
    }
    
    # 3. Balance similarity (how evenly the tree splits)
    balance_sim = _calculate_balance_similarity(metrics1, metrics2)
    feature_scores['balance'] = {
        'score': balance_sim,
        'label': 'Tree Balance',
        'icon': '⚖️'
    }
    
    # 4. Topology similarity (branching pattern)
    topo_sim = _calculate_topology_similarity(metrics1, metrics2)
    feature_scores['topology'] = {
        'score': topo_sim,
        'label': 'Branching Pattern',
        'icon': '🌳'
    }
    
    # 5. Branch length similarity (if available)
    branch_sim = _calculate_branch_similarity(metrics1, metrics2)
    feature_scores['branches'] = {
        'score': branch_sim,
        'label': 'Branch Lengths',
        'icon': '📐'
    }
    
    # Generate human-readable reasons
    reasons = _generate_similarity_reasons(metrics1, metrics2, feature_scores)
    
    # Calculate overall weighted score
    weights = {'size': 0.2, 'depth': 0.2, 'balance': 0.2, 'topology': 0.3, 'branches': 0.1}
    overall_score = sum(feature_scores[k]['score'] * weights[k] for k in weights)
    
    return {
        'overall_score': overall_score,
        'feature_scores': feature_scores,
        'comparison': {
            'query': {
                'leaves': metrics1['n_leaves'],
                'depth': round(metrics1['avg_depth'], 1),
                'max_depth': metrics1['max_depth'],
                'balance': round(metrics1['avg_balance'], 2)
            },
            'result': {
                'leaves': metrics2['n_leaves'],
                'depth': round(metrics2['avg_depth'], 1),
                'max_depth': metrics2['max_depth'],
                'balance': round(metrics2['avg_balance'], 2)
            }
        },
        'reasons': reasons
    }


def _extract_tree_metrics(tree) -> Dict[str, Any]:
    """Extract key metrics from a tree for comparison."""
    leaves = list(tree.get_terminals())
    internal = [c for c in tree.find_clades() if not c.is_terminal()]
    
    n_leaves = len(leaves)
    n_internal = len(internal)
    
    # Depth metrics
    leaf_depths = [len(tree.get_path(leaf)) for leaf in leaves]
    max_depth = max(leaf_depths) if leaf_depths else 0
    min_depth = min(leaf_depths) if leaf_depths else 0
    avg_depth = sum(leaf_depths) / len(leaf_depths) if leaf_depths else 0
    
    # Balance metrics (how evenly children split at each internal node)
    balances = []
    def get_subtree_size(clade):
        if clade.is_terminal():
            return 1
        return sum(get_subtree_size(c) for c in clade.clades)
    
    for node in internal:
        if hasattr(node, 'clades') and len(node.clades) >= 2:
            sizes = sorted([get_subtree_size(c) for c in node.clades])
            balance = sizes[0] / max(sizes[-1], 1)
            balances.append(balance)
    
    avg_balance = sum(balances) / len(balances) if balances else 1.0
    
    # Branch length metrics
    branch_lengths = [c.branch_length for c in tree.find_clades() if c.branch_length]
    avg_branch = sum(branch_lengths) / len(branch_lengths) if branch_lengths else 0
    total_branch = sum(branch_lengths) if branch_lengths else 0
    
    # Topology signature (simplified hash of structure)
    def topo_sig(clade, depth=0):
        if clade.is_terminal():
            return f"L{depth}"
        child_sigs = sorted([topo_sig(c, depth+1) for c in clade.clades])
        return f"({','.join(child_sigs)})"
    
    topology = topo_sig(tree.root)
    
    return {
        'n_leaves': n_leaves,
        'n_internal': n_internal,
        'max_depth': max_depth,
        'min_depth': min_depth,
        'avg_depth': avg_depth,
        'depth_variance': max_depth - min_depth,
        'avg_balance': avg_balance,
        'balances': balances,
        'avg_branch': avg_branch,
        'total_branch': total_branch,
        'has_branches': len(branch_lengths) > 0,
        'topology': topology,
        'leaf_depths': leaf_depths
    }


def _calculate_size_similarity(m1: Dict, m2: Dict) -> float:
    """Calculate similarity based on tree size."""
    # Compare number of leaves
    leaf_ratio = min(m1['n_leaves'], m2['n_leaves']) / max(m1['n_leaves'], m2['n_leaves'], 1)
    
    # Compare number of internal nodes
    internal_ratio = min(m1['n_internal'], m2['n_internal']) / max(m1['n_internal'], m2['n_internal'], 1)
    
    return (leaf_ratio + internal_ratio) / 2


def _calculate_depth_similarity(m1: Dict, m2: Dict) -> float:
    """Calculate similarity based on depth structure."""
    # Compare max depth
    max_depth_diff = abs(m1['max_depth'] - m2['max_depth'])
    max_depth_sim = max(0, 1 - max_depth_diff / max(m1['max_depth'], m2['max_depth'], 1))
    
    # Compare average depth
    avg_depth_diff = abs(m1['avg_depth'] - m2['avg_depth'])
    avg_depth_sim = max(0, 1 - avg_depth_diff / max(m1['avg_depth'], m2['avg_depth'], 1))
    
    # Compare depth variance
    var_diff = abs(m1['depth_variance'] - m2['depth_variance'])
    var_sim = max(0, 1 - var_diff / max(m1['depth_variance'], m2['depth_variance'], 1))
    
    return (max_depth_sim + avg_depth_sim + var_sim) / 3


def _calculate_balance_similarity(m1: Dict, m2: Dict) -> float:
    """Calculate similarity based on tree balance."""
    # Compare average balance
    balance_diff = abs(m1['avg_balance'] - m2['avg_balance'])
    return max(0, 1 - balance_diff)


def _calculate_topology_similarity(m1: Dict, m2: Dict) -> float:
    """Calculate similarity based on topology."""
    # If topologies are identical (same structure), perfect match
    if m1['topology'] == m2['topology']:
        return 1.0
    
    # Otherwise, compare depth distributions
    d1 = sorted(m1['leaf_depths'])
    d2 = sorted(m2['leaf_depths'])
    
    # Pad to same length
    max_len = max(len(d1), len(d2))
    d1 = d1 + [0] * (max_len - len(d1))
    d2 = d2 + [0] * (max_len - len(d2))
    
    # Calculate correlation
    if max_len == 0:
        return 0.5
    
    diff_sum = sum(abs(a - b) for a, b in zip(d1, d2))
    max_diff = max_len * max(max(d1), max(d2), 1)
    
    return max(0, 1 - diff_sum / max_diff)


def _calculate_branch_similarity(m1: Dict, m2: Dict) -> float:
    """Calculate similarity based on branch lengths."""
    if not m1['has_branches'] or not m2['has_branches']:
        return 0.5  # Neutral if no branch info
    
    # Compare average branch length (normalized)
    avg_diff = abs(m1['avg_branch'] - m2['avg_branch'])
    max_avg = max(m1['avg_branch'], m2['avg_branch'], 0.001)
    
    return max(0, 1 - avg_diff / max_avg)


def _generate_similarity_reasons(m1: Dict, m2: Dict, scores: Dict) -> List[Dict[str, str]]:
    """Generate human-readable explanations for similarity."""
    reasons = []
    
    # Size comparison
    if m1['n_leaves'] == m2['n_leaves']:
        reasons.append({
            'type': 'match',
            'text': f"Both trees have exactly {m1['n_leaves']} leaves",
            'category': 'size'
        })
    elif scores['size']['score'] > 0.8:
        reasons.append({
            'type': 'similar',
            'text': f"Similar size: {m1['n_leaves']} vs {m2['n_leaves']} leaves",
            'category': 'size'
        })
    elif scores['size']['score'] < 0.5:
        reasons.append({
            'type': 'different',
            'text': f"Different sizes: {m1['n_leaves']} vs {m2['n_leaves']} leaves",
            'category': 'size'
        })
    
    # Depth comparison
    if m1['max_depth'] == m2['max_depth']:
        reasons.append({
            'type': 'match',
            'text': f"Same maximum depth ({m1['max_depth']} levels)",
            'category': 'depth'
        })
    elif scores['depth']['score'] > 0.7:
        reasons.append({
            'type': 'similar',
            'text': f"Similar depth structure",
            'category': 'depth'
        })
    
    # Balance comparison
    if scores['balance']['score'] > 0.8:
        if m1['avg_balance'] > 0.7:
            reasons.append({
                'type': 'match',
                'text': "Both are well-balanced trees",
                'category': 'balance'
            })
        else:
            reasons.append({
                'type': 'similar',
                'text': "Similar branching imbalance",
                'category': 'balance'
            })
    
    # Topology comparison
    if m1['topology'] == m2['topology']:
        reasons.append({
            'type': 'match',
            'text': "Identical branching structure!",
            'category': 'topology'
        })
    elif scores['topology']['score'] > 0.7:
        reasons.append({
            'type': 'similar',
            'text': "Similar branching pattern",
            'category': 'topology'
        })
    
    # Add overall assessment
    overall = sum(s['score'] for s in scores.values()) / len(scores)
    if overall > 0.8:
        reasons.insert(0, {
            'type': 'summary',
            'text': "Strong structural similarity",
            'category': 'overall'
        })
    elif overall > 0.6:
        reasons.insert(0, {
            'type': 'summary',
            'text': "Moderate structural similarity",
            'category': 'overall'
        })
    elif overall > 0.4:
        reasons.insert(0, {
            'type': 'summary',
            'text': "Some structural similarities",
            'category': 'overall'
        })
    else:
        reasons.insert(0, {
            'type': 'summary',
            'text': "Limited structural similarity",
            'category': 'overall'
        })
    
    return reasons

