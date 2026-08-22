"""
Demo script showing how to use the Adaptive Framework.
"""

import asyncio
from pathlib import Path
from adaptive_framework import create_framework


async def demo_basic_usage():
    """Basic framework usage."""
    print("=== Basic Usage Demo ===")
    
    # Create framework
    fw = await create_framework("/data/data/com.termux/files/home/workspace/adaptive_demo")
    
    try:
        # File operations
        print("\n--- File Operations ---")
        await fw.execute("file.write", {
            "path": "/data/data/com.termux/files/home/workspace/adaptive_demo/test.txt",
            "content": "Hello from Adaptive Framework!"
        })
        
        result = await fw.execute("file.read", {
            "path": "/data/data/com.termux/files/home/workspace/adaptive_demo/test.txt"
        })
        print(f"Read file: {result.get('content')}")
        
        # Shell commands
        print("\n--- Shell Commands ---")
        result = await fw.execute("shell.execute", {
            "command": "echo 'Hello from shell' && pwd"
        })
        print(f"Shell output: {result.get('stdout')}")
        
        # Memory
        print("\n--- Memory ---")
        await fw.remember("fact", {"topic": "python", "info": "Python is a programming language"})
        await fw.remember("preference", {"key": "language", "value": "Python"}, source="user")
        
        facts = await fw.recall(type="fact")
        print(f"Facts: {len(facts)}")
        
        prefs = await fw.get_preferences()
        print(f"Preferences: {prefs}")
        
        # Feedback
        print("\n--- Feedback ---")
        entry = await fw.remember("fact", {"test": "feedback demo"})
        await fw.feedback(entry.id, True, feedback_data={"comment": "Good info!"})
        
        # Learning/patterns
        print("\n--- Learning ---")
        await fw.publish("learning.track", {
            "data": {"action": "file_read", "file": "test.txt"}
        })
        
        analysis = await fw.execute("learning.analyze", {})
        print(f"Interaction analysis: {analysis.get('total_interactions')} events")
        
    finally:
        await fw.stop()
        print("\nFramework stopped")


async def demo_growth():
    """Demo growth/evolution capabilities."""
    print("\n=== Growth Demo ===")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/adaptive_demo_growth")
    
    try:
        # Process user request - no existing capability
        print("\n--- New Capability Request ---")
        result = await fw.process_request("summarize text files in a directory")
        print(f"Result: {result}")
        
        # Auto-create capability
        print("\n--- Creating Capability ---")
        if result.get("can_auto_create"):
            msg = await fw.create_capability(
                "summarize_files",
                "Summarize all text files in a directory",
                examples=[
                    {"input": {"directory": "/path/to/files"}, "output": "summary.txt"}
                ]
            )
            print(f"Created: {msg}")
        
        # Evolve from feedback
        print("\n--- Evolution ---")
        # Add some feedback first
        await fw.remember("correction", {"issue": "summaries too long", "fix": "limit to 100 words"})
        
        evolution = await fw.evolve()
        print(f"Evolution plan: {evolution}")
        
    finally:
        await fw.stop()


async def demo_extension():
    """Demo custom extension creation."""
    print("\n=== Extension Demo ===")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/adaptive_demo_ext")
    
    try:
        # Create extension template
        print("\n--- Creating Extension Template ---")
        ext_dir = fw.registry.create_extension_template(
            "my_custom_tool", 
            "A custom tool for specific tasks"
        )
        print(f"Created at: {ext_dir}")
        
        # Load and enable it
        print("\n--- Loading Extension ---")
        plugin = fw.registry.load_extension("my_custom_tool")
        if plugin:
            await fw.framework.enable_plugin("my_custom_tool")
            print("Extension loaded and enabled")
            
            # Use it
            result = await fw.execute("my_custom_tool.action", {})
            print(f"Extension result: {result}")
        else:
            print("Failed to load extension (expected - it's a template)")
        
    finally:
        await fw.stop()


async def demo_workflow():
    """Demo workflow creation."""
    print("\n=== Workflow Demo ===")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/adaptive_demo_wf")
    
    try:
        # Create a workflow
        print("\n--- Creating Workflow ---")
        steps = [
            {"action": "file.list", "parameters": {"path": "/data/data/com.termux/files/home/workspace", "pattern": "*.py"}},
            {"action": "file.read", "parameters": {"path": "{{results.step_0.files[0].path}}"}, "condition": "len(results.step_0.files) > 0"}
        ]
        
        path = await fw.growth.builder.create_workflow_from_steps("process_txt_files", steps)
        print(f"Workflow created at: {path}")
        
    finally:
        await fw.stop()


async def demo_autonomous_agent():
    """Demo the autonomous agent."""
    print("\n=== Autonomous Agent Demo ===")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/agent_demo")
    
    try:
        # Create and start agent
        agent = fw.agent_loop.agent
        await agent.run({
            "description": "List all Python files in workspace",
            "success_criteria": ["List of Python files displayed"]
        })
        
        # Check results
        state = agent.get_state()
        print(f"Agent status: {state['status']}")
        for task in state['tasks']:
            print(f"  Task: {task['description']} - {task['status']}")
        
    finally:
        await fw.stop()


async def main():
    """Run all demos."""
    await demo_basic_usage()
    await demo_growth()
    await demo_extension()
    await demo_workflow()
    # await demo_autonomous_agent()  # Uncomment to test agent
    print("\n=== All demos completed ===")


if __name__ == "__main__":
    asyncio.run(main())