"""
Simple test to verify framework works.
"""

import asyncio
from adaptive_framework import create_framework


async def test_file_ops():
    """Test just file operations."""
    print("Testing file operations...")
    
    fw = await create_framework("/data/data/com.termux/files/home/workspace/test_demo")
    
    try:
        # Test write
        print("Writing file...")
        result = await fw.execute("file.write", {
            "path": "/data/data/com.termux/files/home/workspace/test_demo/test.txt",
            "content": "Hello from Adaptive Framework!"
        })
        print(f"Write result: {result}")
        
        # Test read
        print("Reading file...")
        result = await fw.execute("file.read", {
            "path": "/data/data/com.termux/files/home/workspace/test_demo/test.txt"
        })
        print(f"Read result: {result}")
        
        # Test list
        print("Listing files...")
        result = await fw.execute("file.list", {
            "path": "/data/data/com.termux/files/home/workspace/test_demo",
            "pattern": "*"
        })
        print(f"List result: {result}")
        
        print("All file ops passed!")
        
    finally:
        await fw.stop()
        print("Framework stopped")


if __name__ == "__main__":
    asyncio.run(test_file_ops())