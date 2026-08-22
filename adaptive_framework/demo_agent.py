"""
Demo script for the Autonomous Agent.
"""

import asyncio
from pathlib import Path
from adaptive_framework import create_framework
from adaptive_framework.agent import AutonomousAgent


async def demo_autonomous_agent():
    """Demo the autonomous agent capabilities."""
    print("=== Autonomous Agent Demo ===")
    
    # Create framework with agent
    fw = await create_framework("/data/data/com.termux/files/home/workspace/agent_demo")
    
    try:
        # Create and register agent
        agent = AutonomousAgent("autonomous_agent", fw.framework)
        fw.framework.register_plugin(agent)
        await fw.framework.enable_plugin("autonomous_agent")
        
        # Start the agent loop
        await agent.start_agent_loop()
        
        print("\n--- Setting Goals ---")
        
        # Goal 1: File operations
        goal1 = await agent.set_goal(
            description="Read all Python files in the workspace and list their sizes",
            success_criteria=["List of Python files with sizes displayed"],
            metadata={"type": "file_operations"}
        )
        print(f"Goal 1 created: {goal1}")
        
        # Goal 2: Shell command
        goal2 = await agent.set_goal(
            description="Run a shell command to show current directory and date",
            success_criteria=["Current directory and date displayed"],
            metadata={"type": "shell_operations"}
        )
        print(f"Goal 2 created: {goal2}")
        
        # Wait for goals to process
        print("\n--- Waiting for execution ---")
        for i in range(10):
            await asyncio.sleep(2)
            status = await agent.get_status()
            print(f"Agent status: {status['active_goals']} active goals, "
                  f"{status['total_tasks_pending']} pending tasks, "
                  f"{status['total_tasks_running']} running tasks")
            
            # Check goal statuses
            for goal_id in [goal1, goal2]:
                result = await fw.execute("agent.get_goal_status", {"goal_id": goal_id})
                goal_status = result.get("result", {})
                if goal_status.get("status") == "completed":
                    print(f"Goal {goal_id} completed!")
                    break
        
        # Get final status
        print("\n--- Final Goal Status ---")
        for goal_id in [goal1, goal2]:
            result = await fw.execute("agent.get_goal_status", {"goal_id": goal_id})
            goal_status = result.get("result", {})
            print(f"Goal {goal_id}: {goal_status.get('status', 'unknown')}")
            for task in goal_status.get("tasks", []):
                print(f"  Task: {task['description']} - {task['status']}")
        
        # Trigger reflection
        print("\n--- Reflection ---")
        for goal_id in [goal1, goal2]:
            result = await fw.execute("agent.reflect", {"goal_id": goal_id})
            reflection = result.get("result", {})
            print(f"Reflection for {goal_id}:")
            print(f"  Success rate: {reflection.get('success_rate', 0):.1%}")
            print(f"  Insights: {len(reflection.get('insights', []))}")
            print(f"  Improvements: {len(reflection.get('improvements', []))}")
        
        # Get improvements
        print("\n--- Proposed Improvements ---")
        result = await fw.execute("agent.get_improvements", {})
        improvements = result.get("result", {}).get("improvements", [])
        for imp in improvements:
            print(f"  {imp['type']}: {imp.get('suggestion', imp.get('reason', ''))}")
        
        # Stop agent loop
        await agent.stop_agent_loop()
        
    finally:
        await fw.stop()
        print("\nFramework stopped")


async def demo_continuous_agent():
    """Demo continuous autonomous operation."""
    print("\n=== Continuous Agent Demo ===")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/agent_continuous")
    
    try:
        agent = AutonomousAgent("autonomous_agent", fw.framework)
        fw.framework.register_plugin(agent)
        await fw.framework.enable_plugin("autonomous_agent")
        await agent.start_agent_loop()
        
        # Set multiple goals
        goals = []
        for desc in [
            "Create a summary file of all .py files in workspace",
            "List all directories in workspace",
            "Create a simple Python script that prints hello world"
        ]:
            goal_id = await agent.set_goal(
                description=desc,
                success_criteria=[f"Completed: {desc}"]
            )
            goals.append(goal_id)
            print(f"Created goal: {goal_id}")
        
        # Let it run for a bit
        print("Running agent for 15 seconds...")
        await asyncio.sleep(15)
        
        # Check results
        status = await agent.get_status()
        print(f"Final status: {status}")
        
        await agent.stop_agent_loop()
        
    finally:
        await fw.stop()


async def main():
    await demo_autonomous_agent()
    # await demo_continuous_agent()
    print("\n=== Agent demos completed ===")


if __name__ == "__main__":
    asyncio.run(main())