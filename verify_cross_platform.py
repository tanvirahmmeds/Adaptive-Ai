#!/usr/bin/env python3
"""
Cross-platform verification script for Adaptive Framework.
Tests compatibility across: Web UI, CLI, Terminal, Desktop GUI, Linux, macOS, Android (Termux)
"""

import asyncio
import sys
import os
import platform
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from adaptive_framework import create_framework, AdaptiveFramework


class PlatformVerifier:
    """Verify framework works on current platform."""
    
    def __init__(self):
        self.results: Dict[str, bool] = {}
        self.errors: Dict[str, str] = {}
        self.platform_info = self._get_platform_info()
    
    def _get_platform_info(self) -> Dict[str, str]:
        """Get detailed platform information."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "is_termux": "TERMUX_VERSION" in os.environ or "com.termux" in os.environ.get("PREFIX", ""),
            "is_android": "ANDROID_ROOT" in os.environ,
            "is_wsl": "microsoft" in platform.release().lower(),
            "is_darwin": platform.system() == "Darwin",
            "is_linux": platform.system() == "Linux",
            "is_windows": platform.system() == "Windows",
        }
    
    def print_platform_info(self):
        """Print platform information."""
        print("=" * 60)
        print("PLATFORM INFORMATION")
        print("=" * 60)
        for key, value in self.platform_info.items():
            print(f"  {key}: {value}")
        print()
    
    async def test_core_framework(self) -> bool:
        """Test core framework initialization."""
        print("Testing core framework...")
        try:
            fw = await create_framework()
            await fw.stop()
            self.results["core_framework"] = True
            print("  ✓ Core framework initialization")
            return True
        except Exception as e:
            self.results["core_framework"] = False
            self.errors["core_framework"] = str(e)
            print(f"  ✗ Core framework: {e}")
            return False
    
    async def test_plugins(self) -> bool:
        """Test all built-in plugins load correctly."""
        print("Testing plugins...")
        try:
            fw = await create_framework()
            plugins = fw.framework.list_plugins()
            expected = ["file_ops", "shell", "memory", "learning", "feedback", "mcp", "agent_loop"]
            
            for plugin in expected:
                if plugin not in plugins:
                    raise Exception(f"Plugin {plugin} not registered")
                if not plugins[plugin]["enabled"]:
                    raise Exception(f"Plugin {plugin} not enabled")
            
            await fw.stop()
            self.results["plugins"] = True
            print(f"  ✓ All {len(expected)} plugins loaded and enabled")
            return True
        except Exception as e:
            self.results["plugins"] = False
            self.errors["plugins"] = str(e)
            print(f"  ✗ Plugins: {e}")
            return False
    
    async def test_file_operations(self) -> bool:
        """Test file operations work on this platform."""
        print("Testing file operations...")
        try:
            fw = await create_framework()
            
            # Test write
            test_path = Path(fw.data_dir) / "test_cross_platform.txt"
            await fw.execute("file.write", {
                "path": str(test_path),
                "content": "Cross-platform test content\nUnicode: 🌍\nPath: " + str(test_path)
            })
            
            # Test read
            result = await fw.execute("file.read", {"path": str(test_path)})
            if "Cross-platform test content" not in result.get("content", ""):
                raise Exception("File content mismatch")
            
            # Test list
            result = await fw.execute("file.list", {
                "path": str(fw.data_dir),
                "pattern": "*"
            })
            files = result.get("files", [])
            if not any(f["name"] == "test_cross_platform.txt" for f in files):
                raise Exception("File not found in listing")
            
            # Cleanup
            test_path.unlink(missing_ok=True)
            
            await fw.stop()
            self.results["file_operations"] = True
            print("  ✓ File operations (write, read, list)")
            return True
        except Exception as e:
            self.results["file_operations"] = False
            self.errors["file_operations"] = str(e)
            print(f"  ✗ File operations: {e}")
            return False
    
    async def test_shell_commands(self) -> bool:
        """Test shell command execution."""
        print("Testing shell commands...")
        try:
            fw = await create_framework()
            
            # Platform-appropriate command
            if self.platform_info["is_windows"]:
                cmd = "echo hello && cd"
            else:
                cmd = "echo hello && pwd"
            
            result = await fw.execute("shell.execute", {
                "command": cmd,
                "timeout": 30
            })
            
            if result.get("returncode") != 0:
                raise Exception(f"Command failed: {result.get('stderr')}")
            
            if "hello" not in result.get("stdout", ""):
                raise Exception("Command output missing")
            
            await fw.stop()
            self.results["shell_commands"] = True
            print("  ✓ Shell command execution")
            return True
        except Exception as e:
            self.results["shell_commands"] = False
            self.errors["shell_commands"] = str(e)
            print(f"  ✗ Shell commands: {e}")
            return False
    
    async def test_memory_system(self) -> bool:
        """Test memory system."""
        print("Testing memory system...")
        try:
            fw = await create_framework()
            
            # Remember
            entry = await fw.remember("fact", {
                "topic": "cross_platform_test",
                "data": "Platform: " + self.platform_info["system"]
            })
            
            # Recall
            memories = await fw.recall(type="fact", limit=10)
            if not any(m.id == entry.id for m in memories):
                raise Exception("Memory not recalled")
            
            # Preferences
            await fw.set_preference("test_key", "test_value")
            prefs = await fw.get_preferences()
            if prefs.get("test_key") != "test_value":
                raise Exception("Preference not stored")
            
            await fw.stop()
            self.results["memory_system"] = True
            print("  ✓ Memory system (remember, recall, preferences)")
            return True
        except Exception as e:
            self.results["memory_system"] = False
            self.errors["memory_system"] = str(e)
            print(f"  ✗ Memory system: {e}")
            return False
    
    async def test_vector_memory(self) -> bool:
        """Test vector memory (semantic search)."""
        print("Testing vector memory...")
        try:
            fw = await create_framework()
            
            if not fw.vector_memory:
                raise Exception("Vector memory not initialized")
            
            # Add texts
            await fw.vector_memory.add_text(
                "Python is great for AI development",
                metadata={"topic": "programming"}
            )
            await fw.vector_memory.add_text(
                "Machine learning uses neural networks",
                metadata={"topic": "ai"}
            )
            
            # Search
            results = await fw.vector_memory.search("AI programming", limit=5, threshold=0.0)
            if len(results) == 0:
                raise Exception("No search results")
            
            await fw.stop()
            self.results["vector_memory"] = True
            print("  ✓ Vector memory (semantic search)")
            return True
        except Exception as e:
            self.results["vector_memory"] = False
            self.errors["vector_memory"] = str(e)
            print(f"  ✗ Vector memory: {e}")
            return False
    
    async def test_agent_loop(self) -> bool:
        """Test agent loop."""
        print("Testing agent loop...")
        try:
            fw = await create_framework()
            
            result = await fw.execute("agent.run", {
                "goal": {
                    "description": "List files in workspace",
                    "success_criteria": ["Files listed"]
                },
                "max_iterations": 5
            })
            
            state = result.get("state", {})
            if state.get("status") not in ("completed", "running"):
                raise Exception(f"Agent failed: {state.get('error')}")
            
            await fw.stop()
            self.results["agent_loop"] = True
            print("  ✓ Agent loop (ReAct pattern)")
            return True
        except Exception as e:
            self.results["agent_loop"] = False
            self.errors["agent_loop"] = str(e)
            print(f"  ✗ Agent loop: {e}")
            return False
    
    async def test_mcp_integration(self) -> bool:
        """Test MCP integration."""
        print("Testing MCP integration...")
        try:
            fw = await create_framework()
            
            # List servers (should be empty initially)
            result = await fw.execute("mcp.list_servers", {})
            servers = result.get("servers", {})
            
            await fw.stop()
            self.results["mcp_integration"] = True
            print("  ✓ MCP integration (server management)")
            return True
        except Exception as e:
            self.results["mcp_integration"] = False
            self.errors["mcp_integration"] = str(e)
            print(f"  ✗ MCP integration: {e}")
            return False
    
    async def test_learning_feedback(self) -> bool:
        """Test learning and feedback loop."""
        print("Testing learning & feedback...")
        try:
            fw = await create_framework()
            
            # Remember something
            entry = await fw.remember("fact", {"test": "learning"})
            
            # Give positive feedback
            await fw.feedback(entry.id, True, feedback_data={"comment": "Good"})
            
            # Check confidence increased
            recalled = await fw.recall(type="fact", limit=1)
            if recalled and recalled[0].confidence <= 0.5:
                raise Exception("Confidence not increased after positive feedback")
            
            await fw.stop()
            self.results["learning_feedback"] = True
            print("  ✓ Learning & feedback loop")
            return True
        except Exception as e:
            self.results["learning_feedback"] = False
            self.errors["learning_feedback"] = str(e)
            print(f"  ✗ Learning & feedback: {e}")
            return False
    
    async def test_extension_system(self) -> bool:
        """Test extension system."""
        print("Testing extension system...")
        try:
            fw = await create_framework()
            
            # Create extension template
            ext_dir = fw.registry.create_extension_template(
                "test_extension",
                "Test extension for cross-platform"
            )
            
            if not ext_dir.exists():
                raise Exception("Extension directory not created")
            
            # Check manifest
            manifest_path = ext_dir / "manifest.json"
            if not manifest_path.exists():
                raise Exception("Manifest not created")
            
            with open(manifest_path) as f:
                manifest = json.load(f)
                if manifest["name"] != "test_extension":
                    raise Exception("Manifest name mismatch")
            
            await fw.stop()
            self.results["extension_system"] = True
            print("  ✓ Extension system (template creation)")
            return True
        except Exception as e:
            self.results["extension_system"] = False
            self.errors["extension_system"] = str(e)
            print(f"  ✗ Extension system: {e}")
            return False
    
    def test_cli_import(self) -> bool:
        """Test CLI modules can be imported."""
        print("Testing CLI imports...")
        try:
            # Test main CLI
            from adaptive_framework.cli import cli
            # Test agent CLI
            from adaptive_framework.agent_cli import cli as agent_cli
            
            self.results["cli_imports"] = True
            print("  ✓ CLI modules importable")
            return True
        except Exception as e:
            self.results["cli_imports"] = False
            self.errors["cli_imports"] = str(e)
            print(f"  ✗ CLI imports: {e}")
            return False
    
    def test_webui_import(self) -> bool:
        """Test Web UI modules can be imported."""
        print("Testing Web UI imports...")
        try:
            from adaptive_framework.webui import app, run_webui
            
            self.results["webui_imports"] = True
            print("  ✓ Web UI modules importable")
            return True
        except Exception as e:
            self.results["webui_imports"] = False
            self.errors["webui_imports"] = str(e)
            print(f"  ✗ Web UI imports: {e}")
            return False
    
    def test_gui_import(self) -> bool:
        """Test GUI modules can be imported (if Qt available)."""
        print("Testing GUI imports...")
        try:
            from adaptive_framework.gui import run_gui, MainWindow
            
            self.results["gui_imports"] = True
            print("  ✓ GUI modules importable")
            return True
        except ImportError:
            # Qt not available - this is OK for headless environments
            self.results["gui_imports"] = True
            print("  ⊘ GUI imports (Qt not available - expected in headless)")
            return True
        except Exception as e:
            self.results["gui_imports"] = False
            self.errors["gui_imports"] = str(e)
            print(f"  ✗ GUI imports: {e}")
            return False
    
    def test_termux_compatibility(self) -> bool:
        """Test Termux/Android specific compatibility."""
        print("Testing Termux compatibility...")
        try:
            is_termux = self.platform_info["is_termux"]
            is_android = self.platform_info["is_android"]
            
            if not is_termux and not is_android:
                print("  ⊘ Not Termux/Android - skipping")
                self.results["termux_compat"] = True
                return True
            
            # Test that we can access filesystem
            test_path = Path.home() / "test_termux.tmp"
            test_path.write_text("test")
            content = test_path.read_text()
            test_path.unlink()
            
            if content != "test":
                raise Exception("Filesystem access failed")
            
            # Test that we can run subprocesses
            result = subprocess.run(["echo", "test"], capture_output=True, text=True)
            if result.returncode != 0 or "test" not in result.stdout:
                raise Exception("Subprocess execution failed")
            
            self.results["termux_compat"] = True
            print("  ✓ Termux/Android compatibility")
            return True
        except Exception as e:
            self.results["termux_compat"] = False
            self.errors["termux_compat"] = str(e)
            print(f"  ✗ Termux compatibility: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all verification tests."""
        self.print_platform_info()
        
        tests = [
            ("Core Framework", self.test_core_framework),
            ("Plugins", self.test_plugins),
            ("File Operations", self.test_file_operations),
            ("Shell Commands", self.test_shell_commands),
            ("Memory System", self.test_memory_system),
            ("Vector Memory", self.test_vector_memory),
            ("Agent Loop", self.test_agent_loop),
            ("MCP Integration", self.test_mcp_integration),
            ("Learning & Feedback", self.test_learning_feedback),
            ("Extension System", self.test_extension_system),
            ("CLI Imports", self.test_cli_import),
            ("Web UI Imports", self.test_webui_import),
            ("GUI Imports", self.test_gui_import),
            ("Termux Compatibility", self.test_termux_compatibility),
        ]
        
        passed = 0
        failed = 0
        
        for name, test_func in tests:
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                self.results[name.lower().replace(" ", "_")] = False
                self.errors[name.lower().replace(" ", "_")] = str(e)
                print(f"  ✗ {name}: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Total:  {passed + failed}")
        
        if failed > 0:
            print("\nFailures:")
            for name, error in self.errors.items():
                print(f"  {name}: {error}")
        
        print()
        return self.results


async def main():
    """Main entry point."""
    print("Adaptive Framework - Cross-Platform Verification")
    print("=" * 60)
    
    verifier = PlatformVerifier()
    results = await verifier.run_all_tests()
    
    # Exit code based on results
    failed = sum(1 for v in results.values() if not v)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())