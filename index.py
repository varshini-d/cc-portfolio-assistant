"""Step 3 — build the FAISS vector index over the KB (local, free embeddings).

Run once after editing knowledge_base.py:  python index.py

build_index() is also called at app startup (see app.py) so a fresh deploy can
regenerate the index from source, since kb.index is gitignored.
"""
import pickle

import faiss
from sentence_transformers import SentenceTransformer

from knowledge_base import KB_DOCS


def build_index(model=None):
    """Embed the KB docs and write kb.index + kb_meta.pkl. Returns doc count."""
    model = model or SentenceTransformer("all-MiniLM-L6-v2")
    texts = [d["text"] for d in KB_DOCS]
    emb = model.encode(texts, normalize_embeddings=True).astype("float32")

    index = faiss.IndexFlatIP(emb.shape[1])  # inner product on normalized vecs = cosine
    index.add(emb)

    faiss.write_index(index, "kb.index")
    with open("kb_meta.pkl", "wb") as f:
        pickle.dump(KB_DOCS, f)
    return len(KB_DOCS)


if __name__ == "__main__":
    n = build_index()
    print(f"OK  indexed {n} KB docs -> kb.index")
