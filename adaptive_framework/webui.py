"""
Adaptive Framework Web UI - FastAPI-based web interface.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from adaptive_framework import create_framework, AdaptiveFramework


# Global framework instance
framework: Optional[AdaptiveFramework] = None
active_websockets: List[WebSocket] = []


class GoalRequest(BaseModel):
    description: str
    success_criteria: List[str] = []
    max_iterations: int = 20


class ExecuteRequest(BaseModel):
    action: str
    parameters: Dict[str, Any] = {}
    context: Dict[str, Any] = {}


class MemoryRequest(BaseModel):
    type: str
    content: Dict[str, Any]
    context: Dict[str, Any] = {}
    confidence: float = 0.5
    tags: List[str] = []


class MCPConnectRequest(BaseModel):
    name: str
    command: List[str]
    env: Dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global framework
    framework = await create_framework()
    yield
    await framework.stop()


app = FastAPI(
    title="Adaptive Framework Web UI",
    description="Self-improving AI agent with MCP, vector memory, and autonomous capabilities",
    version="0.1.0",
    lifespan=lifespan
)

# Templates and static files
templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

if templates_dir.exists():
    templates = Jinja2Templates(directory=str(templates_dir))
else:
    templates = None

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main dashboard."""
    if templates:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return HTMLResponse("""
    <html>
    <head><title>Adaptive Framework</title></head>
    <body>
        <h1>Adaptive Framework Web UI</h1>
        <p>Dashboard - Templates not found. Create templates/dashboard.html</p>
        <a href="/docs">API Docs</a>
    </body>
    </html>
    """)


@app.get("/api/status")
async def get_status():
    """Get framework status."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    return await framework.execute("agent.state", {})


@app.post("/api/goal")
async def set_goal(goal: GoalRequest):
    """Set a new goal for the agent."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    result = await framework.execute("agent.run", {
        "goal": {
            "description": goal.description,
            "success_criteria": goal.success_criteria
        },
        "max_iterations": goal.max_iterations
    })
    return result


@app.post("/api/execute")
async def execute_action(request: ExecuteRequest):
    """Execute a capability."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    return await framework.execute(request.action, request.parameters, request.context)


@app.post("/api/memory")
async def add_memory(request: MemoryRequest):
    """Add a memory entry."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    return await framework.remember(
        type=request.type,
        content=request.content,
        context=request.context,
        confidence=request.confidence,
        tags=set(request.tags)
    )


@app.get("/api/memory/search")
async def search_memory(query: str, limit: int = 10):
    """Search memories."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    memories = await framework.recall(limit=limit)
    return {"memories": [{"id": m.id, "type": m.type, "content": m.content} for m in memories]}


@app.get("/api/vector/search")
async def vector_search(query: str, limit: int = 10, threshold: float = 0.5):
    """Semantic vector search."""
    if not framework or not framework.vector_memory:
        raise HTTPException(503, "Vector memory not available")
    results = await framework.vector_memory.search(query, limit=limit, threshold=threshold)
    return {"results": [{"text": e.text, "score": s, "metadata": e.metadata} for e, s in results]}


@app.post("/api/mcp/connect")
async def mcp_connect(request: MCPConnectRequest):
    """Connect to MCP server."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    return await framework.execute("mcp.connect", {
        "name": request.name,
        "command": request.command,
        "env": request.env
    })


@app.get("/api/mcp/servers")
async def mcp_servers():
    """List connected MCP servers."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    return await framework.execute("mcp.list_servers", {})


@app.post("/api/mcp/call")
async def mcp_call(server: str, tool: str, arguments: Dict[str, Any]):
    """Call MCP tool."""
    if not framework:
        raise HTTPException(503, "Framework not initialized")
    return await framework.execute("mcp.call_tool", {
        "server": server,
        "tool": tool,
        "arguments": arguments
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe":
                # Subscribe to events
                pass
            elif message.get("type") == "execute":
                # Execute action via websocket
                if framework:
                    result = await framework.execute(
                        message["action"],
                        message.get("parameters", {}),
                        message.get("context", {})
                    )
                    await websocket.send_json({"type": "result", "request_id": message.get("request_id"), "result": result})
            
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


async def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcast event to all connected websockets."""
    message = json.dumps({"type": event_type, "data": data})
    for ws in active_websockets[:]:
        try:
            await ws.send_text(message)
        except:
            active_websockets.remove(ws)


def run_webui(host: str = "0.0.0.0", port: int = 8080, reload: bool = False, data_dir: Optional[str] = None):
    """Run the web UI server."""
    uvicorn.run(
        "adaptive_framework.webui:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )