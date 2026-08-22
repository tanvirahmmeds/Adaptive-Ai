"""
Autonomous AI Agent - A self-directed agent built on the Adaptive Framework.

Capabilities:
- Goal setting and task decomposition
- Autonomous planning and execution
- Error handling and retry with adaptation
- Self-reflection and learning
- Dynamic capability creation
- Memory-augmented decision making
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from adaptive_framework import AdaptiveFramework
from adaptive_framework.core import Plugin, Framework, Event
from adaptive_framework.memory import MemoryManager, MemoryEntry
from adaptive_framework.extensions import CapabilityBuilder, GrowthManager

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """A task in the agent's plan."""
    id: str
    goal: str
    description: str
    action: str
    parameters: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: Set[str] = field(default_factory=set)


@dataclass
class Goal:
    """A high-level goal for the agent."""
    id: str
    description: str
    success_criteria: List[str]
    tasks: List[Task] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlanningEngine:
    """Decomposes goals into executable tasks."""
    
    def __init__(self, framework: Framework, memory: MemoryManager):
        self.framework = framework
        self.memory = memory
    
    async def decompose_goal(self, goal: Goal) -> List[Task]:
        """Break down a goal into tasks."""
        # Check memory for similar goals
        similar = await self.memory.recall(
            type="goal_plan",
            context={"goal_type": self._classify_goal(goal.description)},
            min_confidence=0.4,
            limit=3
        )
        
        if similar:
            # Reuse learned plan
            return await self._adapt_plan(goal, similar[0])
        
        # Generate new plan using available capabilities
        return await self._generate_plan(goal)
    
    def _classify_goal(self, description: str) -> str:
        """Classify goal type for plan reuse."""
        desc = description.lower()
        if any(w in desc for w in ["file", "read", "write", "list", "search"]):
            return "file_operations"
        elif any(w in desc for w in ["run", "execute", "command", "script", "shell"]):
            return "shell_operations"
        elif any(w in desc for w in ["analyze", "process", "transform", "convert"]):
            return "data_processing"
        elif any(w in desc for w in ["create", "build", "generate", "make"]):
            return "creation"
        elif any(w in desc for w in ["learn", "research", "find", "discover"]):
            return "research"
        return "general"
    
    async def _adapt_plan(self, goal: Goal, memory_entry: MemoryEntry) -> List[Task]:
        """Adapt a learned plan to the current goal."""
        plan_data = memory_entry.content.get("plan", [])
        tasks = []
        
        for i, step in enumerate(plan_data):
            task = Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description=step.get("description", f"Step {i+1}"),
                action=step.get("action", ""),
                parameters=step.get("parameters", {}),
                context=step.get("context", {}),
                priority=TaskPriority(step.get("priority", 2)),
                dependencies=step.get("dependencies", []),
                tags={"adapted", goal.id}
            )
            tasks.append(task)
        
        return tasks
    
    async def _generate_plan(self, goal: Goal) -> List[Task]:
        """Generate a new plan from available capabilities."""
        # Get available capabilities
        plugins = self.framework.list_plugins()
        capabilities = []
        for name, info in plugins.items():
            if info["enabled"]:
                for cap in info["capabilities"]:
                    capabilities.append(f"{name}.{cap}")
        
        # Simple heuristic planning based on goal keywords
        tasks = []
        desc = goal.description.lower()
        
        if "file" in desc and ("read" in desc or "write" in desc or "list" in desc):
            tasks.extend(self._plan_file_ops(goal, desc))
        
        if "shell" in desc or "command" in desc or "run" in desc:
            tasks.extend(self._plan_shell_ops(goal, desc))
        
        if "analyze" in desc or "process" in desc:
            tasks.extend(self._plan_analysis(goal, desc))
        
        if "create" in desc or "build" in desc or "generate" in desc:
            tasks.extend(self._plan_creation(goal, desc))
        
        if "learn" in desc or "research" in desc:
            tasks.extend(self._plan_research(goal, desc))
        
        # If no specific plan, create a generic exploration task
        if not tasks:
            tasks.append(Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description=f"Explore approach for: {goal.description}",
                action="learning.track",
                parameters={"data": {"goal": goal.description, "phase": "exploration"}},
                priority=TaskPriority.NORMAL,
                tags={"exploration", goal.id}
            ))
        
        return tasks
    
    def _plan_file_ops(self, goal: Goal, desc: str) -> List[Task]:
        tasks = []
        
        # If both "read" and "list" or "all" in description, create a list-then-read sequence
        if ("read" in desc and ("list" in desc or "all" in desc or "each" in desc)) or \
           ("list" in desc and "read" in desc):
            # First list files
            list_task = Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description="List target files",
                action="file.list",
                parameters={"path": self._extract_path(desc) or "/data/data/com.termux/files/home/workspace", "pattern": "*.py"},
                priority=TaskPriority.HIGH,
                tags={"file_ops", goal.id}
            )
            # Then read each file (this will be expanded by the executor)
            read_task = Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description="Read each listed file",
                action="file.read",
                parameters={"path": "{{results.step_0.files[0].path}}"},  # Template for first file
                priority=TaskPriority.HIGH,
                dependencies=[list_task.id],
                tags={"file_ops", goal.id}
            )
            tasks.extend([list_task, read_task])
            return tasks
        
        if "read" in desc:
            tasks.append(Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description="Read target file(s)",
                action="file.read",
                parameters={"path": self._extract_path(desc) or "/data/data/com.termux/files/home/workspace"},
                priority=TaskPriority.HIGH,
                tags={"file_ops", goal.id}
            ))
        if "write" in desc or "create" in desc:
            tasks.append(Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description="Write output file",
                action="file.write",
                parameters={"path": self._extract_output_path(desc) or "output.txt", "content": ""},
                priority=TaskPriority.HIGH,
                tags={"file_ops", goal.id}
            ))
        if "list" in desc or "find" in desc:
            tasks.append(Task(
                id=str(uuid.uuid4())[:8],
                goal=goal.id,
                description="List files in directory",
                action="file.list",
                parameters={"path": self._extract_path(desc) or "/data/data/com.termux/files/home/workspace", "pattern": "*"},
                priority=TaskPriority.NORMAL,
                tags={"file_ops", goal.id}
            ))
        return tasks
    
    def _plan_shell_ops(self, goal: Goal, desc: str) -> List[Task]:
        return [Task(
            id=str(uuid.uuid4())[:8],
            goal=goal.id,
            description="Execute shell command",
            action="shell.execute",
            parameters={"command": self._extract_command(desc) or "pwd && date"},
            priority=TaskPriority.HIGH,
            tags={"shell_ops", goal.id}
        )]
    
    def _plan_analysis(self, goal: Goal, desc: str) -> List[Task]:
        return [Task(
            id=str(uuid.uuid4())[:8],
            goal=goal.id,
            description="Track analysis task for learning",
            action="learning.track",
            parameters={"data": {"goal": goal.description, "phase": "analysis"}},
            priority=TaskPriority.NORMAL,
            tags={"analysis", goal.id}
        )]
    
    def _plan_creation(self, goal: Goal, desc: str) -> List[Task]:
        return [Task(
            id=str(uuid.uuid4())[:8],
            goal=goal.id,
            description="Create new capability if needed",
            action="memory.remember",
            parameters={
                "type": "skill",
                "content": {"name": "auto_generated", "description": goal.description},
                "context": {"goal_id": goal.id},
                "tags": ["capability", "auto_generated"]
            },
            priority=TaskPriority.NORMAL,
            tags={"creation", goal.id}
        )]
    
    def _plan_research(self, goal: Goal, desc: str) -> List[Task]:
        return [Task(
            id=str(uuid.uuid4())[:8],
            goal=goal.id,
            description="Research and gather information",
            action="memory.recall",
            parameters={"type": "fact", "limit": 10},
            priority=TaskPriority.NORMAL,
            tags={"research", goal.id}
        )]
    
    def _extract_path(self, desc: str) -> Optional[str]:
        import re
        # Try quoted paths first
        match = re.search(r'["\']([^"\']+\.(?:txt|py|md|json|csv))["\']', desc)
        if match:
            return match.group(1)
        # Try to find directory names after "in", "from", "at"
        match = re.search(r'(?:in|from|at)\s+(?:the\s+)?(\S+(?:/\S+)*\s*)', desc)
        if match:
            path = match.group(1).strip()
            # Filter out common stop words
            if path.lower() not in ["the", "a", "an", "this", "that", "workspace", "directory", "folder"]:
                return path
        # Default to workspace
        return "/data/data/com.termux/files/home/workspace"
    
    def _extract_output_path(self, desc: str) -> Optional[str]:
        import re
        match = re.search(r'(?:to|into|as)\s+["\']?([^"\']+\.(?:txt|py|md|json|csv))["\']?', desc)
        if match:
            return match.group(1)
        return None
    
    def _extract_command(self, desc: str) -> Optional[str]:
        import re
        match = re.search(r'["\']([^"\']+)["\']', desc)
        if match:
            return match.group(1)
        return None


class ExecutionEngine:
    """Executes tasks and handles errors/adaptation."""
    
    def __init__(self, adaptive_framework: AdaptiveFramework, memory: MemoryManager, growth: GrowthManager):
        self.framework = adaptive_framework
        self.memory = memory
        self.growth = growth
        self.running_tasks: Dict[str, Task] = {}
    
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a single task with retry logic."""
        import logging
        logger = logging.getLogger(__name__)
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks[task.id] = task
        
        logger.info(f"Starting task {task.id}: {task.action} with params {task.parameters}")
        
        try:
            # Execute the action using AdaptiveFramework's execute method
            logger.info(f"Calling framework.execute for task {task.id}")
            result = await self.framework.execute(task.action, task.parameters, task.context)
            logger.info(f"Task {task.id} got result: {result}")
            
            # Check for errors
            if result.get("error"):
                raise Exception(result["error"])
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Learn from success
            await self._learn_from_execution(task, success=True)
            
            logger.info(f"Task {task.id} completed successfully")
            return result
            
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                # Adapt parameters for retry
                await self._adapt_for_retry(task, e)
                logger.info(f"Retrying task {task.id} (attempt {task.retry_count + 1})")
                return await self.execute_task(task)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                await self._learn_from_execution(task, success=False)
                logger.error(f"Task {task.id} failed after {task.max_retries} retries: {e}")
                return {"error": str(e), "task_id": task.id}
        finally:
            self.running_tasks.pop(task.id, None)
    
    async def _adapt_for_retry(self, task: Task, error: Exception):
        """Adapt task parameters based on error."""
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(error).lower()
        
        if "not found" in error_str or "no such file" in error_str:
            # Try alternative paths
            if "path" in task.parameters:
                original = task.parameters["path"]
                alternatives = [
                    original.replace("/tmp", "/data/data/com.termux/files/home/workspace"),
                    original.replace(".", "/data/data/com.termux/files/home/workspace"),
                    f"/data/data/com.termux/files/home/workspace/{original}"
                ]
                for alt in alternatives:
                    if alt != original:
                        task.parameters["path"] = alt
                        break
        
        elif "timeout" in error_str:
            # Increase timeout if applicable
            if "timeout" in task.parameters:
                task.parameters["timeout"] = task.parameters["timeout"] * 2
        
        elif "permission" in error_str:
            # Try different approach
            task.parameters["use_sudo"] = True
    
    async def _learn_from_execution(self, task: Task, success: bool):
        """Record execution outcome for learning."""
        import logging
        logger = logging.getLogger(__name__)
        await self.memory.learn_from_pattern(
            pattern_type="task_execution",
            pattern_data={
                "action": task.action,
                "parameters": task.parameters,
                "success": success,
                "error": task.error,
                "retry_count": task.retry_count,
                "goal": task.goal
            },
            context={"task_id": task.id, "goal_id": task.goal},
            confidence=0.7 if success else 0.3
        )
        
        # Store successful patterns as reusable plans
        if success and task.retry_count == 0:
            await self._store_successful_pattern(task)
    
    async def _store_successful_pattern(self, task: Task):
        """Store successful execution as a reusable pattern."""
        import logging
        logger = logging.getLogger(__name__)
        # Check if we already have this pattern
        existing = await self.memory.recall(
            type="pattern",
            tags={"task_pattern", task.action},
            context={"action": task.action},
            min_confidence=0.5
        )
        
        if not existing:
            await self.memory.remember(
                type="pattern",
                content={
                    "pattern_type": "task_pattern",
                    "data": {
                        "action": task.action,
                        "parameters_template": task.parameters,
                        "context_template": task.context,
                        "success_rate": 1.0
                    }
                },
                context={"action": task.action},
                confidence=0.8,
                source="inferred",
                tags={"task_pattern", task.action, "auto_learned"}
            )


class ReflectionEngine:
    """Self-reflection and improvement."""
    
    def __init__(self, framework: Framework, memory: MemoryManager, growth: GrowthManager):
        import logging
        self.logger = logging.getLogger(__name__)
        self.framework = framework
        self.memory = memory
        self.growth = growth
    
    async def reflect_on_goal(self, goal: Goal) -> Dict[str, Any]:
        """Analyze goal execution and derive insights."""
        completed_tasks = [t for t in goal.tasks if t.status == TaskStatus.COMPLETED]
        failed_tasks = [t for t in goal.tasks if t.status == TaskStatus.FAILED]
        
        reflection = {
            "goal_id": goal.id,
            "total_tasks": len(goal.tasks),
            "completed": len(completed_tasks),
            "failed": len(failed_tasks),
            "success_rate": len(completed_tasks) / len(goal.tasks) if goal.tasks else 0,
            "insights": [],
            "improvements": []
        }
        
        # Analyze failures
        for task in failed_tasks:
            reflection["insights"].append({
                "type": "failure",
                "action": task.action,
                "error": task.error,
                "retry_count": task.retry_count
            })
            
            # Suggest capability creation for repeated failures
            similar_failures = await self.memory.recall(
                type="pattern",
                tags={"task_pattern", task.action},
                min_confidence=0.0
            )
            failed_count = sum(1 for p in similar_failures 
                             if not p.content.get("data", {}).get("success", True))
            if failed_count >= 2:
                reflection["improvements"].append({
                    "type": "create_capability",
                    "action": task.action,
                    "reason": f"Repeated failures ({failed_count}) in {task.action}"
                })
        
        # Analyze successes for patterns
        if completed_tasks:
            actions_used = {}
            for task in completed_tasks:
                actions_used[task.action] = actions_used.get(task.action, 0) + 1
            
            for action, count in actions_used.items():
                if count >= 3:
                    reflection["insights"].append({
                        "type": "frequent_action",
                        "action": action,
                        "count": count,
                        "suggestion": f"Consider creating workflow for {action}"
                    })
        
        # Store reflection
        await self.memory.remember(
            type="reflection",
            content=reflection,
            context={"goal_id": goal.id},
            confidence=0.8,
            source="self_reflection",
            tags={"reflection", goal.id}
        )
        
        self.logger.info(f"Reflection on goal {goal.id}: {reflection['success_rate']:.1%} success rate")
        return reflection
    
    async def propose_improvements(self) -> List[Dict[str, Any]]:
        """Propose system improvements based on accumulated experience."""
        import logging
        logger = logging.getLogger(__name__)
        # Get all reflections
        reflections = await self.memory.recall(type="reflection", min_confidence=0.5)
        
        improvements = []
        
        # Aggregate failure patterns
        failure_actions = {}
        for r in reflections:
            for insight in r.content.get("insights", []):
                if insight.get("type") == "failure":
                    action = insight.get("action", "unknown")
                    failure_actions[action] = failure_actions.get(action, 0) + 1
        
        for action, count in failure_actions.items():
            if count >= 3:
                improvements.append({
                    "type": "capability_gap",
                    "action": action,
                    "frequency": count,
                    "suggestion": f"Create robust capability for {action}"
                })
        
        # Check for unused capabilities
        plugins = self.framework.list_plugins()
        for name, info in plugins.items():
            if info["enabled"]:
                usage = await self.memory.recall(
                    type="pattern",
                    tags={"task_pattern", name},
                    min_confidence=0.0
                )
                if not usage:
                    improvements.append({
                        "type": "unused_capability",
                        "plugin": name,
                        "suggestion": f"Consider disabling unused plugin: {name}"
                    })
        
        logger.info(f"Proposed {len(improvements)} improvements")
        return improvements


class AutonomousAgent(Plugin):
    """Main autonomous agent plugin."""
    
    def __init__(self, name: str, framework: Framework, adaptive_framework: AdaptiveFramework = None):
        super().__init__(name, framework)
        self.adaptive_framework = adaptive_framework
        self.memory: Optional[MemoryManager] = None
        self.growth: Optional[GrowthManager] = None
        self.planner: Optional[PlanningEngine] = None
        self.executor: Optional[ExecutionEngine] = None
        self.reflector: Optional[ReflectionEngine] = None
        
        self.active_goals: Dict[str, Goal] = {}
        self.task_queue: List[Task] = []
        self.running = False
        self._main_loop_task: Optional[asyncio.Task] = None
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "set_goal",
            "get_goal_status",
            "list_goals",
            "pause_goal",
            "resume_goal",
            "cancel_goal",
            "get_agent_status",
            "trigger_reflection",
            "get_improvements"
        ]
    
    async def initialize(self) -> bool:
        # Get dependencies
        import logging
        logger = logging.getLogger(__name__)
        memory_plugin = self.framework.get_plugin("memory")
        if memory_plugin and hasattr(memory_plugin, 'memory'):
            self.memory = memory_plugin.memory
        else:
            logger.error("Memory plugin not available")
            return False
        
        # Get growth manager from framework (need to access it)
        # We'll create our own reference
        from adaptive_framework.extensions import GrowthManager, ExtensionRegistry
        from adaptive_framework.memory import SQLiteMemoryStore
        
        data_dir = self.framework.data_dir
        memory_store = SQLiteMemoryStore(data_dir / "memory.db")
        self.memory = MemoryManager(memory_store)
        
        registry = ExtensionRegistry(self.framework, data_dir / "extensions")
        self.growth = GrowthManager(self.framework, self.memory, registry)
        
        self.planner = PlanningEngine(self.framework, self.memory)
        self.executor = ExecutionEngine(self.adaptive_framework, self.memory, self.growth)
        self.reflector = ReflectionEngine(self.framework, self.memory, self.growth)
        
        # Subscribe to events
        self.framework.event_bus.subscribe("agent.set_goal", self._handle_set_goal)
        self.framework.event_bus.subscribe("agent.get_goal_status", self._handle_get_goal_status)
        self.framework.event_bus.subscribe("agent.list_goals", self._handle_list_goals)
        self.framework.event_bus.subscribe("agent.pause_goal", self._handle_pause_goal)
        self.framework.event_bus.subscribe("agent.resume_goal", self._handle_resume_goal)
        self.framework.event_bus.subscribe("agent.cancel_goal", self._handle_cancel_goal)
        self.framework.event_bus.subscribe("agent.get_status", self._handle_get_status)
        self.framework.event_bus.subscribe("agent.reflect", self._handle_reflect)
        self.framework.event_bus.subscribe("agent.get_improvements", self._handle_get_improvements)
        
        return True
    
    async def shutdown(self):
        self.running = False
        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
    
    async def start_agent_loop(self):
        """Start the main autonomous loop."""
        self.running = True
        self._main_loop_task = asyncio.create_task(self._main_loop())
    
    async def stop_agent_loop(self):
        """Stop the main autonomous loop."""
        self.running = False
        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
    
    async def _main_loop(self):
        """Main autonomous execution loop."""
        while self.running:
            try:
                # Process active goals
                for goal_id, goal in list(self.active_goals.items()):
                    if goal.status != "active":
                        continue
                    
                    # Find next executable task
                    task = self._get_next_task(goal)
                    if task:
                        # Execute task
                        await self.executor.execute_task(task)
                        
                        # Check if goal is complete
                        if self._is_goal_complete(goal):
                            goal.status = "completed"
                            goal.completed_at = datetime.now()
                            
                            # Reflect on completion
                            await self.reflector.reflect_on_goal(goal)
                            
                            await self.framework.event_bus.publish(Event("agent.goal_completed", {
                                "goal_id": goal_id,
                                "goal": goal.description
                            }))
                
                # Periodic reflection
                if len(self.active_goals) == 0:
                    # No active goals, do maintenance
                    await self._maintenance_cycle()
                
                await asyncio.sleep(1)  # Tick rate
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Agent loop error: {e}")
                await asyncio.sleep(5)
    
    def _get_next_task(self, goal: Goal) -> Optional[Task]:
        """Get the next executable task for a goal."""
        # Find pending tasks whose dependencies are met
        for task in goal.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check dependencies
            deps_met = True
            for dep_id in task.dependencies:
                dep_task = next((t for t in goal.tasks if t.id == dep_id), None)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    deps_met = False
                    break
            
            if deps_met:
                return task
        
        return None
    
    def _is_goal_complete(self, goal: Goal) -> bool:
        """Check if all tasks in a goal are complete."""
        if not goal.tasks:
            return False
        return all(t.status == TaskStatus.COMPLETED for t in goal.tasks)
    
    async def _maintenance_cycle(self):
        """Periodic maintenance when idle."""
        # Propose improvements
        improvements = await self.reflector.propose_improvements()
        for imp in improvements:
            await self.framework.event_bus.publish(Event("agent.improvement_proposed", imp))
        
        # Clean up old completed goals
        cutoff = datetime.now().timestamp() - 86400  # 24 hours
        to_remove = []
        for goal_id, goal in self.active_goals.items():
            if goal.status == "completed" and goal.completed_at:
                if goal.completed_at.timestamp() < cutoff:
                    to_remove.append(goal_id)
        
        for goal_id in to_remove:
            del self.active_goals[goal_id]
    
    # Event handlers
    
    async def _handle_set_goal(self, event: Event):
        """Handle new goal request."""
        description = event.payload.get("description", "")
        success_criteria = event.payload.get("success_criteria", [])
        metadata = event.payload.get("metadata", {})
        
        goal = Goal(
            id=str(uuid.uuid4())[:8],
            description=description,
            success_criteria=success_criteria,
            metadata=metadata
        )
        
        # Decompose into tasks
        goal.tasks = await self.planner.decompose_goal(goal)
        
        self.active_goals[goal.id] = goal
        
        # Store goal in memory
        await self.memory.remember(
            type="goal",
            content={
                "id": goal.id,
                "description": goal.description,
                "success_criteria": goal.success_criteria,
                "task_count": len(goal.tasks)
            },
            context={"goal_id": goal.id},
            confidence=0.9,
            source="user",
            tags={"goal", "active"}
        )
        
        await self.framework.event_bus.publish(Event("agent.goal_created", {
            "request_id": event.payload.get("request_id"),
            "goal_id": goal.id,
            "tasks": len(goal.tasks)
        }))
    
    async def _handle_get_goal_status(self, event: Event):
        goal_id = event.payload.get("goal_id")
        goal = self.active_goals.get(goal_id)
        
        if goal:
            result = {
                "goal_id": goal.id,
                "description": goal.description,
                "status": goal.status,
                "tasks": [
                    {
                        "id": t.id,
                        "description": t.description,
                        "action": t.action,
                        "status": t.status.value,
                        "error": t.error,
                        "retry_count": t.retry_count
                    }
                    for t in goal.tasks
                ],
                "progress": f"{sum(1 for t in goal.tasks if t.status == TaskStatus.COMPLETED)}/{len(goal.tasks)}"
            }
        else:
            result = {"error": "Goal not found"}
        
        await self.framework.event_bus.publish(Event("agent.get_goal_status.result", {
            "request_id": event.payload.get("request_id"),
            "result": result
        }))
    
    async def _handle_list_goals(self, event: Event):
        goals = [
            {
                "id": g.id,
                "description": g.description,
                "status": g.status,
                "task_count": len(g.tasks),
                "completed_tasks": sum(1 for t in g.tasks if t.status == TaskStatus.COMPLETED)
            }
            for g in self.active_goals.values()
        ]
        
        await self.framework.event_bus.publish(Event("agent.list_goals.result", {
            "request_id": event.payload.get("request_id"),
            "goals": goals
        }))
    
    async def _handle_pause_goal(self, event: Event):
        goal_id = event.payload.get("goal_id")
        goal = self.active_goals.get(goal_id)
        
        if goal:
            goal.status = "paused"
            await self.framework.event_bus.publish(Event("agent.pause_goal.result", {
                "request_id": event.payload.get("request_id"),
                "success": True
            }))
        else:
            await self.framework.event_bus.publish(Event("agent.pause_goal.result", {
                "request_id": event.payload.get("request_id"),
                "error": "Goal not found"
            }))
    
    async def _handle_resume_goal(self, event: Event):
        goal_id = event.payload.get("goal_id")
        goal = self.active_goals.get(goal_id)
        
        if goal:
            goal.status = "active"
            await self.framework.event_bus.publish(Event("agent.resume_goal.result", {
                "request_id": event.payload.get("request_id"),
                "success": True
            }))
        else:
            await self.framework.event_bus.publish(Event("agent.resume_goal.result", {
                "request_id": event.payload.get("request_id"),
                "error": "Goal not found"
            }))
    
    async def _handle_cancel_goal(self, event: Event):
        goal_id = event.payload.get("goal_id")
        goal = self.active_goals.get(goal_id)
        
        if goal:
            goal.status = "cancelled"
            # Cancel pending tasks
            for task in goal.tasks:
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.FAILED
                    task.error = "Goal cancelled"
            await self.framework.event_bus.publish(Event("agent.cancel_goal.result", {
                "request_id": event.payload.get("request_id"),
                "success": True
            }))
        else:
            await self.framework.event_bus.publish(Event("agent.cancel_goal.result", {
                "request_id": event.payload.get("request_id"),
                "error": "Goal not found"
            }))
    
    async def _handle_get_status(self, event: Event):
        status = {
            "running": self.running,
            "active_goals": len([g for g in self.active_goals.values() if g.status == "active"]),
            "paused_goals": len([g for g in self.active_goals.values() if g.status == "paused"]),
            "total_tasks_pending": sum(
                1 for g in self.active_goals.values() 
                for t in g.tasks if t.status == TaskStatus.PENDING
            ),
            "total_tasks_running": len(self.executor.running_tasks) if self.executor else 0,
            "memory_stats": {
                "total_memories": len(await self.memory.recall(min_confidence=0.0, limit=10000))
            }
        }
        
        await self.framework.event_bus.publish(Event("agent.get_status.result", {
            "request_id": event.payload.get("request_id"),
            "status": status
        }))
    
    async def _handle_reflect(self, event: Event):
        goal_id = event.payload.get("goal_id")
        goal = self.active_goals.get(goal_id)
        
        if goal:
            reflection = await self.reflector.reflect_on_goal(goal)
            await self.framework.event_bus.publish(Event("agent.reflect.result", {
                "request_id": event.payload.get("request_id"),
                "reflection": reflection
            }))
        else:
            await self.framework.event_bus.publish(Event("agent.reflect.result", {
                "request_id": event.payload.get("request_id"),
                "error": "Goal not found"
            }))
    
    async def _handle_get_improvements(self, event: Event):
        improvements = await self.reflector.propose_improvements()
        await self.framework.event_bus.publish(Event("agent.get_improvements.result", {
            "request_id": event.payload.get("request_id"),
            "improvements": improvements
        }))
    
    # High-level API
    
    async def set_goal(self, description: str, success_criteria: List[str] = None, metadata: Dict = None) -> str:
        """Set a new goal for the agent."""
        request_id = str(uuid.uuid4())[:8]
        future = asyncio.get_event_loop().create_future()
        
        def handler(event):
            if event.payload.get("request_id") == request_id:
                future.set_result(event.payload)
        
        self.framework.event_bus.subscribe("agent.goal_created", handler)
        
        try:
            await self.framework.event_bus.publish(Event("agent.set_goal", {
                "request_id": request_id,
                "description": description,
                "success_criteria": success_criteria or [],
                "metadata": metadata or {}
            }))
            result = await asyncio.wait_for(future, timeout=10)
            return result.get("goal_id", "")
        finally:
            self.framework.event_bus.unsubscribe("agent.goal_created", handler)
    
    async def get_status(self) -> Dict[str, Any]:
        request_id = str(uuid.uuid4())[:8]
        future = asyncio.get_event_loop().create_future()
        
        def handler(event):
            if event.payload.get("request_id") == request_id:
                future.set_result(event.payload)
        
        self.framework.event_bus.subscribe("agent.get_status.result", handler)
        
        try:
            await self.framework.event_bus.publish(Event("agent.get_status", {"request_id": request_id}))
            result = await asyncio.wait_for(future, timeout=10)
            return result.get("status", {})
        finally:
            self.framework.event_bus.unsubscribe("agent.get_status.result", handler)


# Extension manifest and entry point
def create_agent_extension(framework: Framework, data_dir: Path) -> AutonomousAgent:
    """Factory function to create and configure the agent."""
    agent = AutonomousAgent("autonomous_agent", framework)
    return agent