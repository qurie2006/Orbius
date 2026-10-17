from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try importing chromadb if available
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except Exception:
    HAS_CHROMADB = False


class VectorStore:
    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir or str(Path(__file__).parent.parent / "chroma_db")
        self._chroma_client = None
        self._collections: Dict[str, Any] = {}
        # In-memory vector fallback index
        self._memory_index: Dict[str, List[Dict[str, Any]]] = {}

        if HAS_CHROMADB:
            try:
                os.makedirs(self.persist_dir, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(
                    path=self.persist_dir,
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info("ChromaDB vector store initialized at %s", self.persist_dir)
            except Exception as e:
                logger.warning("ChromaDB initialization failed (%s); falling back to in-memory vector store.", e)
                self._chroma_client = None

    def _get_collection(self, session_id: str):
        col_name = f"session_{session_id.replace('-', '_')}"
        if self._chroma_client:
            try:
                if col_name not in self._collections:
                    self._collections[col_name] = self._chroma_client.get_or_create_collection(
                        name=col_name,
                        metadata={"hnsw:space": "cosine"}
                    )
                return self._collections[col_name]
            except Exception as e:
                logger.warning("Chroma collection error (%s), using memory store", e)
        return None

    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using Gemini API if available, else semantic term vector."""
        try:
            from app.config import settings
            api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
            if api_key:
                from google import genai
                client = genai.Client(api_key=api_key)
                res = client.models.embed_content(
                    model="text-embedding-004",
                    contents=text[:2000]
                )
                if hasattr(res, "embedding") and res.embedding:
                    vec = getattr(res.embedding, "values", None) or list(res.embedding)
                    if vec:
                        return [float(x) for x in vec]
                elif hasattr(res, "embeddings") and res.embeddings:
                    vec = res.embeddings[0].values
                    if vec:
                        return [float(x) for x in vec]
        except Exception:
            pass

        # Fallback sparse term embedding
        words = text.lower().split()
        import hashlib
        dim = 128
        vec = [0.0] * dim
        for w in words:
            idx = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def add_chunks(self, session_id: str, chunks: List[Any]) -> None:
        if not chunks:
            return

        col = self._get_collection(session_id)
        docs = []
        ids = []
        metas = []
        embeddings = []

        for c in chunks:
            text = getattr(c, "text", "") or ""
            if not text.strip():
                continue
            chunk_id = getattr(c, "source_id", None) or str(len(ids))
            file_name = getattr(c, "file_name", "unknown")
            modality = getattr(c, "modality", "text")
            page_or_ts = getattr(c, "page_or_ts", "")

            docs.append(text)
            ids.append(f"{session_id}_{chunk_id}")
            metas.append({
                "file_name": file_name,
                "modality": modality,
                "page_or_ts": str(page_or_ts),
                "source_id": str(chunk_id)
            })
            emb = self._embed_text(text)
            embeddings.append(emb)

        if col:
            try:
                col.upsert(
                    ids=ids,
                    documents=docs,
                    metadatas=metas,
                    embeddings=embeddings
                )
            except Exception as e:
                logger.warning("Failed to upsert to ChromaDB (%s); recording in memory store", e)

        # Always update memory index as guaranteed fallback
        if session_id not in self._memory_index:
            self._memory_index[session_id] = []
        for i in range(len(ids)):
            self._memory_index[session_id].append({
                "id": ids[i],
                "text": docs[i],
                "metadata": metas[i],
                "embedding": embeddings[i]
            })

    def search(self, session_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_emb = self._embed_text(query)
        col = self._get_collection(session_id)

        if col:
            try:
                res = col.query(
                    query_embeddings=[query_emb],
                    n_results=min(top_k, max(1, col.count()))
                )
                if res and res.get("documents") and res["documents"][0]:
                    out = []
                    for i, doc in enumerate(res["documents"][0]):
                        meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                        cid = res["ids"][0][i] if res.get("ids") else f"chunk_{i}"
                        out.append({
                            "id": cid,
                            "text": doc,
                            "metadata": meta,
                            "score": 1.0 - (res["distances"][0][i] if res.get("distances") else 0.0)
                        })
                    if out:
                        return out
            except Exception as e:
                logger.warning("ChromaDB query error (%s); falling back to memory cosine search", e)

        # Fallback cosine search over memory index
        items = self._memory_index.get(session_id, [])
        if not items:
            return []

        scored = []
        for it in items:
            it_emb = it.get("embedding")
            if not it_emb:
                continue
            # Cosine similarity
            dot = sum(a * b for a, b in zip(query_emb, it_emb))
            norm_q = math.sqrt(sum(a * a for a in query_emb)) or 1.0
            norm_it = math.sqrt(sum(b * b for b in it_emb)) or 1.0
            sim = dot / (norm_q * norm_it)
            scored.append((sim, it))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": it["id"],
                "text": it["text"],
                "metadata": it["metadata"],
                "score": float(sim)
            }
            for sim, it in scored[:top_k]
        ]


# Singleton vector store instance
vector_store = VectorStore()
