"""Step 3 — build the FAISS vector index over the KB (local, free embeddings).

Run once after editing knowledge_base.py:  python index.py
"""
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from knowledge_base import KB_DOCS

model = SentenceTransformer("all-MiniLM-L6-v2")
texts = [d["text"] for d in KB_DOCS]
emb = model.encode(texts, normalize_embeddings=True).astype("float32")

index = faiss.IndexFlatIP(emb.shape[1])  # inner product on normalized vecs = cosine
index.add(emb)

faiss.write_index(index, "kb.index")
with open("kb_meta.pkl", "wb") as f:
    pickle.dump(KB_DOCS, f)

print(f"OK  indexed {len(KB_DOCS)} KB docs -> kb.index")
