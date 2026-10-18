from __future__ import annotations

import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try importing chromadb if available
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except Exception as e:
    HAS_CHROMADB = False
    logger.warning("ChromaDB not available: %s", e)


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

    def _clean_collection_name(self, session_id: str) -> str:
        """ChromaDB collection names must be 3-63 chars, start and end with alphanumeric,
        and only contain alphanumeric, underscores, and hyphens."""
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id).strip("_")
        if not clean:
            clean = "default"
        name = f"sess_{clean}"[:63]
        while len(name) < 3:
            name += "_0"
        if not name[-1].isalnum():
            name = name[:-1] + "1"
        if not name[0].isalnum():
            name = "s" + name[1:]
        return name

    def _get_collection(self, session_id: str):
        if not self._chroma_client:
            return None
        col_name = self._clean_collection_name(session_id)
        try:
            if col_name not in self._collections:
                self._collections[col_name] = self._chroma_client.get_or_create_collection(
                    name=col_name,
                    metadata={"hnsw:space": "cosine"}
                )
            return self._collections[col_name]
        except Exception as e:
            logger.warning("Chroma collection error for '%s' (%s), using memory store", col_name, e)
            return None

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Gemini API (gemini-embedding-001) with fallback to term vectors."""
        if not texts:
            return []

        # 1. Try Gemini Embeddings
        try:
            from app.config import settings
            api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
            if api_key:
                from google import genai
                client = genai.Client(api_key=api_key)
                
                # Truncate texts to avoid token limits
                truncated = [t[:2500] if t else " " for t in texts]
                
                # Batch embed
                res = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=truncated
                )
                
                if hasattr(res, "embeddings") and res.embeddings:
                    out = []
                    for emb in res.embeddings:
                        vals = getattr(emb, "values", None) or list(emb)
                        out.append([float(x) for x in vals])
                    if len(out) == len(texts):
                        return out
                elif hasattr(res, "embedding") and res.embedding:
                    vals = getattr(res.embedding, "values", None) or list(res.embedding)
                    return [[float(x) for x in vals]]
        except Exception as err:
            logger.debug("Gemini embedding API failed (%s); falling back to sparse term vectors.", err)

        # 2. Deterministic term vector fallback (128-dim normalized)
        import hashlib
        dim = 128
        out = []
        for text in texts:
            words = (text or "").lower().split()
            vec = [0.0] * dim
            for w in words:
                idx = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out

    def _embed_text(self, text: str) -> List[float]:
        res = self._embed_texts([text])
        return res[0] if res else [0.0] * 128

    def add_chunks(self, session_id: str, chunks: List[Any]) -> int:
        if not chunks:
            return 0

        valid_chunks = []
        texts = []
        for c in chunks:
            text = getattr(c, "text", "") or ""
            if text.strip():
                valid_chunks.append(c)
                texts.append(text)

        if not valid_chunks:
            return 0

        # Batch embed for performance
        embeddings = self._embed_texts(texts)

        docs = []
        ids = []
        metas = []

        for i, c in enumerate(valid_chunks):
            chunk_id = getattr(c, "source_id", None) or str(i)
            file_name = getattr(c, "file_name", "unknown")
            modality = getattr(c, "modality", "text")
            page_or_ts = getattr(c, "page_or_ts", "")

            # Deterministic ID per session and chunk
            doc_id = f"{session_id}_{file_name}_{chunk_id}"
            clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", doc_id)[:100]

            docs.append(texts[i])
            ids.append(clean_id)
            metas.append({
                "file_name": file_name,
                "modality": modality,
                "page_or_ts": str(page_or_ts),
                "source_id": str(chunk_id),
                "session_id": session_id,
            })

        # Upsert to ChromaDB
        col = self._get_collection(session_id)
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
        
        # Replace existing or append
        existing_ids = {item["id"] for item in self._memory_index[session_id]}
        for i in range(len(ids)):
            if ids[i] not in existing_ids:
                self._memory_index[session_id].append({
                    "id": ids[i],
                    "text": docs[i],
                    "metadata": metas[i],
                    "embedding": embeddings[i]
                })

        return len(ids)

    def search(self, session_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []

        query_emb = self._embed_text(query)
        col = self._get_collection(session_id)

        if col:
            try:
                count = col.count()
                if count > 0:
                    res = col.query(
                        query_embeddings=[query_emb],
                        n_results=min(top_k, count)
                    )
                    if res and res.get("documents") and res["documents"][0]:
                        out = []
                        for i, doc in enumerate(res["documents"][0]):
                            meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                            cid = res["ids"][0][i] if res.get("ids") else f"chunk_{i}"
                            dist = res["distances"][0][i] if res.get("distances") else 0.0
                            out.append({
                                "id": cid,
                                "text": doc,
                                "metadata": meta,
                                "score": round(max(0.0, 1.0 - dist), 4),
                                "source": "chromadb",
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
                "score": round(float(sim), 4),
                "source": "memory_fallback",
            }
            for sim, it in scored[:top_k]
        ]

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Inspect vector database status, persistence, and chunk counts."""
        col = self._get_collection(session_id)
        chroma_count = 0
        if col:
            try:
                chroma_count = col.count()
            except Exception:
                chroma_count = 0

        memory_count = len(self._memory_index.get(session_id, []))

        return {
            "has_chromadb": HAS_CHROMADB,
            "engine": "ChromaDB Persistent (HNSW Cosine)" if col else "In-Memory Vector Fallback",
            "persist_dir": self.persist_dir,
            "session_id": session_id,
            "chroma_chunks": chroma_count,
            "memory_chunks": memory_count,
            "total_chunks_indexed": max(chroma_count, memory_count),
            "embedding_model": "gemini-embedding-001 (3072-dim)" if os.environ.get("GEMINI_API_KEY") else "sparse-term-vector (128-dim)"
        }


# Singleton vector store instance
vector_store = VectorStore()
