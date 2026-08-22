"""
Agent Loop - Proper ReAct loop with state graph for the Adaptive Framework.
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypedDict, Union
import logging

from adaptive_framework.core import Plugin, Framework, Event
from adaptive_framework.memory import MemoryManager, MemoryEntry
from adaptive_framework.vector_memory import VectorMemoryManager

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Agent state for the ReAct loop."""
    messages: List[Dict[str, Any]]
    goals: List[Dict[str, Any]]
    current_goal: Optional[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    current_task: Optional[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    working_memory: Dict[str, Any]
    iteration: int
    max_iterations: int
    status: str  # running, completed, failed, paused
    error: Optional[str]


class NodeType(Enum):
    """Types of nodes in the agent graph."""
    OBSERVE = "observe"
    THINK = "think"
    ACT = "act"
    REFLECT = "reflect"
    HUMAN_INPUT = "human_input"
    CHECKPOINT = "checkpoint"


@dataclass
class GraphNode:
    """Node in the agent state graph."""
    name: str
    node_type: NodeType
    handler: Callable
    edges: List[str] = field(default_factory=list)
    condition: Optional[Callable[[AgentState], bool]] = None


class AgentGraph:
    """State graph for agent execution (LangGraph-style)."""
    
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.entry_point: Optional[str] = None
    
    def add_node(self, node: GraphNode):
        self.nodes[node.name] = node
    
    def set_entry_point(self, name: str):
        self.entry_point = name
    
    def add_edge(self, from_node: str, to_node: str):
        if from_node in self.nodes:
            self.nodes[from_node].edges.append(to_node)
    
    def add_conditional_edge(self, from_node: str, to_node: str, condition: Callable[[AgentState], bool]):
        if from_node in self.nodes:
            self.nodes[from_node].edges.append(to_node)
            self.nodes[from_node].condition = condition


class ReActAgent:
    """ReAct (Reasoning + Acting) agent with proper loop."""
    
    def __init__(self, 
                 framework: Framework,
                 memory: MemoryManager,
                 vector_memory: Optional[VectorMemoryManager] = None,
                 llm_provider = None,
                 adaptive_framework = None):
        self.framework = framework
        self.adaptive_framework = adaptive_framework
        self.memory = memory
        self.vector_memory = vector_memory
        self.llm_provider = llm_provider
        
        self.graph = AgentGraph()
        self.state: AgentState = self._initial_state()
        self.running = False
        self.checkpoints: List[AgentState] = []
        
        self._build_default_graph()
    
    def _initial_state(self) -> AgentState:
        return {
            "messages": [],
            "goals": [],
            "current_goal": None,
            "tasks": [],
            "current_task": None,
            "observations": [],
            "working_memory": {},
            "iteration": 0,
            "max_iterations": 20,
            "status": "idle",
            "error": None
        }
    
    def _build_default_graph(self):
        """Build the default ReAct graph."""
        # Observe node
        self.graph.add_node(GraphNode(
            name="observe",
            node_type=NodeType.OBSERVE,
            handler=self._observe,
            edges=["think"]
        ))
        
        # Think node
        self.graph.add_node(GraphNode(
            name="think",
            node_type=NodeType.THINK,
            handler=self._think,
            edges=["act", "reflect"]
        ))
        
        # Act node
        self.graph.add_node(GraphNode(
            name="act",
            node_type=NodeType.ACT,
            handler=self._act,
            edges=["observe"]
        ))
        
        # Reflect node
        self.graph.add_node(GraphNode(
            name="reflect",
            node_type=NodeType.REFLECT,
            handler=self._reflect,
            edges=["observe", "__end__"]
        ))
        
        self.graph.set_entry_point("observe")
    
    async def _observe(self, state: AgentState) -> AgentState:
        """Observe environment and gather context."""
        logger.info(f"[Iteration {state['iteration']}] OBSERVE")
        
        # Get current goal
        if not state["current_goal"] and state["goals"]:
            state["current_goal"] = state["goals"][0]
        
        # Get relevant memories
        if state["current_goal"]:
            goal_text = state["current_goal"].get("description", "")
            if self.vector_memory:
                context = await self.vector_memory.get_context_for_query(goal_text, max_tokens=1500)
                state["working_memory"]["relevant_context"] = context
            
            # Also get from regular memory
            memories = await self.memory.recall(
                type="fact",
                limit=10
            )
            state["working_memory"]["facts"] = [m.content for m in memories]
        
        # Get pending tasks
        if state["current_goal"]:
            goal_id = state["current_goal"].get("id")
            pending = [t for t in state["tasks"] 
                      if t.get("goal_id") == goal_id and t.get("status") == "pending"]
            if pending:
                state["current_task"] = pending[0]
        
        # Record observation
        state["observations"].append({
            "iteration": state["iteration"],
            "timestamp": datetime.now().isoformat(),
            "goal": state["current_goal"].get("description") if state["current_goal"] else None,
            "task": state["current_task"].get("description") if state["current_task"] else None,
            "context_keys": list(state["working_memory"].keys())
        })
        
        return state
    
    async def _think(self, state: AgentState) -> AgentState:
        """Reason about next action using LLM."""
        logger.info(f"[Iteration {state['iteration']}] THINK")
        
        state["iteration"] += 1
        
        if state["iteration"] > state["max_iterations"]:
            state["status"] = "failed"
            state["error"] = "Max iterations exceeded"
            return state
        
        # Check if goal is complete
        if state["current_goal"]:
            goal_tasks = [t for t in state["tasks"] if t.get("goal_id") == state["current_goal"].get("id")]
            completed = [t for t in goal_tasks if t.get("status") == "completed"]
            if len(completed) == len(goal_tasks) and len(goal_tasks) > 0:
                state["status"] = "completed"
                state["current_goal"]["status"] = "completed"
                state["current_goal"]["completed_at"] = datetime.now().isoformat()
                return state
        
        # If no current task, we need to plan or we're done
        if not state["current_task"]:
            if state["current_goal"] and state["current_goal"].get("status") == "completed":
                # Move to next goal
                state["goals"] = [g for g in state["goals"] if g.get("status") != "completed"]
                if state["goals"]:
                    state["current_goal"] = state["goals"][0]
                    # Will create tasks in next observe
                else:
                    state["status"] = "completed"
            return state
        
        # Use LLM to decide next action
        if self.llm_provider:
            action = await self._llm_decide_action(state)
            state["working_memory"]["llm_action"] = action
        else:
            # Fallback: simple heuristic
            state["working_memory"]["llm_action"] = {
                "action": state["current_task"].get("action"),
                "parameters": state["current_task"].get("parameters", {}),
                "reasoning": "Executing planned task"
            }
        
        return state
    
    async def _llm_decide_action(self, state: AgentState) -> Dict[str, Any]:
        """Use LLM to decide next action."""
        # Build prompt
        prompt = self._build_think_prompt(state)
        
        try:
            response = await self.llm_provider(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"LLM decision failed: {e}")
            return {
                "action": state["current_task"].get("action"),
                "parameters": state["current_task"].get("parameters", {}),
                "reasoning": "Fallback to planned action"
            }
    
    def _build_think_prompt(self, state: AgentState) -> str:
        """Build prompt for LLM reasoning."""
        goal = state["current_goal"]
        task = state["current_task"]
        context = state["working_memory"]
        
        prompt = f"""You are an autonomous AI agent. Decide the next action.

CURRENT GOAL: {goal.get('description') if goal else 'None'}
SUCCESS CRITERIA: {goal.get('success_criteria') if goal else 'None'}

CURRENT TASK: {task.get('description') if task else 'None'}
PLANNED ACTION: {task.get('action') if task else 'None'}
TASK PARAMETERS: {json.dumps(task.get('parameters', {})) if task else '{}'}

RELEVANT CONTEXT:
{json.dumps(context.get('relevant_context', []), indent=2)}

AVAILABLE TOOLS:
{json.dumps(self._get_available_tools(), indent=2)}

Decide the next action. Respond with JSON:
{{
    "action": "tool_name",
    "parameters": {{...}},
    "reasoning": "Why this action",
    "expected_outcome": "What you expect"
}}"""
        return prompt
    
    def _get_available_tools(self) -> List[Dict]:
        """Get list of available tools."""
        plugins = self.framework.list_plugins()
        tools = []
        for name, info in plugins.items():
            if info.get("enabled"):
                for cap in info.get("capabilities", []):
                    tools.append({"name": f"{name}.{cap}", "plugin": name, "capability": cap})
        return tools
    
    async def _act(self, state: AgentState) -> AgentState:
        """Execute the decided action."""
        logger.info(f"[Iteration {state['iteration']}] ACT")
        
        action_info = state["working_memory"].get("llm_action", {})
        action = action_info.get("action")
        parameters = action_info.get("parameters", {})
        
        if not action:
            state["error"] = "No action specified"
            state["status"] = "failed"
            return state
        
        # Execute via framework
        try:
            executor = self.adaptive_framework if self.adaptive_framework else self.framework
            result = await executor.execute(action, parameters)
            
            # Update task status
            if state["current_task"]:
                state["current_task"]["status"] = "completed"
                state["current_task"]["result"] = result
                state["current_task"]["completed_at"] = datetime.now().isoformat()
            
            # Record observation
            state["observations"].append({
                "iteration": state["iteration"],
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "parameters": parameters,
                "result": result,
                "success": "error" not in result
            })
            
            # Learn from execution
            if state["current_task"]:
                await self.memory.learn_from_pattern(
                    pattern_type="task_execution",
                    pattern_data={
                        "action": action,
                        "parameters": parameters,
                        "success": "error" not in result,
                        "result": result
                    },
                    context={"goal_id": state["current_task"].get("goal_id")},
                    confidence=0.7 if "error" not in result else 0.3
                )
            
        except Exception as e:
            state["error"] = str(e)
            state["observations"].append({
                "iteration": state["iteration"],
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "error": str(e)
            })
            
            # Retry logic
            if state["current_task"]:
                state["current_task"]["retry_count"] = state["current_task"].get("retry_count", 0) + 1
                if state["current_task"]["retry_count"] >= 3:
                    state["current_task"]["status"] = "failed"
                    state["current_task"]["error"] = str(e)
                else:
                    state["current_task"]["status"] = "pending"
        
        return state
    
    async def _reflect(self, state: AgentState) -> AgentState:
        """Reflect on progress and learn."""
        logger.info(f"[Iteration {state['iteration']}] REFLECT")
        
        if state["current_goal"]:
            # Analyze goal progress
            goal_id = state["current_goal"].get("id")
            goal_tasks = [t for t in state["tasks"] if t.get("goal_id") == goal_id]
            
            completed = len([t for t in goal_tasks if t.get("status") == "completed"])
            failed = len([t for t in goal_tasks if t.get("status") == "failed"])
            total = len(goal_tasks)
            
            reflection = {
                "goal_id": goal_id,
                "total_tasks": total,
                "completed": completed,
                "failed": failed,
                "success_rate": completed / total if total > 0 else 0,
                "iterations": state["iteration"],
                "observations": len(state["observations"])
            }
            
            # Store reflection
            await self.memory.remember(
                type="reflection",
                content=reflection,
                context={"goal_id": goal_id},
                confidence=0.8,
                source="self_reflection",
                tags={"reflection", goal_id}
            )
            
            # Check if we should continue
            if state["status"] == "completed":
                return state
            
            # If many failures, suggest improvement
            if failed >= 2:
                await self.memory.remember(
                    type="improvement_proposal",
                    content={
                        "goal_id": goal_id,
                        "reason": f"{failed} tasks failed",
                        "suggestion": "Consider alternative approach or new capability"
                    },
                    context={"goal_id": goal_id},
                    confidence=0.7,
                    source="self_reflection",
                    tags={"improvement", goal_id}
                )
        
        # Save checkpoint
        self.checkpoints.append(state.copy())
        if len(self.checkpoints) > 10:
            self.checkpoints.pop(0)
        
        return state
    
    async def run(self, goal: Dict[str, Any] = None, max_iterations: int = 20) -> AgentState:
        """Run the agent loop."""
        self.running = True
        self.state = self._initial_state()
        self.state["max_iterations"] = max_iterations
        self.state["status"] = "running"
        
        if goal:
            goal["id"] = goal.get("id", str(uuid.uuid4())[:8])
            goal["status"] = "active"
            goal["created_at"] = datetime.now().isoformat()
            self.state["goals"].append(goal)
            
            # Decompose goal into tasks (simple version)
            self.state["tasks"] = await self._decompose_goal(goal)
        
        current_node = self.graph.entry_point
        
        while self.running and current_node and current_node != "__end__":
            node = self.graph.nodes.get(current_node)
            if not node:
                break
            
            # Execute node
            self.state = await node.handler(self.state)
            
            # Check termination
            if self.state["status"] in ("completed", "failed", "paused"):
                break
            
            # Determine next node
            next_node = None
            for edge in node.edges:
                if edge == "__end__":
                    next_node = "__end__"
                    break
                if node.condition and node.condition(self.state):
                    next_node = edge
                    break
                elif not node.condition:
                    next_node = edge
                    break
            
            current_node = next_node
        
        self.running = False
        return self.state
    
    async def _decompose_goal(self, goal: Dict) -> List[Dict]:
        """Decompose goal into tasks."""
        # Simple heuristic decomposition
        desc = goal.get("description", "").lower()
        tasks = []
        
        if "file" in desc and ("read" in desc or "list" in desc):
            tasks.append({
                "id": str(uuid.uuid4())[:8],
                "goal_id": goal["id"],
                "description": "List relevant files",
                "action": "file.list",
                "parameters": {"path": "/data/data/com.termux/files/home/workspace", "pattern": "*.py"},
                "status": "pending"
            })
        
        if "shell" in desc or "command" in desc or "run" in desc:
            tasks.append({
                "id": str(uuid.uuid4())[:8],
                "goal_id": goal["id"],
                "description": "Execute shell command",
                "action": "shell.execute",
                "parameters": {"command": "pwd && ls -la"},
                "status": "pending"
            })
        
        if not tasks:
            tasks.append({
                "id": str(uuid.uuid4())[:8],
                "goal_id": goal["id"],
                "description": f"Explore: {goal.get('description')}",
                "action": "learning.track",
                "parameters": {"data": {"goal": goal.get("description"), "phase": "exploration"}},
                "status": "pending"
            })
        
        return tasks
    
    def pause(self):
        self.running = False
        self.state["status"] = "paused"
    
    def resume(self):
        if self.state["status"] == "paused":
            self.state["status"] = "running"
            asyncio.create_task(self.run())
    
    def get_state(self) -> AgentState:
        return self.state
    
    def add_custom_node(self, node: GraphNode):
        self.graph.add_node(node)
    
    def set_llm_provider(self, provider: Callable):
        self.llm_provider = provider


class AgentLoopPlugin(Plugin):
    """Plugin exposing the ReAct agent loop."""
    
    def __init__(self, name: str, framework: Framework, adaptive_framework = None):
        super().__init__(name, framework)
        self.agent: Optional[ReActAgent] = None
        self.adaptive_framework = adaptive_framework
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["agent_run", "agent_pause", "agent_resume", "agent_state", "agent_add_goal"]
    
    async def initialize(self) -> bool:
        memory_plugin = self.framework.get_plugin("memory")
        if memory_plugin and hasattr(memory_plugin, 'memory'):
            memory = memory_plugin.memory
        else:
            from adaptive_framework.memory import SQLiteMemoryStore
            memory = MemoryManager(SQLiteMemoryStore(self.framework.data_dir / "memory.db"))
        
        # Try to get vector memory
        vector_memory = None
        try:
            from adaptive_framework.vector_memory import create_vector_memory
            vector_memory = await create_vector_memory(self.framework.data_dir)
        except Exception as e:
            logger.warning(f"Vector memory not available: {e}")
        
        self.agent = ReActAgent(self.framework, memory, vector_memory, adaptive_framework=self.adaptive_framework)
        
        self.framework.event_bus.subscribe("agent.run", self._handle_run)
        self.framework.event_bus.subscribe("agent.pause", self._handle_pause)
        self.framework.event_bus.subscribe("agent.resume", self._handle_resume)
        self.framework.event_bus.subscribe("agent.state", self._handle_state)
        self.framework.event_bus.subscribe("agent.add_goal", self._handle_add_goal)
        
        return True
    
    async def shutdown(self):
        if self.agent:
            self.agent.pause()
    
    async def _handle_run(self, event: Event):
        goal = event.payload.get("goal")
        max_iterations = event.payload.get("max_iterations", 20)
        
        state = await self.agent.run(goal, max_iterations)
        
        await self.framework.event_bus.publish(Event("agent.run.result", {
            "request_id": event.payload.get("request_id"),
            "state": state
        }))
    
    async def _handle_pause(self, event: Event):
        self.agent.pause()
        await self.framework.event_bus.publish(Event("agent.pause.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))
    
    async def _handle_resume(self, event: Event):
        self.agent.resume()
        await self.framework.event_bus.publish(Event("agent.resume.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))
    
    async def _handle_state(self, event: Event):
        state = self.agent.get_state()
        await self.framework.event_bus.publish(Event("agent.state.result", {
            "request_id": event.payload.get("request_id"),
            "state": state
        }))
    
    async def _handle_add_goal(self, event: Event):
        goal = event.payload.get("goal")
        if self.agent and self.agent.state["status"] == "running":
            goal["id"] = goal.get("id", str(uuid.uuid4())[:8])
            goal["status"] = "active"
            self.agent.state["goals"].append(goal)
            self.agent.state["tasks"].extend(await self.agent._decompose_goal(goal))
        
        await self.framework.event_bus.publish(Event("agent.add_goal.result", {
            "request_id": event.payload.get("request_id"),
            "success": True
        }))