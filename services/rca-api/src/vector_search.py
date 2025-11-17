"""Vector Search using FAISS (AgentDB incompatible with Pydantic v2)"""

import faiss
import numpy as np

class VectorSearch:
    def __init__(self, dimension=384):
        self.index = faiss.IndexFlatL2(dimension)
        self.documents = []

    def add(self, vector, document):
        self.index.add(np.array([vector]))
        self.documents.append(document)

    def search(self, query_vector, k=5):
        distances, indices = self.index.search(np.array([query_vector]), k)
        return [(self.documents[i], distances[0][j]) for j, i in enumerate(indices[0])]
