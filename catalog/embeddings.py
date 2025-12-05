from abc import ABC, abstractmethod
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

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
        print(f"Loading SentenceTransformer model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        
    def encode(self, texts: List[str]) -> List[List[float]]:
        # SentenceTransformers handles batching internally, but we can also batch here if needed.
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

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

def get_embedding_model(model_type: str = "sentence-transformer", **kwargs) -> EmbeddingModel:
    global _current_model
    if _current_model is None:
        if model_type == "sentence-transformer":
            _current_model = SentenceTransformerModel(**kwargs)
        elif model_type == "mock":
            _current_model = MockBioModel(**kwargs)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    return _current_model
