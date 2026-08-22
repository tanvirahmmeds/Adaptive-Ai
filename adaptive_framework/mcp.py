"""
MCP (Model Context Protocol) Integration for Adaptive Framework.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging

from adaptive_framework.core import Plugin, Framework, Event
from adaptive_framework.memory import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP Tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPResource:
    """MCP Resource definition."""
    uri: str
    name: str
    description: str
    mime_type: str


@dataclass
class MCPPrompt:
    """MCP Prompt template."""
    name: str
    description: str
    arguments: List[Dict[str, Any]]


class MCPClient:
    """MCP Client for connecting to MCP servers."""
    
    def __init__(self, server_command: List[str], server_env: Dict[str, str] = None):
        self.server_command = server_command
        self.server_env = server_env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.tools: List[MCPTool] = []
        self.resources: List[MCPResource] = []
        self.prompts: List[MCPPrompt] = []
        self.initialized = False
    
    async def start(self):
        """Start MCP server process and initialize connection."""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            env=self.server_env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Start reading responses
        asyncio.create_task(self._read_responses())
        
        # Initialize
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "adaptive-framework", "version": "1.0.0"}
        })
        
        # List tools
        await self.list_tools()
        await self.list_resources()
        await self.list_prompts()
        
        self.initialized = True
        logger.info(f"MCP client connected to {' '.join(self.server_command)}")
    
    async def stop(self):
        """Stop MCP server."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
    
    async def _read_responses(self):
        """Read responses from MCP server."""
        while self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                response = json.loads(line.decode())
                await self._handle_response(response)
            except Exception as e:
                logger.error(f"MCP read error: {e}")
    
    async def _handle_response(self, response: Dict):
        """Handle JSON-RPC response."""
        req_id = response.get("id")
        if req_id in self.pending_requests:
            future = self.pending_requests.pop(req_id)
            if "error" in response:
                future.set_exception(Exception(response["error"]))
            else:
                future.set_result(response.get("result"))
    
    async def _send_request(self, method: str, params: Dict = None) -> Any:
        """Send JSON-RPC request."""
        self.request_id += 1
        req_id = self.request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method
        }
        if params:
            request["params"] = params
        
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[req_id] = future
        
        data = (json.dumps(request) + "\n").encode()
        self.process.stdin.write(data)
        await self.process.stdin.drain()
        
        return await asyncio.wait_for(future, timeout=30)
    
    async def list_tools(self) -> List[MCPTool]:
        """List available tools from server."""
        result = await self._send_request("tools/list")
        self.tools = [MCPTool(**t) for t in result.get("tools", [])]
        return self.tools
    
    async def list_resources(self) -> List[MCPResource]:
        """List available resources."""
        result = await self._send_request("resources/list")
        self.resources = [MCPResource(**r) for r in result.get("resources", [])]
        return self.resources
    
    async def list_prompts(self) -> List[MCPPrompt]:
        """List available prompts."""
        result = await self._send_request("prompts/list")
        self.prompts = [MCPPrompt(**p) for p in result.get("prompts", [])]
        return self.prompts
    
    async def call_tool(self, name: str, arguments: Dict) -> Any:
        """Call a tool on the MCP server."""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return result
    
    async def read_resource(self, uri: str) -> Any:
        """Read a resource."""
        result = await self._send_request("resources/read", {"uri": uri})
        return result
    
    async def get_prompt(self, name: str, arguments: Dict = None) -> Any:
        """Get a prompt template."""
        result = await self._send_request("prompts/get", {
            "name": name,
            "arguments": arguments or {}
        })
        return result


class MCPServer:
    """MCP Server to expose framework capabilities as tools."""
    
    def __init__(self, framework: Framework, memory: MemoryManager):
        self.framework = framework
        self.memory = memory
        self.tools: Dict[str, Dict] = {}
        self.resources: Dict[str, Dict] = {}
        self.prompts: Dict[str, Dict] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register framework capabilities as MCP tools."""
        self.tools = {
            "read_file": {
                "description": "Read a file from the filesystem",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"}
                    },
                    "required": ["path"]
                },
                "handler": self._handle_read_file
            },
            "write_file": {
                "description": "Write content to a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                },
                "handler": self._handle_write_file
            },
            "list_files": {
                "description": "List files in a directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path", "default": "."},
                        "pattern": {"type": "string", "description": "Glob pattern", "default": "*"}
                    }
                },
                "handler": self._handle_list_files
            },
            "execute_shell": {
                "description": "Execute a shell command",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to execute"},
                        "cwd": {"type": "string", "description": "Working directory", "default": "."},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60}
                    },
                    "required": ["command"]
                },
                "handler": self._handle_execute_shell
            },
            "remember": {
                "description": "Store a memory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Memory type"},
                        "content": {"type": "object", "description": "Memory content"},
                        "context": {"type": "object", "description": "Context"},
                        "confidence": {"type": "number", "description": "Confidence 0-1", "default": 0.5},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["type", "content"]
                },
                "handler": self._handle_remember
            },
            "recall": {
                "description": "Retrieve memories",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Memory type filter"},
                        "query": {"type": "string", "description": "Search query"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "default": 20}
                    }
                },
                "handler": self._handle_recall
            },
            "set_goal": {
                "description": "Set an autonomous agent goal",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "Goal description"},
                        "success_criteria": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["description"]
                },
                "handler": self._handle_set_goal
            }
        }
    
    async def _handle_read_file(self, args: Dict) -> Dict:
        path = Path(args["path"])
        if path.exists() and path.is_file():
            return {"content": path.read_text(), "path": str(path)}
        return {"error": "File not found", "path": str(path)}
    
    async def _handle_write_file(self, args: Dict) -> Dict:
        path = Path(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"])
        return {"success": True, "path": str(path)}
    
    async def _handle_list_files(self, args: Dict) -> Dict:
        path = Path(args.get("path", "."))
        pattern = args.get("pattern", "*")
        files = list(path.glob(pattern))
        return {
            "files": [
                {"name": f.name, "path": str(f), "is_dir": f.is_dir(), "size": f.stat().st_size if f.is_file() else 0}
                for f in files
            ]
        }
    
    async def _handle_execute_shell(self, args: Dict) -> Dict:
        proc = await asyncio.create_subprocess_shell(
            args["command"],
            cwd=args.get("cwd", "."),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=args.get("timeout", 60))
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": proc.returncode
        }
    
    async def _handle_remember(self, args: Dict) -> Dict:
        entry = await self.memory.remember(
            type=args["type"],
            content=args["content"],
            context=args.get("context", {}),
            confidence=args.get("confidence", 0.5),
            tags=set(args.get("tags", []))
        )
        return {"entry_id": entry.id}
    
    async def _handle_recall(self, args: Dict) -> Dict:
        entries = await self.memory.recall(
            type=args.get("type"),
            tags=set(args.get("tags", [])),
            limit=args.get("limit", 20)
        )
        return {
            "entries": [
                {"id": e.id, "type": e.type, "content": e.content, "confidence": e.confidence, "tags": list(e.tags)}
                for e in entries
            ]
        }
    
    async def _handle_set_goal(self, args: Dict) -> Dict:
        agent_plugin = self.framework.get_plugin("autonomous_agent")
        if agent_plugin and hasattr(agent_plugin, "set_goal"):
            goal_id = await agent_plugin.set_goal(
                description=args["description"],
                success_criteria=args.get("success_criteria", [])
            )
            return {"goal_id": goal_id}
        return {"error": "Autonomous agent not available"}


class MCPPlugin(Plugin):
    """Plugin for MCP integration."""
    
    def __init__(self, name: str, framework: Framework):
        super().__init__(name, framework)
        self.memory: Optional[MemoryManager] = None
        self.server: Optional[MCPServer] = None
        self.clients: Dict[str, MCPClient] = {}
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return ["mcp_connect", "mcp_disconnect", "mcp_list_tools", "mcp_call_tool", "mcp_list_servers"]
    
    async def initialize(self) -> bool:
        # Get memory
        memory_plugin = self.framework.get_plugin("memory")
        if memory_plugin and hasattr(memory_plugin, 'memory'):
            self.memory = memory_plugin.memory
        else:
            logger.warning("Memory plugin not available")
        
        # Create MCP server
        if self.memory:
            self.server = MCPServer(self.framework, self.memory)
        
        # Subscribe to events
        self.framework.event_bus.subscribe("mcp.connect", self._handle_connect)
        self.framework.event_bus.subscribe("mcp.disconnect", self._handle_disconnect)
        self.framework.event_bus.subscribe("mcp.list_tools", self._handle_list_tools)
        self.framework.event_bus.subscribe("mcp.call_tool", self._handle_call_tool)
        self.framework.event_bus.subscribe("mcp.list_servers", self._handle_list_servers)
        
        return True
    
    async def shutdown(self):
        for client in self.clients.values():
            await client.stop()
        self.clients.clear()
    
    async def _handle_connect(self, event: Event):
        """Connect to an MCP server."""
        name = event.payload.get("name")
        command = event.payload.get("command")
        env = event.payload.get("env", {})
        
        if name in self.clients:
            await self.framework.event_bus.publish(Event("mcp.connect.result", {
                "request_id": event.payload.get("request_id"),
                "error": f"Already connected to {name}"
            }))
            return
        
        client = MCPClient(command, env)
        try:
            await client.start()
            self.clients[name] = client
            await self.framework.event_bus.publish(Event("mcp.connect.result", {
                "request_id": event.payload.get("request_id"),
                "name": name,
                "tools": len(client.tools),
                "resources": len(client.resources),
                "prompts": len(client.prompts)
            }))
        except Exception as e:
            await self.framework.event_bus.publish(Event("mcp.connect.result", {
                "request_id": event.payload.get("request_id"),
                "error": str(e)
            }))
    
    async def _handle_disconnect(self, event: Event):
        """Disconnect from an MCP server."""
        name = event.payload.get("name")
        client = self.clients.pop(name, None)
        if client:
            await client.stop()
            await self.framework.event_bus.publish(Event("mcp.disconnect.result", {
                "request_id": event.payload.get("request_id"),
                "success": True
            }))
        else:
            await self.framework.event_bus.publish(Event("mcp.disconnect.result", {
                "request_id": event.payload.get("request_id"),
                "error": f"Not connected to {name}"
            }))
    
    async def _handle_list_tools(self, event: Event):
        """List tools from connected servers."""
        server_name = event.payload.get("server")
        if server_name and server_name in self.clients:
            tools = self.clients[server_name].tools
            await self.framework.event_bus.publish(Event("mcp.list_tools.result", {
                "request_id": event.payload.get("request_id"),
                "server": server_name,
                "tools": [{"name": t.name, "description": t.description, "schema": t.input_schema} for t in tools]
            }))
        else:
            # All servers
            all_tools = {}
            for name, client in self.clients.items():
                all_tools[name] = [
                    {"name": t.name, "description": t.description, "schema": t.input_schema}
                    for t in client.tools
                ]
            await self.framework.event_bus.publish(Event("mcp.list_tools.result", {
                "request_id": event.payload.get("request_id"),
                "servers": all_tools
            }))
    
    async def _handle_call_tool(self, event: Event):
        """Call a tool on an MCP server."""
        server_name = event.payload.get("server")
        tool_name = event.payload.get("tool")
        arguments = event.payload.get("arguments", {})
        
        client = self.clients.get(server_name)
        if not client:
            await self.framework.event_bus.publish(Event("mcp.call_tool.result", {
                "request_id": event.payload.get("request_id"),
                "error": f"Not connected to {server_name}"
            }))
            return
        
        try:
            result = await client.call_tool(tool_name, arguments)
            await self.framework.event_bus.publish(Event("mcp.call_tool.result", {
                "request_id": event.payload.get("request_id"),
                "result": result
            }))
        except Exception as e:
            await self.framework.event_bus.publish(Event("mcp.call_tool.result", {
                "request_id": event.payload.get("request_id"),
                "error": str(e)
            }))
    
    async def _handle_list_servers(self, event: Event):
        """List connected MCP servers."""
        servers = {
            name: {
                "tools": len(c.tools),
                "resources": len(c.resources),
                "prompts": len(c.prompts)
            }
            for name, c in self.clients.items()
        }
        await self.framework.event_bus.publish(Event("mcp.list_servers.result", {
            "request_id": event.payload.get("request_id"),
            "servers": servers
        }))


# Convenience functions
async def connect_mcp_server(framework: Framework, name: str, command: List[str], env: Dict = None):
    """Connect to an MCP server."""
    request_id = uuid.uuid4().hex[:8]
    future = asyncio.get_event_loop().create_future()
    
    def handler(event):
        if event.payload.get("request_id") == request_id:
            future.set_result(event.payload)
    
    framework.event_bus.subscribe("mcp.connect.result", handler)
    
    try:
        await framework.event_bus.publish(Event("mcp.connect", {
            "request_id": request_id,
            "name": name,
            "command": command,
            "env": env or {}
        }))
        return await asyncio.wait_for(future, timeout=30)
    finally:
        framework.event_bus.unsubscribe("mcp.connect.result", handler)