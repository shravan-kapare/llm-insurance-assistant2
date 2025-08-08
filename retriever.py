from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

model = None  # lazy loaded

def get_model():
    global model
    if model is None:
        model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

def build_vector_index(chunks):
    embeddings = get_model().encode(chunks)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings))
    # Return in-memory index and chunks
    return index, chunks

def search(query, index, chunks, top_k=5):
    query_vec = get_model().encode([query])
    D, I = index.search(np.array(query_vec), top_k)
    return [(i, chunks[i]) for i in I[0]]
