from abc import ABC, abstractmethod
from typing import List
import hashlib
import numpy as np

# Try to import sentence-transformers, but make it optional
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

class EmbeddingModel(ABC):
    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts (sequences) into embeddings.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Return the dimension of the embeddings.
        """
        pass

class SentenceTransformerModel(EmbeddingModel):
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not available. "
                "Use model_type='hash' or install sentence-transformers."
            )
        print(f"Loading SentenceTransformer model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        
    def encode(self, texts: List[str]) -> List[List[float]]:
        # SentenceTransformers handles batching internally, but we can also batch here if needed.
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

class HashEmbeddingModel(EmbeddingModel):
    """
    A lightweight embedding model that uses hashing to create deterministic
    embeddings without requiring heavy ML dependencies like PyTorch.
    
    This is suitable for serverless deployments where dependency size matters.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        
    def encode(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            # Create multiple hash-based features
            vec = np.zeros(self.dimension)
            
            # Use multiple hash functions for different parts of the vector
            for i in range(4):
                seed_text = f"{i}:{text}"
                h = hashlib.sha256(seed_text.encode()).digest()
                # Use hash bytes as seed for reproducible random
                np.random.seed(int.from_bytes(h[:4], 'big'))
                vec[i * (self.dimension // 4):(i + 1) * (self.dimension // 4)] = \
                    np.random.randn(self.dimension // 4)
            
            # Add k-mer features for biological sequences
            if len(text) >= 3:
                # Count 3-mers
                kmers = {}
                for j in range(len(text) - 2):
                    kmer = text[j:j+3]
                    kmers[kmer] = kmers.get(kmer, 0) + 1
                
                # Hash k-mer counts into part of the vector
                for kmer, count in kmers.items():
                    idx = hash(kmer) % (self.dimension // 4)
                    vec[idx] += count * 0.1
            
            # Normalize to unit length
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            
            embeddings.append(vec.tolist())
        
        return embeddings

    def get_dimension(self) -> int:
        return self.dimension

class MockBioModel(EmbeddingModel):
    """
    A mock model that generates random embeddings for testing scale
    without the overhead of a real neural network.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        
    def encode(self, texts: List[str]) -> List[List[float]]:
        # Generate random vectors normalized to unit length
        vecs = np.random.randn(len(texts), self.dimension)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return (vecs / norms).tolist()

    def get_dimension(self) -> int:
        return self.dimension

# Factory to get the configured model
_current_model = None

def get_embedding_model(model_type: str = "auto", **kwargs) -> EmbeddingModel:
    """
    Get the embedding model. 
    
    model_type options:
        - "auto": Use sentence-transformer if available, otherwise hash
        - "sentence-transformer": Use SentenceTransformer (requires PyTorch)
        - "hash": Use lightweight hash-based embeddings
        - "mock": Use random embeddings for testing
    """
    global _current_model
    if _current_model is None:
        if model_type == "auto":
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                model_type = "sentence-transformer"
            else:
                model_type = "hash"
                print("sentence-transformers not available, using hash embeddings")
        
        if model_type == "sentence-transformer":
            _current_model = SentenceTransformerModel(**kwargs)
        elif model_type == "hash":
            _current_model = HashEmbeddingModel(**kwargs)
        elif model_type == "mock":
            _current_model = MockBioModel(**kwargs)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    return _current_model
