"""
Memory & Learning System - Persistent memory with feedback-driven improvement.
"""

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    type: str  # fact, preference, pattern, skill, correction
    content: Dict[str, Any]
    context: Dict[str, Any]
    confidence: float  # 0.0 - 1.0
    source: str  # user, system, inferred
    created_at: datetime
    updated_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: Set[str] = field(default_factory=set)
    feedback: List[Dict[str, Any]] = field(default_factory=list)  # positive/negative feedback


@dataclass
class LearningSignal:
    """A signal that triggers learning."""
    type: str  # explicit_feedback, implicit_feedback, pattern_detected, correction
    source: str
    target_id: Optional[str]  # memory entry ID if related
    data: Dict[str, Any]
    weight: float  # importance 0.0 - 1.0


class MemoryStore(ABC):
    """Abstract memory backend."""
    
    @abstractmethod
    async def store(self, entry: MemoryEntry):
        pass
    
    @abstractmethod
    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        pass
    
    @abstractmethod
    async def query(self, 
                   type_filter: Optional[str] = None,
                   tags: Optional[Set[str]] = None,
                   context_match: Optional[Dict[str, Any]] = None,
                   min_confidence: float = 0.0,
                   limit: int = 50) -> List[MemoryEntry]:
        pass
    
    @abstractmethod
    async def update(self, entry: MemoryEntry):
        pass
    
    @abstractmethod
    async def delete(self, entry_id: str):
        pass


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed persistent memory."""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT,
                    tags TEXT NOT NULL,
                    feedback TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON memories(confidence)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags ON memories(tags)")
    
    def _row_to_entry(self, row) -> MemoryEntry:
        # Handle potential schema mismatch where columns might be shifted
        # Expected columns: id, type, content, context, confidence, source, created_at, updated_at, access_count, last_accessed, tags, feedback
        # If source is a datetime string, columns are shifted
        source_val = row[5]
        created_at_val = row[6]
        updated_at_val = row[7]
        
        # Check if columns are shifted (source contains datetime-like string)
        if source_val and ('T' in source_val or '-' in source_val) and len(source_val) > 10:
            # Columns are shifted - source is actually created_at, created_at is updated_at, etc.
            created_at_val = source_val
            updated_at_val = row[6]
            source_val = "system"  # default
        
        return MemoryEntry(
            id=row[0],
            type=row[1],
            content=json.loads(row[2]),
            context=json.loads(row[3]),
            confidence=row[4],
            source=source_val,
            created_at=datetime.fromisoformat(created_at_val) if created_at_val else datetime.now(),
            updated_at=datetime.fromisoformat(updated_at_val) if updated_at_val else datetime.now(),
            access_count=row[8],
            last_accessed=datetime.fromisoformat(row[9]) if row[9] else None,
            tags=set(json.loads(row[10])),
            feedback=json.loads(row[11])
        )
    
    def _entry_to_row(self, entry: MemoryEntry):
        return (
            entry.id, entry.type, json.dumps(entry.content),
            json.dumps(entry.context), entry.confidence, entry.source,
            entry.created_at.isoformat(), entry.updated_at.isoformat(),
            entry.access_count, entry.last_accessed.isoformat() if entry.last_accessed else None,
            json.dumps(list(entry.tags)), json.dumps(entry.feedback)
        )
    
    async def store(self, entry: MemoryEntry):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._entry_to_row(entry))
    
    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM memories WHERE id=?", (entry_id,)).fetchone()
            if row:
                entry = self._row_to_entry(row)
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                await self.update(entry)
                return entry
            return None
    
    async def query(self, 
                   type_filter: Optional[str] = None,
                   tags: Optional[Set[str]] = None,
                   context_match: Optional[Dict[str, Any]] = None,
                   min_confidence: float = 0.0,
                   limit: int = 50) -> List[MemoryEntry]:
        
        query = "SELECT * FROM memories WHERE confidence >= ?"
        params = [min_confidence]
        
        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)
        
        if tags:
            tag_list = json.dumps(list(tags))
            query += " AND tags LIKE ?"
            params.append(f"%{tag_list}%")
        
        query += " ORDER BY confidence DESC, access_count DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            results = [self._row_to_entry(r) for r in rows]
            
            if context_match:
                # Filter by context similarity (simple key overlap)
                filtered = []
                for entry in results:
                    overlap = sum(1 for k, v in context_match.items() 
                                if k in entry.context and entry.context[k] == v)
                    if overlap > 0:
                        filtered.append(entry)
                return filtered
            
            return results
    
    async def update(self, entry: MemoryEntry):
        entry.updated_at = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE memories SET 
                    content=?, context=?, confidence=?, updated_at=?, 
                    access_count=?, last_accessed=?, tags=?, feedback=?
                WHERE id=?
            """, (*self._entry_to_row(entry)[2:10], entry.id))
    
    async def delete(self, entry_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memories WHERE id=?", (entry_id,))


class MemoryManager:
    """High-level memory management with learning capabilities."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
        self._learning_handlers: Dict[str, Callable] = {}
    
    async def remember(self, 
                      type: str,
                      content: Dict[str, Any],
                      context: Dict[str, Any] = None,
                      confidence: float = 0.5,
                      source: str = "system",
                      tags: Set[str] = None) -> MemoryEntry:
        """Store a new memory."""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            type=type,
            content=content,
            context=context or {},
            confidence=confidence,
            source=source,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            tags=tags or set()
        )
        await self.store.store(entry)
        return entry
    
    async def recall(self, 
                    type: str = None,
                    context: Dict[str, Any] = None,
                    tags: Set[str] = None,
                    min_confidence: float = 0.3,
                    limit: int = 20) -> List[MemoryEntry]:
        """Retrieve relevant memories."""
        return await self.store.query(
            type_filter=type,
            context_match=context,
            tags=tags,
            min_confidence=min_confidence,
            limit=limit
        )
    
    async def learn_from_feedback(self, 
                                 entry_id: str, 
                                 positive: bool, 
                                 feedback_data: Dict[str, Any] = None,
                                 weight: float = 0.1):
        """Update memory based on feedback."""
        entry = await self.store.retrieve(entry_id)
        if not entry:
            return
        
        # Record feedback
        entry.feedback.append({
            "positive": positive,
            "data": feedback_data or {},
            "timestamp": datetime.now().isoformat(),
            "weight": weight
        })
        
        # Adjust confidence based on feedback
        if positive:
            entry.confidence = min(1.0, entry.confidence + weight)
        else:
            entry.confidence = max(0.0, entry.confidence - weight)
        
        # If confidence drops too low, mark for review
        if entry.confidence < 0.2:
            entry.tags.add("needs_review")
        
        await self.store.update(entry)
        
        # Trigger learning handlers
        signal = LearningSignal(
            type="explicit_feedback",
            source="user",
            target_id=entry_id,
            data={"positive": positive, "feedback": feedback_data},
            weight=weight
        )
        await self._process_learning_signal(signal)
    
    async def learn_from_pattern(self, 
                                pattern_type: str,
                                pattern_data: Dict[str, Any],
                                context: Dict[str, Any],
                                confidence: float = 0.6):
        """Learn a new pattern from observed behavior."""
        # Check if similar pattern exists
        existing = await self.recall(
            type="pattern",
            context=context,
            tags={pattern_type},
            min_confidence=0.4
        )
        
        if existing:
            # Strengthen existing pattern
            for entry in existing:
                entry.confidence = min(1.0, entry.confidence + 0.05)
                entry.access_count += 1
                await self.store.update(entry)
        else:
            # Create new pattern memory
            await self.remember(
                type="pattern",
                content={"pattern_type": pattern_type, "data": pattern_data},
                context=context,
                confidence=confidence,
                source="inferred",
                tags={pattern_type, "auto_learned"}
            )
    
    def register_learning_handler(self, signal_type: str, handler: Callable):
        self._learning_handlers[signal_type] = handler
    
    async def _process_learning_signal(self, signal: LearningSignal):
        handler = self._learning_handlers.get(signal.type)
        if handler:
            try:
                await handler(signal)
            except Exception as e:
                logger.error(f"Learning handler error: {e}")
    
    async def get_user_preferences(self, user_id: str = "default") -> Dict[str, Any]:
        """Get learned user preferences."""
        prefs = await self.recall(
            type="preference",
            context={"user_id": user_id},
            min_confidence=0.4
        )
        return {p.content.get("key"): p.content.get("value") for p in prefs}
    
    async def set_user_preference(self, 
                                 key: str, 
                                 value: Any, 
                                 user_id: str = "default",
                                 confidence: float = 0.8):
        """Set a user preference."""
        await self.remember(
            type="preference",
            content={"key": key, "value": value, "user_id": user_id},
            context={"user_id": user_id},
            confidence=confidence,
            source="user",
            tags={"preference", user_id}
        )


class SkillMemory:
    """Memory for learned skills/capabilities."""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
    
    async def record_skill_use(self, 
                              skill_name: str,
                              parameters: Dict[str, Any],
                              result: Any,
                              success: bool,
                              context: Dict[str, Any] = None):
        """Record a skill execution for learning."""
        await self.memory.learn_from_pattern(
            pattern_type="skill_usage",
            pattern_data={
                "skill": skill_name,
                "parameters": parameters,
                "success": success,
                "result_type": type(result).__name__
            },
            context=context or {},
            confidence=0.7 if success else 0.3
        )
    
    async def get_skill_patterns(self, skill_name: str) -> List[MemoryEntry]:
        """Get learned patterns for a skill."""
        return await self.memory.recall(
            type="pattern",
            context={},
            tags={"skill_usage", skill_name},
            min_confidence=0.4
        )
    
    async def suggest_parameters(self, skill_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest parameters based on learned patterns."""
        patterns = await self.get_skill_patterns(skill_name)
        if not patterns:
            return {}
        
        # Find most successful patterns in similar contexts
        successful = [p for p in patterns if p.content.get("data", {}).get("success")]
        if not successful:
            return {}
        
        # Simple: return parameters from most confident successful pattern
        best = max(successful, key=lambda p: p.confidence)
        return best.content.get("data", {}).get("parameters", {})