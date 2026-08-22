"""
Test enhanced framework with MCP, Vector Memory, and Agent Loop.
"""

import asyncio
from adaptive_framework import create_framework


async def test_enhanced_framework():
    """Test all new components."""
    print("=== Enhanced Framework Test ===")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/test_enhanced")
    
    try:
        # Test 1: Vector Memory
        print("\n--- Test 1: Vector Memory ---")
        if fw.vector_memory:
            # Add some texts
            id1 = await fw.vector_memory.add_text(
                "Python is a programming language with dynamic typing",
                metadata={"topic": "programming", "language": "python"}
            )
            id2 = await fw.vector_memory.add_text(
                "JavaScript is used for web development",
                metadata={"topic": "programming", "language": "javascript"}
            )
            id3 = await fw.vector_memory.add_text(
                "Machine learning uses neural networks for pattern recognition",
                metadata={"topic": "ai", "subtopic": "ml"}
            )
            print(f"Added texts with IDs: {id1[:8]}, {id2[:8]}, {id3[:8]}")
            
            # Search
            results = await fw.vector_memory.search("programming language", limit=3, threshold=0.1)
            print(f"Search 'programming language': {len(results)} results")
            for entry, score in results:
                print(f"  Score: {score:.3f} - {entry.text[:50]}...")
            
            results = await fw.vector_memory.search("neural networks", limit=3, threshold=0.1)
            print(f"Search 'neural networks': {len(results)} results")
            for entry, score in results:
                print(f"  Score: {score:.3f} - {entry.text[:50]}...")
        else:
            print("Vector memory not available")
        
        # Test 2: MCP Server (built-in tools)
        print("\n--- Test 2: MCP Server Tools ---")
        # The MCP server is registered, test via events
        result = await fw.execute("mcp.list_servers", {})
        print(f"MCP servers: {result}")
        
        # Test 3: Agent Loop
        print("\n--- Test 3: Agent Loop ---")
        result = await fw.execute("agent.state", {})
        print(f"Agent state: {result.get('state', {}).get('status', 'unknown')}")
        
        # Run agent with a goal
        goal = {
            "description": "List Python files in workspace",
            "success_criteria": ["Files listed"]
        }
        result = await fw.execute("agent.run", {"goal": goal, "max_iterations": 5})
        state = result.get("state", {})
        print(f"Agent run status: {state.get('status')}")
        print(f"Iterations: {state.get('iteration')}")
        print(f"Error: {state.get('error')}")
        print(f"Tasks: {len(state.get('tasks', []))}")
        for task in state.get('tasks', []):
            print(f"  - {task.get('description')}: {task.get('status')}")
            if task.get('error'):
                print(f"    Error: {task.get('error')}")
            if task.get('result'):
                print(f"    Result: {task.get('result')}")
        
        # Test 4: MCP Tool calls via server
        print("\n--- Test 4: MCP Tool Calls ---")
        result = await fw.execute("mcp.call_tool", {
            "server": "local",  # This won't work since we don't have external servers
            "tool": "list_files",
            "arguments": {"path": "/data/data/com.termux/files/home/workspace", "pattern": "*.py"}
        })
        print(f"MCP call result: {result}")
        
        print("\n=== All Tests Completed ===")
        
    finally:
        await fw.stop()
        print("Framework stopped")


if __name__ == "__main__":
    asyncio.run(test_enhanced_framework())