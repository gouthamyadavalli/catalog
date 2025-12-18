#!/usr/bin/env python3
"""
Re-embed all trees with the improved Phylo2Vec encoding.
Run this after updating tree_embeddings.py to fix search quality.
"""
import sys
sys.path.insert(0, '.')

import lancedb
import numpy as np
from catalog.tree_embeddings import phylo2vec_encode, pad_embedding

DB_PATH = "./data/lancedb"
TREES_TABLE = "phylo_trees"

def main():
    print("=" * 60)
    print("Re-embedding all trees with improved Phylo2Vec encoding...")
    print("=" * 60)
    
    db = lancedb.connect(DB_PATH)
    
    if TREES_TABLE not in db.table_names():
        print("No trees table found!")
        return
    
    tbl = db.open_table(TREES_TABLE)
    df = tbl.to_pandas()
    
    print(f"\nFound {len(df)} trees to re-embed.\n")
    
    updated_count = 0
    
    for idx, row in df.iterrows():
        tree_id = row['id']
        name = row['name']
        newick = row['newick']
        
        try:
            # Generate new embedding
            new_embedding = phylo2vec_encode(newick, normalize=True)
            new_embedding = pad_embedding(new_embedding, 256)
            
            # Check quality
            emb_arr = np.array(new_embedding)
            non_zero = np.count_nonzero(emb_arr)
            norm = np.linalg.norm(emb_arr)
            
            # Update in database
            tbl.delete(f"id = '{tree_id}'")
            
            # Prepare record
            record = row.to_dict()
            record['embedding'] = new_embedding
            
            tbl.add([record])
            
            print(f"✓ {name[:40]:<40} | Non-zero: {non_zero:>3}/256 | Norm: {norm:.4f}")
            updated_count += 1
            
        except Exception as e:
            print(f"✗ {name[:40]:<40} | Error: {e}")
    
    print("\n" + "=" * 60)
    print(f"Done! Re-embedded {updated_count}/{len(df)} trees.")
    print("=" * 60)
    
    # Verify embeddings
    print("\nVerifying new embeddings...")
    tbl = db.open_table(TREES_TABLE)
    df_new = tbl.to_pandas()
    
    for _, row in df_new.head(3).iterrows():
        emb = row['embedding']
        emb_arr = np.array(emb)
        non_zero = np.count_nonzero(emb_arr)
        print(f"  {row['name'][:30]}: {non_zero} non-zero values")


if __name__ == "__main__":
    main()

