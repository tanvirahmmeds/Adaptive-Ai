"""
Built-in plugins for common capabilities.
"""

import json
import subprocess
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .core import Plugin, Framework, Event
from .memory import MemoryManager, MemoryEntry


class FileOperationsPlugin(Plugin):
    """Plugin for file system operations."""
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["read_file", "write_file", "list_files", "search_files", "delete_file"]
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("file.read", self._handle_read)
        self.framework.event_bus.subscribe("file.write", self._handle_write)
        self.framework.event_bus.subscribe("file.list", self._handle_list)
        self.framework.event_bus.subscribe("file.search", self._handle_search)
        self.framework.event_bus.subscribe("file.delete", self._handle_delete)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_read(self, event: Event):
        path = Path(event.payload.get("path", ""))
        if path.exists() and path.is_file():
            content = path.read_text()
            await self.framework.event_bus.publish(Event("file.read.result", {
                "request_id": event.payload.get("request_id"),
                "path": str(path),
                "content": content
            }))
        else:
            await self.framework.event_bus.publish(Event("file.read.error", {
                "request_id": event.payload.get("request_id"),
                "path": str(path),
                "error": "File not found"
            }))
    
    async def _handle_write(self, event: Event):
        path = Path(event.payload.get("path", ""))
        content = event.payload.get("content", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        await self.framework.event_bus.publish(Event("file.write.result", {
            "request_id": event.payload.get("request_id"),
            "path": str(path),
            "success": True
        }))
    
    async def _handle_list(self, event: Event):
        path = Path(event.payload.get("path", "."))
        pattern = event.payload.get("pattern", "*")
        files = list(path.glob(pattern))
        await self.framework.event_bus.publish(Event("file.list.result", {
            "request_id": event.payload.get("request_id"),
            "files": [{"name": f.name, "path": str(f), "is_dir": f.is_dir()} for f in files]
        }))
    
    async def _handle_search(self, event: Event):
        path = Path(event.payload.get("path", "."))
        query = event.payload.get("query", "")
        results = []
        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix in ['.py', '.txt', '.md', '.json', '.js', '.ts']:
                try:
                    content = file_path.read_text()
                    if query.lower() in content.lower():
                        results.append({"path": str(file_path), "matches": content.count(query)})
                except:
                    pass
        await self.framework.event_bus.publish(Event("file.search.result", {
            "request_id": event.payload.get("request_id"),
            "results": results
        }))
    
    async def _handle_delete(self, event: Event):
        path = Path(event.payload.get("path", ""))
        if path.exists():
            if path.is_file():
                path.unlink()
            else:
                import shutil
                shutil.rmtree(path)
            await self.framework.event_bus.publish(Event("file.delete.result", {
                "request_id": event.payload.get("request_id"),
                "success": True
            }))


class ShellPlugin(Plugin):
    """Plugin for executing shell commands."""
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["execute", "execute_background", "get_output"]
    
    def __init__(self, name: str, framework: Framework):
        super().__init__(name, framework)
        self.background_processes: Dict[str, subprocess.Popen] = {}
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("shell.execute", self._handle_execute)
        self.framework.event_bus.subscribe("shell.background", self._handle_background)
        self.framework.event_bus.subscribe("shell.status", self._handle_status)
        return True
    
    async def shutdown(self):
        for proc in self.background_processes.values():
            proc.terminate()
    
    async def _handle_execute(self, event: Event):
        cmd = event.payload.get("command", "")
        cwd = event.payload.get("cwd", ".")
        timeout = event.payload.get("timeout", 60)
        
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            await self.framework.event_bus.publish(Event("shell.execute.result", {
                "request_id": event.payload.get("request_id"),
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": proc.returncode
            }))
        except asyncio.TimeoutError:
            await self.framework.event_bus.publish(Event("shell.execute.error", {
                "request_id": event.payload.get("request_id"),
                "error": f"Command timed out after {timeout}s"
            }))
        except Exception as e:
            await self.framework.event_bus.publish(Event("shell.execute.error", {
                "request_id": event.payload.get("request_id"),
                "error": str(e)
            }))
    
    async def _handle_background(self, event: Event):
        cmd = event.payload.get("command", "")
        cwd = event.payload.get("cwd", ".")
        proc_id = str(__import__('uuid').uuid4())
        
        proc = subprocess.Popen(
            cmd, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.background_processes[proc_id] = proc
        
        await self.framework.event_bus.publish(Event("shell.background.result", {
            "request_id": event.payload.get("request_id"),
            "process_id": proc_id
        }))
    
    async def _handle_status(self, event: Event):
        proc_id = event.payload.get("process_id")
        proc = self.background_processes.get(proc_id)
        
        if proc:
            returncode = proc.poll()
            if returncode is not None:
                stdout, stderr = proc.communicate()
                await self.framework.event_bus.publish(Event("shell.status.result", {
                    "request_id": event.payload.get("request_id"),
                    "process_id": proc_id,
                    "status": "completed",
                    "returncode": returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else ""
                }))
                del self.background_processes[proc_id]
            else:
                await self.framework.event_bus.publish(Event("shell.status.result", {
                    "request_id": event.payload.get("request_id"),
                    "process_id": proc_id,
                    "status": "running"
                }))


class MemoryPlugin(Plugin):
    """Plugin exposing memory operations."""
    
    def __init__(self, name: str, framework: Framework, memory_manager: MemoryManager):
        super().__init__(name, framework)
        self.memory = memory_manager
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["remember", "recall", "feedback", "preferences"]
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("memory.remember", self._handle_remember)
        self.framework.event_bus.subscribe("memory.recall", self._handle_recall)
        self.framework.event_bus.subscribe("memory.feedback", self._handle_feedback)
        self.framework.event_bus.subscribe("memory.preferences.get", self._handle_get_prefs)
        self.framework.event_bus.subscribe("memory.preferences.set", self._handle_set_prefs)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_remember(self, event: Event):
        entry = await self.memory.remember(
            type=event.payload.get("type", "fact"),
            content=event.payload.get("content", {}),
            context=event.payload.get("context", {}),
            confidence=event.payload.get("confidence", 0.5),
            source=event.payload.get("source", "plugin"),
            tags=set(event.payload.get("tags", []))
        )
        await self.framework.event_bus.publish(Event("memory.remember.result", {
            "request_id": event.payload.get("request_id"),
            "entry_id": entry.id
        }))
    
    async def _handle_recall(self, event: Event):
        entries = await self.memory.recall(
            type=event.payload.get("type"),
            context=event.payload.get("context"),
            tags=set(event.payload.get("tags", [])),
            min_confidence=event.payload.get("min_confidence", 0.3),
            limit=event.payload.get("limit", 20)
        )
        await self.framework.event_bus.publish(Event("memory.recall.result", {
            "request_id": event.payload.get("request_id"),
            "entries": [
                {
                    "id": e.id,
                    "type": e.type,
                    "content": e.content,
                    "context": e.context,
                    "confidence": e.confidence,
                    "tags": list(e.tags)
                }
                for e in entries
            ]
        }))
    
    async def _handle_feedback(self, event: Event):
        await self.memory.learn_from_feedback(
            entry_id=event.payload.get("entry_id"),
            positive=event.payload.get("positive", True),
            feedback_data=event.payload.get("data"),
            weight=event.payload.get("weight", 0.1)
        )
        await self.framework.event_bus.publish(Event("memory.feedback.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))
    
    async def _handle_get_prefs(self, event: Event):
        prefs = await self.memory.get_user_preferences(
            event.payload.get("user_id", "default")
        )
        await self.framework.event_bus.publish(Event("memory.preferences.get.result", {
            "request_id": event.payload.get("request_id"),
            "preferences": prefs
        }))
    
    async def _handle_set_prefs(self, event: Event):
        await self.memory.set_user_preference(
            key=event.payload.get("key"),
            value=event.payload.get("value"),
            user_id=event.payload.get("user_id", "default"),
            confidence=event.payload.get("confidence", 0.8)
        )
        await self.framework.event_bus.publish(Event("memory.preferences.set.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))


class LearningPlugin(Plugin):
    """Plugin for automatic learning from interactions."""
    
    def __init__(self, name: str, framework: Framework, memory_manager: MemoryManager):
        super().__init__(name, framework)
        self.memory = memory_manager
        self.interaction_history: List[Dict] = []
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["track_interaction", "analyze_patterns", "suggest_improvements"]
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("learning.track", self._handle_track)
        self.framework.event_bus.subscribe("learning.analyze", self._handle_analyze)
        self.framework.event_bus.subscribe("learning.suggest", self._handle_suggest)
        
        # Subscribe to all events to track patterns
        self.framework.event_bus.subscribe("", self._track_all_events)
        return True
    
    async def shutdown(self):
        pass
    
    async def _track_all_events(self, event: Event):
        """Track all events for pattern analysis."""
        self.interaction_history.append({
            "event_type": event.type,
            "timestamp": event.timestamp.isoformat(),
            "payload_keys": list(event.payload.keys())
        })
        # Keep last 1000 interactions
        if len(self.interaction_history) > 1000:
            self.interaction_history = self.interaction_history[-1000:]
    
    async def _handle_track(self, event: Event):
        """Explicitly track an interaction."""
        await self.memory.learn_from_pattern(
            pattern_type="interaction",
            pattern_data=event.payload.get("data", {}),
            context={"event_type": event.payload.get("event_type", "unknown")},
            confidence=0.6
        )
    
    async def _handle_analyze(self, event: Event):
        """Analyze patterns in interaction history."""
        # Simple frequency analysis
        event_counts = {}
        for interaction in self.interaction_history:
            et = interaction["event_type"]
            event_counts[et] = event_counts.get(et, 0) + 1
        
        # Find common sequences
        sequences = {}
        for i in range(len(self.interaction_history) - 1):
            seq = (self.interaction_history[i]["event_type"], 
                   self.interaction_history[i+1]["event_type"])
            sequences[seq] = sequences.get(seq, 0) + 1
        
        top_sequences = sorted(sequences.items(), key=lambda x: x[1], reverse=True)[:10]
        
        await self.framework.event_bus.publish(Event("learning.analyze.result", {
            "request_id": event.payload.get("request_id"),
            "event_frequencies": event_counts,
            "common_sequences": [{"sequence": list(k), "count": v} for k, v in top_sequences],
            "total_interactions": len(self.interaction_history)
        }))
    
    async def _handle_suggest(self, event: Event):
        """Suggest improvements based on patterns."""
        suggestions = []
        
        # Suggest enabling plugins for frequent event types
        event_counts = {}
        for interaction in self.interaction_history:
            et = interaction["event_type"]
            event_counts[et] = event_counts.get(et, 0) + 1
        
        for event_type, count in event_counts.items():
            if count > 10 and event_type.startswith("plugin."):
                plugin_name = event_type.split(".")[1]
                if plugin_name in self.framework.plugins and not self.framework.plugins[plugin_name].enabled:
                    suggestions.append({
                        "type": "enable_plugin",
                        "plugin": plugin_name,
                        "reason": f"Frequent {event_type} events ({count} times)"
                    })
        
        await self.framework.event_bus.publish(Event("learning.suggest.result", {
            "request_id": event.payload.get("request_id"),
            "suggestions": suggestions
        }))


class UserFeedbackPlugin(Plugin):
    """Plugin for collecting and processing user feedback."""
    
    def __init__(self, name: str, framework: Framework, memory_manager: MemoryManager):
        super().__init__(name, framework)
        self.memory = memory_manager
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["collect_feedback", "process_correction", "get_feedback_stats"]
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("feedback.submit", self._handle_feedback)
        self.framework.event_bus.subscribe("feedback.correction", self._handle_correction)
        self.framework.event_bus.subscribe("feedback.stats", self._handle_stats)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_feedback(self, event: Event):
        """Process user feedback on a response/action."""
        target_id = event.payload.get("target_id")
        positive = event.payload.get("positive", True)
        comment = event.payload.get("comment", "")
        
        await self.memory.learn_from_feedback(
            entry_id=target_id,
            positive=positive,
            feedback_data={"comment": comment, "source": "explicit"},
            weight=0.15
        )
        
        await self.framework.event_bus.publish(Event("feedback.submit.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))
    
    async def _handle_correction(self, event: Event):
        """Process a correction from the user."""
        correction = event.payload.get("correction", {})
        context = event.payload.get("context", {})
        
        # Store correction as high-confidence memory
        await self.memory.remember(
            type="correction",
            content=correction,
            context=context,
            confidence=0.9,
            source="user",
            tags={"correction", "user_provided"}
        )
        
        await self.framework.event_bus.publish(Event("feedback.correction.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))
    
    async def _handle_stats(self, event: Event):
            """Get feedback statistics."""
            # Query corrections and feedback
            corrections = await self.memory.recall(type="correction", min_confidence=0.5)
        
            recent_count = len([c for c in corrections 
                               if (datetime.now() - c.created_at).days < 7])
        
            await self.framework.event_bus.publish(Event("feedback.stats.result", {
                "request_id": event.payload.get("request_id"),
                "total_corrections": len(corrections),
                "recent_corrections": recent_count
            }))


# Import datetime for the feedback plugin
from datetime import datetime