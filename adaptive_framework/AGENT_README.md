# Autonomous AI Agent

A full autonomous AI agent built on the Adaptive Framework with goal-setting, planning, execution, and self-improvement capabilities.

## Features

- **Goal Setting** - Set high-level goals with success criteria
- **Autonomous Planning** - Decomposes goals into executable tasks
- **Task Execution** - Runs tasks with retry logic and error adaptation
- **Self-Reflection** - Analyzes goal execution for insights
- **Continuous Improvement** - Proposes system improvements from experience
- **Memory-Augmented** - Learns from successes and failures

## Architecture

```
AutonomousAgent (Plugin)
├── PlanningEngine - Decomposes goals into tasks
├── ExecutionEngine - Executes tasks with retry/adaptation
├── ReflectionEngine - Self-reflection and improvement proposals
└── Memory Integration - Persistent learning via Adaptive Framework
```

## Quick Start

```python
import asyncio
from adaptive_framework import create_framework
from adaptive_framework.agent import AutonomousAgent

async def main():
    # Create framework
    fw = await create_framework("~/.my_agent")
    
    # Create and start agent
    agent = AutonomousAgent("autonomous_agent", fw.framework, fw)
    fw.framework.register_plugin(agent)
    await fw.framework.enable_plugin("autonomous_agent")
    await agent.start_agent_loop()
    
    # Set goals
    goal_id = await agent.set_goal(
        description="List all Python files and show their contents",
        success_criteria=["Python files listed", "Contents displayed"]
    )
    
    # Wait and check status
    await asyncio.sleep(10)
    status = await agent.get_status()
    print(f"Agent status: {status}")
    
    # Reflect on completion
    reflection = await fw.execute("agent.reflect", {"goal_id": goal_id})
    print(f"Reflection: {reflection}")
    
    # Get improvement proposals
    improvements = await fw.execute("agent.get_improvements", {})
    print(f"Improvements: {improvements}")
    
    await agent.stop_agent_loop()
    await fw.stop()

asyncio.run(main())
```

## Goal Examples

```python
# File operations
await agent.set_goal(
    description="Read all Python files in workspace and list their sizes",
    success_criteria=["List of Python files with sizes displayed"]
)

# Shell commands
await agent.set_goal(
    description="Run shell commands to check system status",
    success_criteria=["System info displayed"]
)

# Data processing
await agent.set_goal(
    description="Analyze log files for errors and create summary report",
    success_criteria=["Error summary created", "Report saved"]
)

# Multi-step workflows
await agent.set_goal(
    description="Find all TODO comments in codebase and create issue list",
    success_criteria=["TODO list generated", "Issues prioritized"]
)
```

## Agent Capabilities (via Events)

| Action | Parameters | Description |
|--------|------------|-------------|
| `agent.set_goal` | `description`, `success_criteria`, `metadata` | Create new goal |
| `agent.get_goal_status` | `goal_id` | Get goal progress |
| `agent.list_goals` | - | List all goals |
| `agent.pause_goal` | `goal_id` | Pause goal execution |
| `agent.resume_goal` | `goal_id` | Resume paused goal |
| `agent.cancel_goal` | `goal_id` | Cancel goal |
| `agent.get_status` | - | Get agent status |
| `agent.reflect` | `goal_id` | Trigger reflection |
| `agent.get_improvements` | - | Get improvement proposals |

## Event System

The agent communicates via events:

```python
# Subscribe to goal completion
fw.subscribe("agent.goal_completed", lambda event: print(f"Goal done: {event.payload}"))

# Subscribe to improvement proposals
fw.subscribe("agent.improvement_proposed", lambda event: print(f"Improvement: {event.payload}"))
```

## Learning & Adaptation

The agent learns automatically:

1. **Successful patterns** - Stored as reusable task templates
2. **Failure adaptation** - Retries with parameter adjustments
3. **Reflection insights** - Analyzes patterns in execution
4. **Improvement proposals** - Suggests new capabilities or workflows

## Demo

```bash
cd adaptive_framework
python -m adaptive_framework.demo_agent
```

## Extension

Create custom planning strategies:

```python
class CustomPlanner(PlanningEngine):
    async def decompose_goal(self, goal):
        # Custom planning logic
        return await super().decompose_goal(goal)

# Use in agent
agent.planner = CustomPlanner(fw.framework, agent.memory)
```