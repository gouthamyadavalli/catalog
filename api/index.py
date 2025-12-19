"""
Genomic Catalog - Phylogenetic Tree Search API
Deployed on Vercel Serverless Functions
"""
import uuid
from io import StringIO
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import numpy as np
from Bio import Phylo

# Create FastAPI app
app = FastAPI(title="Genomic Catalog", description="Phylogenetic tree search API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
_trees: Dict[str, Dict[str, Any]] = {}
_tree_nodes: Dict[str, Dict[str, Any]] = {}

# ============= Pydantic Models =============
class TreeSearchQuery(BaseModel):
    newick: str
    limit: int = 10

class ExplainRequest(BaseModel):
    query_newick: str
    result_tree_id: str

# ============= Tree Embedding =============
def phylo2vec_encode(newick_string: str, normalize: bool = True) -> List[float]:
    """Encode a phylogenetic tree into a 256-dim vector."""
    handle = StringIO(newick_string)
    tree = Phylo.read(handle, "newick")
    
    embedding = np.zeros(256)
    clades = list(tree.find_clades())
    leaves = list(tree.get_terminals())
    internal_nodes = [c for c in clades if not c.is_terminal()]
    
    # Feature Group 1: Basic stats (0-31)
    embedding[0] = len(leaves) / 100.0
    embedding[1] = len(internal_nodes) / 100.0
    embedding[2] = len(clades) / 100.0
    
    depths = tree.depths()
    if depths:
        embedding[3] = max(depths.values()) / 20.0
        embedding[4] = sum(depths.values()) / len(depths) / 20.0
    
    # Feature Group 2: Leaf depth histogram (32-63)
    leaf_depths = [depths.get(leaf, 0) for leaf in leaves]
    if leaf_depths:
        max_d = max(leaf_depths) or 1
        for d in leaf_depths:
            embedding[32 + min(int(d / max_d * 31), 31)] += 1.0 / len(leaf_depths)
    
    # Feature Group 3: Subtree sizes (64-95)
    def count_leaves(c):
        return 1 if c.is_terminal() else sum(count_leaves(x) for x in (c.clades or []))
    
    sizes = sorted([count_leaves(c) for c in internal_nodes])[:32]
    for i, s in enumerate(sizes):
        embedding[64 + i] = s / max(len(leaves), 1)
    
    # Feature Group 4: Split patterns (96-159)
    idx = 96
    for c in internal_nodes[:32]:
        if c.clades and len(c.clades) >= 2:
            l, r = count_leaves(c.clades[0]), count_leaves(c.clades[1]) if len(c.clades) > 1 else 0
            if l + r > 0:
                embedding[idx], embedding[idx + 1] = l / (l + r), r / (l + r)
            idx += 2
            if idx >= 160: break
    
    # Feature Group 5: Topology hash (160-223)
    def topo(c):
        return "L" if c.is_terminal() else f"({','.join(sorted(topo(x) for x in (c.clades or [])))})"
    h = hash(topo(tree.root))
    for i in range(64):
        embedding[160 + i] = ((h >> i) & 1) * 0.5
    
    # Feature Group 6: Branch lengths (224-255)
    bls = [c.branch_length for c in clades if c.branch_length]
    if bls:
        embedding[224:228] = [np.mean(bls) * 0.1, np.std(bls) * 0.1, max(bls) * 0.1, min(bls) * 0.1]
    
    if normalize:
        n = np.linalg.norm(embedding)
        if n > 0: embedding /= n
    
    return embedding.tolist()

def explain_similarity(newick1: str, newick2: str) -> Dict[str, Any]:
    """Explain similarity between two trees."""
    e1, e2 = np.array(phylo2vec_encode(newick1, False)), np.array(phylo2vec_encode(newick2, False))
    
    groups = [("Basic Statistics", 0, 32), ("Depth Distribution", 32, 64), ("Subtree Sizes", 64, 96),
              ("Split Patterns", 96, 160), ("Topology", 160, 224), ("Branch Lengths", 224, 256)]
    
    breakdown = []
    for name, s, e in groups:
        v1, v2, n1, n2 = e1[s:e], e2[s:e], np.linalg.norm(e1[s:e]), np.linalg.norm(e2[s:e])
        sim = float(np.dot(v1, v2) / (n1 * n2)) if n1 > 0 and n2 > 0 else (1.0 if n1 == 0 and n2 == 0 else 0.0)
        breakdown.append({"feature": name, "similarity": round(sim * 100, 1), "weight": round((n1 + n2) / 2, 3)})
    
    n1, n2 = np.linalg.norm(e1), np.linalg.norm(e2)
    overall = float(np.dot(e1, e2) / (n1 * n2)) if n1 > 0 and n2 > 0 else 0
    
    return {"overall_similarity": round(overall * 100, 1), "feature_breakdown": breakdown,
            "insights": [f"Overall structural similarity: {round(overall * 100, 1)}%"]}

# ============= Initialize Sample Data =============
def init_data():
    samples = [
        ("Primate Evolution", "((Human:0.1,Chimp:0.1):0.3,(Gorilla:0.2,Orangutan:0.2):0.2);"),
        ("Great Apes", "(((Human:0.5,Chimp:0.5):0.3,Gorilla:0.8):0.2,Orangutan:1.0);"),
        ("Mammalian Orders", "((((Human,Mouse):0.3,Dog):0.2,Elephant):0.1,Platypus);"),
        ("Bacterial 16S", "(((E_coli,Salmonella):0.1,Bacillus):0.2,(Streptococcus,Staphylococcus):0.15);"),
        ("Virus Evolution", "((SARS_CoV_2,SARS_CoV):0.3,(MERS,Common_Cold):0.4);"),
        ("Plant Phylogeny", "(((Arabidopsis,Rice):0.2,(Tomato,Potato):0.15):0.1,Pine);"),
        ("Bird Evolution", "((Eagle,Hawk):0.1,((Penguin,Ostrich):0.2,Chicken):0.15);"),
        ("Fish Diversity", "(((Salmon,Trout):0.1,Tuna):0.2,(Shark,Ray):0.3);"),
        ("Fungi Kingdom", "((Yeast,Candida):0.2,((Mushroom,Truffle):0.1,Mold):0.15);"),
        ("Insect Orders", "(((Butterfly,Moth):0.1,Beetle):0.2,(Ant,Bee):0.15);"),
        ("Hominid Branch", "((Human:0.2,Chimp:0.2):0.5,Gorilla:0.7);"),
        ("Canine Family", "((Dog:0.1,Wolf:0.1):0.2,(Fox:0.15,Jackal:0.15):0.25);"),
        ("Feline Family", "((Lion:0.1,Tiger:0.1):0.2,(Cat:0.15,Leopard:0.15):0.25);"),
        ("Cetacean Tree", "((Dolphin:0.1,Porpoise:0.1):0.2,(Whale:0.15,Orca:0.15):0.25);"),
        ("Reptile Evolution", "(((Snake:0.2,Lizard:0.2):0.1,Crocodile):0.3,Turtle);"),
    ]
    
    import hashlib
    
    def make_node_id(tree_id: str, index: int) -> str:
        """Generate deterministic node ID based on tree and index."""
        return hashlib.md5(f"{tree_id}:node:{index}".encode()).hexdigest()[:16]
    
    for name, newick in samples:
        tid = name.lower().replace(" ", "_")
        handle = StringIO(newick)
        tree = Phylo.read(handle, "newick")
        
        _trees[tid] = {
            'id': tid, 'name': name, 'newick': newick,
            'embedding': phylo2vec_encode(newick),
            'num_leaves': len(list(tree.get_terminals())),
            'num_nodes': len(list(tree.find_clades())),
            'metadata': {}, 'created_at': datetime.now()
        }
        
        # Extract nodes with deterministic IDs
        depths = tree.depths()
        all_clades = list(tree.find_clades())
        clade_ids = {id(c): make_node_id(tid, i) for i, c in enumerate(all_clades)}
        parent_map = {id(ch): id(p) for p in all_clades for ch in (p.clades or [])}
        
        for c in all_clades:
            chs = c.clades or []
            _tree_nodes[clade_ids[id(c)]] = {
                'id': clade_ids[id(c)], 'tree_id': tid, 'name': c.name,
                'parent_id': clade_ids[parent_map[id(c)]] if id(c) in parent_map else None,
                'left_child_id': clade_ids[id(chs[0])] if len(chs) > 0 else None,
                'right_child_id': clade_ids[id(chs[1])] if len(chs) > 1 else None,
                'depth': int(depths.get(c, 0)), 'branch_length': float(c.branch_length or 0),
                'is_leaf': c.is_terminal()
            }

init_data()

# ============= API Endpoints =============
@app.get("/")
async def root():
    return HTMLResponse('<html><head><meta http-equiv="refresh" content="0;url=/index.html"></head></html>')

@app.get("/stats")
async def stats():
    return {"total_sequences": 0, "total_trees": len(_trees), "embedding_dimension": 256, "storage_type": "in-memory"}

@app.get("/trees")
async def list_trees(limit: int = 100):
    return {"trees": [{"id": t['id'], "name": t['name'], "newick": t['newick'], "num_leaves": t['num_leaves'],
                       "num_nodes": t['num_nodes'], "metadata": {}, "created_at": t['created_at'].isoformat()}
                      for t in list(_trees.values())[:limit]], "total": len(_trees)}

@app.get("/trees/{tree_id}")
async def get_tree(tree_id: str):
    t = _trees.get(tree_id)
    if not t: raise HTTPException(404, "Tree not found")
    return {"id": t['id'], "name": t['name'], "newick": t['newick'], "num_leaves": t['num_leaves'],
            "num_nodes": t['num_nodes'], "metadata": {}, "created_at": t['created_at'].isoformat()}

@app.get("/trees/{tree_id}/nodes")
async def get_nodes(tree_id: str):
    nodes = [n for n in _tree_nodes.values() if n['tree_id'] == tree_id]
    if not nodes: raise HTTPException(404, "Tree not found")
    return {"nodes": nodes}

@app.get("/trees/{tree_id}/root")
async def get_root(tree_id: str):
    for n in _tree_nodes.values():
        if n['tree_id'] == tree_id and n['parent_id'] is None:
            return n
    raise HTTPException(404, "Root not found")

@app.get("/trees/{tree_id}/subtree/{node_id}/newick")
async def get_subtree(tree_id: str, node_id: str, include_branch_lengths: bool = False):
    node = _tree_nodes.get(node_id)
    if not node or node['tree_id'] != tree_id: raise HTTPException(404, "Node not found")
    
    def build(n):
        if n['is_leaf']:
            return f"{n['name'] or ''}:{n['branch_length']}" if include_branch_lengths and n['branch_length'] else (n['name'] or '')
        parts = [build(_tree_nodes[cid]) for cid in [n['left_child_id'], n['right_child_id']] if cid and cid in _tree_nodes]
        sub = f"({','.join(parts)})"
        return f"{sub}:{n['branch_length']}" if include_branch_lengths and n['branch_length'] else sub
    
    def get_ids(n):
        ids = [n['id']]
        for cid in [n['left_child_id'], n['right_child_id']]:
            if cid and cid in _tree_nodes: ids.extend(get_ids(_tree_nodes[cid]))
        return ids
    
    return {"newick": build(node) + ";", "node_ids": get_ids(node)}

@app.post("/trees/search/similar")
async def search_similar(query: TreeSearchQuery):
    try:
        qv = np.array(phylo2vec_encode(query.newick))
        qn = np.linalg.norm(qv)
        if qn == 0: return {"results": [], "query_info": {"num_leaves": 0}}
        qv /= qn
        
        results = []
        for t in _trees.values():
            if not t.get('embedding'): continue
            tv = np.array(t['embedding'])
            tn = np.linalg.norm(tv)
            if tn == 0: continue
            sim = float(np.dot(qv, tv / tn))
            results.append({"tree_id": t['id'], "tree_name": t['name'], "similarity": max(0, min(1, sim)),
                           "num_leaves": t['num_leaves'], "newick": t['newick']})
        
        results.sort(key=lambda x: -x['similarity'])
        
        try:
            h = StringIO(query.newick)
            nl = len(list(Phylo.read(h, "newick").get_terminals()))
        except: nl = 0
        
        return {"results": results[:query.limit], "query_info": {"num_leaves": nl}}
    except Exception as e:
        raise HTTPException(400, f"Invalid Newick: {e}")

@app.post("/trees/explain-similarity")
async def explain(request: ExplainRequest):
    t = _trees.get(request.result_tree_id)
    if not t: raise HTTPException(404, "Tree not found")
    try: return explain_similarity(request.query_newick, t['newick'])
    except Exception as e: raise HTTPException(400, str(e))
