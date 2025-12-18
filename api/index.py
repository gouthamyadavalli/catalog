"""
Vercel Serverless Function Entry Point

This module wraps the FastAPI application for Vercel deployment.
It handles data initialization on cold starts using in-memory LanceDB.
"""
import os
import sys

# Add the parent directory to the path so we can import catalog modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variable for Vercel deployment (use /tmp for writable storage)
os.environ["LANCEDB_PATH"] = "/tmp/lancedb_data"

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from mangum import Mangum

# Import the main FastAPI app
from catalog.main import app

# Data initialization flag
_data_initialized = False

def initialize_sample_data():
    """Initialize sample phylogenetic tree data on cold start."""
    global _data_initialized
    
    if _data_initialized:
        return
    
    try:
        from catalog.tree_db import list_trees, insert_tree, insert_nodes
        from catalog.tree_parser import create_phylo_tree
        from catalog.tree_embeddings import phylo2vec_encode, compute_all_node_embeddings, pad_embedding
        
        # Check if data already exists
        existing_trees = list_trees(limit=1)
        if existing_trees:
            print("Data already initialized")
            _data_initialized = True
            return
        
        print("Initializing sample phylogenetic tree data...")
        
        # Sample trees for demo
        sample_trees = [
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
        ]
        
        for name, newick in sample_trees:
            try:
                # Create tree and nodes
                phylo_tree, nodes = create_phylo_tree(newick, name, {})
                
                # Compute embeddings
                tree_embedding = phylo2vec_encode(newick, normalize=True)
                tree_embedding = pad_embedding(tree_embedding, 256)
                phylo_tree.embedding = tree_embedding
                
                # Compute node embeddings
                node_embeddings = compute_all_node_embeddings(nodes, dimension=64)
                for node in nodes:
                    node.position_embedding = node_embeddings.get(node.id, [])
                
                # Insert into database
                insert_tree(phylo_tree)
                insert_nodes(nodes)
                
                print(f"  Added: {name}")
            except Exception as e:
                print(f"  Failed to add {name}: {e}")
        
        _data_initialized = True
        print("Sample data initialization complete!")
        
    except Exception as e:
        print(f"Data initialization error: {e}")
        _data_initialized = True  # Don't retry on error


# Startup event to initialize data
@app.on_event("startup")
async def startup_event():
    initialize_sample_data()


# Create Mangum handler for AWS Lambda / Vercel
handler = Mangum(app, lifespan="off")

