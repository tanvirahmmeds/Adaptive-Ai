"""
Vector Memory - Semantic search with embeddings for the Adaptive Framework.
"""

import asyncio
import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import hashlib

# Try to import embedding libraries
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None

logger = logging.getLogger(__name__)


@dataclass
class VectorEntry:
    """A vector embedding entry."""
    id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    memory_id: Optional[str] = None  # Link to MemoryEntry


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""
    
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        pass
    
    @abstractmethod
    def dimension(self) -> int:
        pass


class SentenceTransformerProvider(EmbeddingProvider):
    """Sentence Transformers embedding provider."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError("sentence-transformers not installed. pip install sentence-transformers")
        self.model = SentenceTransformer(model_name)
        self._dimension = self.model.get_sentence_embedding_dimension()
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self.model.encode, texts)
        return embeddings.tolist()
    
    def dimension(self) -> int:
        return self._dimension


class HashEmbeddingProvider(EmbeddingProvider):
    """Simple hash-based embedding (no ML dependencies)."""
    
    def __init__(self, dimension: int = 384):
        self._dimension = dimension
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            # Create deterministic hash-based embedding
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            
            # Convert to float vector
            vec = []
            for i in range(0, min(len(hash_bytes), self._dimension * 4), 4):
                chunk = hash_bytes[i:i+4]
                if len(chunk) == 4:
                    val = int.from_bytes(chunk, 'big') / 0xFFFFFFFF
                    vec.append(val * 2 - 1)  # Normalize to [-1, 1]
            
            # Pad or truncate
            if len(vec) < self._dimension:
                vec.extend([0.0] * (self._dimension - len(vec)))
            else:
                vec = vec[:self._dimension]
            
            embeddings.append(vec)
        
        return embeddings
    
    def dimension(self) -> int:
        return self._dimension


class VectorStore(ABC):
    """Abstract vector store."""
    
    @abstractmethod
    async def add(self, entries: List[VectorEntry]):
        pass
    
    @abstractmethod
    async def search(self, query_vector: List[float], limit: int = 10, threshold: float = 0.5) -> List[Tuple[VectorEntry, float]]:
        pass
    
    @abstractmethod
    async def delete(self, entry_id: str):
        pass
    
    @abstractmethod
    async def get(self, entry_id: str) -> Optional[VectorEntry]:
        pass


class SQLiteVectorStore(VectorStore):
    """SQLite-based vector store with cosine similarity."""
    
    def __init__(self, db_path: Path, dimension: int):
        self.db_path = Path(db_path)
        self.dimension = dimension
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS vectors (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    memory_id TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_id ON vectors(memory_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON vectors(created_at)")
    
    def _serialize_vector(self, vec: List[float]) -> bytes:
        if HAS_NUMPY:
            return np.array(vec, dtype=np.float32).tobytes()
        else:
            return json.dumps(vec).encode()
    
    def _deserialize_vector(self, data: bytes) -> List[float]:
        if HAS_NUMPY:
            return np.frombuffer(data, dtype=np.float32).tolist()
        else:
            return json.loads(data.decode())
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if HAS_NUMPY:
            a_np = np.array(a)
            b_np = np.array(b)
            return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))
        else:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(y * y for y in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)
    
    async def add(self, entries: List[VectorEntry]):
        with sqlite3.connect(self.db_path) as conn:
            for entry in entries:
                conn.execute("""
                    INSERT OR REPLACE INTO vectors (id, text, embedding, metadata, created_at, memory_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    entry.id,
                    entry.text,
                    self._serialize_vector(entry.embedding),
                    json.dumps(entry.metadata),
                    entry.created_at.isoformat(),
                    entry.memory_id
                ))
    
    async def search(self, query_vector: List[float], limit: int = 10, threshold: float = 0.5) -> List[Tuple[VectorEntry, float]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT id, text, embedding, metadata, created_at, memory_id FROM vectors").fetchall()
            
            results = []
            for row in rows:
                entry = VectorEntry(
                    id=row[0],
                    text=row[1],
                    embedding=self._deserialize_vector(row[2]),
                    metadata=json.loads(row[3]),
                    created_at=datetime.fromisoformat(row[4]),
                    memory_id=row[5]
                )
                score = self._cosine_similarity(query_vector, entry.embedding)
                if score >= threshold:
                    results.append((entry, score))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
    
    async def delete(self, entry_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM vectors WHERE id=?", (entry_id,))
    
    async def get(self, entry_id: str) -> Optional[VectorEntry]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT id, text, embedding, metadata, created_at, memory_id FROM vectors WHERE id=?", (entry_id,)).fetchone()
            if row:
                return VectorEntry(
                    id=row[0],
                    text=row[1],
                    embedding=self._deserialize_vector(row[2]),
                    metadata=json.loads(row[3]),
                    created_at=datetime.fromisoformat(row[4]),
                    memory_id=row[5]
                )
            return None


class FaissVectorStore(VectorStore):
    """FAISS-based vector store for large-scale similarity search."""
    
    def __init__(self, db_path: Path, dimension: int):
        if not HAS_NUMPY:
            raise ImportError("numpy required for FAISS")
        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            raise ImportError("faiss-cpu not installed. pip install faiss-cpu")
        
        self.db_path = Path(db_path)
        self.dimension = dimension
        self.index_path = self.db_path.with_suffix('.faiss')
        self.meta_path = self.db_path.with_suffix('.meta')
        
        self.index = None
        self.metadata: Dict[int, Dict] = {}
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: Dict[int, str] = {}
        self._next_idx = 0
        
        self._load_or_create()
    
    def _load_or_create(self):
        if self.index_path.exists() and self.meta_path.exists():
            self.index = self.faiss.read_index(str(self.index_path))
            with open(self.meta_path, 'r') as f:
                data = json.load(f)
                self.metadata = {int(k): v for k, v in data['metadata'].items()}
                self.id_to_idx = data['id_to_idx']
                self.idx_to_id = {int(k): v for k, v in data['idx_to_id'].items()}
                self._next_idx = data['next_idx']
        else:
            self.index = self.faiss.IndexFlatIP(self.dimension)  # Inner product (cosine with normalized vectors)
            self.metadata = {}
            self.id_to_idx = {}
            self.idx_to_id = {}
            self._next_idx = 0
    
    def _save(self):
        self.faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, 'w') as f:
            json.dump({
                'metadata': self.metadata,
                'id_to_idx': self.id_to_idx,
                'idx_to_id': self.idx_to_id,
                'next_idx': self._next_idx
            }, f)
    
    def _normalize(self, vec: List[float]):
        import numpy as np
        arr = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr
    
    async def add(self, entries: List[VectorEntry]):
        import numpy as np
        vectors = []
        for entry in entries:
            idx = self._next_idx
            self._next_idx += 1
            
            self.id_to_idx[entry.id] = idx
            self.idx_to_id[idx] = entry.id
            self.metadata[idx] = {
                'text': entry.text,
                'metadata': entry.metadata,
                'created_at': entry.created_at.isoformat(),
                'memory_id': entry.memory_id
            }
            vectors.append(self._normalize(entry.embedding))
        
        if vectors:
            self.index.add(np.vstack(vectors))
            self._save()
    
    async def search(self, query_vector: List[float], limit: int = 10, threshold: float = 0.5) -> List[Tuple[VectorEntry, float]]:
        import numpy as np
        if self.index.ntotal == 0:
            return []
        
        query_norm = self._normalize(query_vector).reshape(1, -1)
        scores, indices = self.index.search(query_norm, min(limit * 2, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or score < threshold:
                continue
            
            entry_id = self.idx_to_id.get(int(idx))
            if not entry_id:
                continue
            
            meta = self.metadata.get(int(idx), {})
            entry = VectorEntry(
                id=entry_id,
                text=meta.get('text', ''),
                embedding=[],  # Not stored in FAISS metadata
                metadata=meta.get('metadata', {}),
                created_at=datetime.fromisoformat(meta.get('created_at', datetime.now().isoformat())),
                memory_id=meta.get('memory_id')
            )
            results.append((entry, float(score)))
        
        return results[:limit]
    
    async def delete(self, entry_id: str):
        # FAISS doesn't support deletion easily - mark as deleted in metadata
        idx = self.id_to_idx.get(entry_id)
        if idx is not None:
            self.metadata[idx]['deleted'] = True
            self._save()
    
    async def get(self, entry_id: str) -> Optional[VectorEntry]:
        idx = self.id_to_idx.get(entry_id)
        if idx is not None and not self.metadata.get(idx, {}).get('deleted'):
            meta = self.metadata[idx]
            return VectorEntry(
                id=entry_id,
                text=meta.get('text', ''),
                embedding=[],
                metadata=meta.get('metadata', {}),
                created_at=datetime.fromisoformat(meta.get('created_at', datetime.now().isoformat())),
                memory_id=meta.get('memory_id')
            )
        return None


class VectorMemoryManager:
    """Manages vector embeddings for semantic memory search."""
    
    def __init__(self, 
                 store: VectorStore,
                 provider: EmbeddingProvider,
                 memory_manager = None):
        self.store = store
        self.provider = provider
        self.memory_manager = memory_manager
        self._batch_buffer: List[VectorEntry] = []
        self._batch_size = 10
    
    async def add_text(self, 
                      text: str, 
                      metadata: Dict[str, Any] = None,
                      memory_id: str = None) -> str:
        """Add text to vector store."""
        entry_id = str(uuid.uuid4())
        embedding = (await self.provider.embed([text]))[0]
        
        entry = VectorEntry(
            id=entry_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {},
            memory_id=memory_id
        )
        
        await self.store.add([entry])
        return entry_id
    
    async def add_memory(self, memory_entry) -> str:
        """Add a memory entry to vector store."""
        # Create searchable text from memory
        text_parts = []
        if isinstance(memory_entry.content, dict):
            for k, v in memory_entry.content.items():
                text_parts.append(f"{k}: {v}")
        else:
            text_parts.append(str(memory_entry.content))
        
        if memory_entry.context:
            for k, v in memory_entry.context.items():
                text_parts.append(f"context_{k}: {v}")
        
        text = " | ".join(text_parts)
        
        return await self.add_text(
            text=text,
            metadata={
                'type': memory_entry.type,
                'source': memory_entry.source,
                'confidence': memory_entry.confidence,
                'tags': list(memory_entry.tags)
            },
            memory_id=memory_entry.id
        )
    
    async def search(self, 
                    query: str, 
                    limit: int = 10, 
                    threshold: float = 0.5,
                    filter_metadata: Dict[str, Any] = None) -> List[Tuple[VectorEntry, float]]:
        """Semantic search for similar memories."""
        query_embedding = (await self.provider.embed([query]))[0]
        results = await self.store.search(query_embedding, limit=limit * 2, threshold=threshold)
        
        # Apply metadata filters
        if filter_metadata:
            filtered = []
            for entry, score in results:
                match = True
                for k, v in filter_metadata.items():
                    if entry.metadata.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append((entry, score))
            results = filtered
        
        return results[:limit]
    
    async def search_by_memory_id(self, memory_id: str, limit: int = 5) -> List[VectorEntry]:
        """Find vector entries linked to a memory."""
        # This would require an index on memory_id - simplified for now
        all_results = await self.store.search([0.0] * self.provider.dimension(), limit=1000, threshold=-1.0)
        return [entry for entry, _ in all_results if entry.memory_id == memory_id][:limit]
    
    async def get_context_for_query(self, query: str, max_tokens: int = 2000) -> List[Dict[str, Any]]:
        """Get relevant context for a query, formatted for LLM."""
        results = await self.search(query, limit=20, threshold=0.4)
        
        context = []
        token_count = 0
        
        for entry, score in results:
            text = entry.text
            # Rough token estimation
            est_tokens = len(text) // 4
            if token_count + est_tokens > max_tokens:
                break
            
            context.append({
                'text': text,
                'score': score,
                'metadata': entry.metadata,
                'memory_id': entry.memory_id
            })
            token_count += est_tokens
        
        return context


# Factory function
async def create_vector_memory(data_dir: Path, 
                              model_name: str = "all-MiniLM-L6-v2",
                              use_faiss: bool = False) -> VectorMemoryManager:
    """Create vector memory with best available provider."""
    
    # Try sentence transformers first
    provider = None
    if HAS_SENTENCE_TRANSFORMERS:
        try:
            provider = SentenceTransformerProvider(model_name)
            logger.info(f"Using SentenceTransformer: {model_name}")
        except Exception as e:
            logger.warning(f"Failed to load SentenceTransformer: {e}")
    
    # Fallback to hash embeddings
    if provider is None:
        provider = HashEmbeddingProvider(dimension=384)
        logger.info("Using hash-based embeddings (no ML deps)")
    
    # Create store
    dimension = provider.dimension()
    if use_faiss and HAS_NUMPY:
        try:
            store = FaissVectorStore(data_dir / "vectors.db", dimension)
            logger.info("Using FAISS vector store")
        except Exception as e:
            logger.warning(f"FAISS not available: {e}")
            store = SQLiteVectorStore(data_dir / "vectors.db", dimension)
    else:
        store = SQLiteVectorStore(data_dir / "vectors.db", dimension)
        logger.info("Using SQLite vector store")
    
    return VectorMemoryManager(store, provider)