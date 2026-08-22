# AI Agent Development - Comprehensive Guide

Based on analysis of top GitHub repositories (LangChain, LangGraph, OpenAI Agents, SuperAGI, Hermes, MCP, and more).

---

## 1. Core Architecture Patterns

### 1.1 Agent Loop (ReAct Pattern)
```
┌─────────────┐
│   Observe   │ ← Perceive environment, read state
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Think     │ ← Reason about goal, plan next action
│  (LLM)      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Act      │ ← Execute tool, delegate, respond
└──────┬──────┘
       │
       ▼
    (Loop)
```

**Best Practice**: Keep the loop tight. Minimize LLM calls per iteration. Use structured output (JSON) for tool calls.

### 1.2 State Management
```python
# LangGraph-style state graph
class AgentState(TypedDict):
    messages: List[BaseMessage]
    goals: List[Goal]
    tasks: List[Task]
    memory: Dict[str, Any]
    context: Dict[str, Any]
    iteration: int
```

### 1.3 Multi-Agent Orchestration
- **Hierarchical**: Supervisor → Workers
- **Peer-to-peer**: Agents communicate via message bus
- **Swarm**: Dynamic agent spawning for parallel work

---

## 2. Tool/Function Calling

### 2.1 Tool Definition Schema (OpenAI/MCP Standard)
```json
{
  "name": "read_file",
  "description": "Read contents of a file",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "File path"}
    },
    "required": ["path"]
  }
}
```

### 2.2 Tool Execution Patterns
| Pattern | Use Case |
|---------|----------|
| **Sync** | Fast operations (file read, calculation) |
| **Async** | I/O, network, long-running |
| **Streaming** | Progress updates, large outputs |
| **Batch** | Multiple independent operations |

### 2.3 Tool Safety
- **Allowlist/denylist** by tool name
- **Confirmation prompts** for destructive actions
- **Sandboxing** (Docker, WASM, subprocess isolation)
- **Rate limiting** per tool

---

## 3. Skills System (Procedural Memory)

### 3.1 Skill Structure (agentskills.io standard)
```yaml
# skill.yaml
name: "analyze_code"
version: "1.0.0"
description: "Analyze code for complexity and issues"
author: "user"
entry_point: "main.py"
parameters:
  - name: "path"
    type: "string"
    required: true
  - name: "language"
    type: "string"
    default: "python"
returns:
  type: "object"
  properties:
    complexity: "number"
    issues: "array"
```

### 3.2 Skill Lifecycle
1. **Discovery** - Scan skills directory
2. **Loading** - Dynamic import, validation
3. **Registration** - Add to agent's toolset
4. **Execution** - Invoke with parameters
5. **Learning** - Record outcomes, improve

### 3.3 Skill Composition
```python
# Chain skills into workflows
workflow = [
    {"skill": "list_files", "params": {"pattern": "*.py"}},
    {"skill": "analyze_code", "params": {"path": "{{results.files[0].path}}"}, "for_each": "files"},
    {"skill": "generate_report", "params": {"analyses": "{{results}}"}}
]
```

---

## 4. Memory Systems

### 4.1 Memory Types
| Type | Purpose | Retention |
|------|---------|-----------|
| **Episodic** | Specific events, conversations | Session + long-term |
| **Semantic** | Facts, knowledge, concepts | Permanent |
| **Procedural** | Skills, procedures, habits | Permanent, evolves |
| **Working** | Current context, scratchpad | Session only |

### 4.2 Memory Implementation (Best Practices)
```python
class MemoryManager:
    def __init__(self):
        self.episodic = VectorDB()      # For similarity search
        self.semantic = GraphDB()       # For relationships
        self.procedural = SkillStore()  # For skills
        self.working = ContextWindow()  # Token-limited
    
    def store(self, memory: MemoryEntry):
        # Route to appropriate store by type
        pass
    
    def retrieve(self, query: str, context: Dict) -> List[MemoryEntry]:
        # Hybrid search: vector + graph + keyword
        pass
```

### 4.3 Memory Consolidation
- **Short-term → Long-term**: Periodic summarization
- **Importance scoring**: Frequency, recency, emotional weight
- **Forgetting curve**: Decay low-importance memories

---

## 5. Model Context Protocol (MCP)

### 5.1 MCP Architecture
```
┌─────────────┐     JSON-RPC      ┌─────────────┐
│   Client    │ ◄──────────────► │   Server    │
│  (Agent)    │                   │  (Tools)    │
└─────────────┘                   └─────────────┘
```

### 5.2 MCP Capabilities
| Capability | Description |
|------------|-------------|
| **Resources** | Read-only data (files, APIs, databases) |
| **Tools** | Executable functions with side effects |
| **Prompts** | Reusable prompt templates |
| **Sampling** | LLM calls from server to client |

### 5.3 Integration Pattern
```python
# Client side (in agent)
mcp_client = MCPClient()
tools = await mcp_client.list_tools("filesystem")
result = await mcp_client.call_tool("filesystem", "read_file", {"path": "/tmp/test.txt"})

# Server side (expose tools)
@mcp.tool()
def read_file(path: str) -> str:
    return Path(path).read_text()
```

---

## 6. Hermes Agent Specifics

### 6.1 Key Features to Emulate
| Feature | Implementation |
|---------|---------------|
| **Closed learning loop** | Auto-create skills from successful tasks |
| **Skill self-improvement** | Modify skill code based on failures |
| **FTS5 session search** | Full-text search with SQLite FTS5 |
| **Honcho user modeling** | Dialectic user profiles |
| **Cron scheduling** | Natural language → cron jobs |
| **Subagents** | Isolated parallel workstreams |
| **Tool Gateway** | Unified API for external services |

### 6.2 Hermes Configuration
```yaml
# ~/.hermes/config.yaml
model:
  provider: "nous"
  name: "hermes-3-70b"
tools:
  enabled: ["filesystem", "shell", "web_search", "mcp"]
skills:
  auto_create: true
  auto_improve: true
memory:
  backend: "sqlite+fts5"
  consolidation_interval: 3600
cron:
  enabled: true
gateway:
  platforms: ["telegram", "discord"]
```

---

## 7. Best Practices from Top Frameworks

### 7.1 LangGraph (Stateful Agents)
- **Explicit state graph** with nodes/edges
- **Checkpointing** for recovery
- **Human-in-the-loop** at specific nodes
- **Streaming** intermediate states

### 7.2 OpenAI Agents (Lightweight)
- **Handoffs** between specialized agents
- **Guardrails** for input/output validation
- **Tracing** for observability
- **Minimal abstraction** over function calling

### 7.3 SuperAGI (Autonomous)
- **Goal-oriented** with recursive task breakdown
- **Agent marketplace** for sharing agents
- **Performance metrics** per agent
- **Multi-modal** support

### 7.4 Hermes (Self-Improving)
- **Skill auto-creation** from task patterns
- **Skill evolution** during use
- **Cross-session memory** with user modeling
- **Platform-agnostic** messaging

---

## 8. Enhanced Framework Design

Based on all learnings, here's the **ideal architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT CORE                                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Planning │  │ Execution│  │ Reflection│ │  Memory  │    │
│  │ Engine   │  │ Engine   │  │ Engine   │  │ Manager  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
          │            │            │            │
          ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                     TOOL LAYER                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Built-in│ │  MCP    │ │ Skills  │ │ Custom  │           │
│  │ Tools   │ │ Servers │ │ System  │ │ Tools   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Event   │ │ Plugin  │ │ Config  │ │ Logging │           │
│  │ Bus     │ │ System  │ │ Manager │ │/Tracing│           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Implementation Checklist

### Core Framework
- [ ] Event-driven architecture (pub/sub)
- [ ] Plugin system with dynamic loading
- [ ] Configuration management (YAML + env vars)
- [ ] Structured logging + tracing
- [ ] Health checks + monitoring

### Agent Loop
- [ ] Observe → Think → Act cycle
- [ ] Structured output parsing (JSON)
- [ ] Retry with exponential backoff
- [ ] Timeout handling per tool
- [ ] Human confirmation for critical actions

### Memory
- [ ] Episodic (vector DB for similarity)
- [ ] Semantic (knowledge graph)
- [ ] Procedural (skills registry)
- [ ] Working (context window management)
- [ ] Consolidation pipeline

### Tools
- [ ] Built-in: filesystem, shell, web, code
- [ ] MCP client integration
- [ ] Skill system (agentskills.io compatible)
- [ ] Custom tool registration
- [ ] Tool composition/workflows

### Learning
- [ ] Success/failure pattern recording
- [ ] Skill auto-creation from patterns
- [ ] Skill self-improvement (code modification)
- [ ] User preference learning
- [ ] Cross-session continuity

### Orchestration
- [ ] Goal → Task decomposition
- [ ] Dependency resolution
- [ ] Parallel execution
- [ ] Subagent spawning
- [ ] Progress streaming

### Interfaces
- [ ] CLI (TUI with history, autocomplete)
- [ ] REST/WebSocket API
- [ ] Messaging gateways (Telegram, Discord, Slack)
- [ ] MCP server (expose agent as tool)

### Deployment
- [ ] Docker support
- [ ] Serverless (Modal, Daytona, Vercel)
- [ ] SSH/remote execution
- [ ] Cron scheduling
- [ ] Configuration migration

---

## 10. Next Steps for Our Framework

Based on this research, here are the priority enhancements for our `adaptive_framework`:

### Priority 1: Core Improvements
1. **Structured Tool Calling** - Use JSON Schema for all tools
2. **MCP Integration** - Add MCP client + server support
3. **Proper Agent Loop** - Observe/Think/Act with state graph
4. **Vector Memory** - Add embeddings for semantic search

### Priority 2: Learning Loop
5. **Skill Auto-Creation** - Generate skills from successful task sequences
6. **Skill Self-Improvement** - Modify skill code based on failures
7. **User Modeling** - Build dialectic profiles (Honcho-style)

### Priority 3: Production Features
8. **Observability** - Tracing, metrics, debugging
9. **Messaging Gateway** - Telegram/Discord/Slack
10. **Cron Scheduler** - Natural language → scheduled tasks
11. **Subagent Support** - Parallel isolated workstreams

### Priority 4: Ecosystem
12. **Skills Hub** - Registry for sharing skills
13. **Agent Marketplace** - Share agent configurations
14. **MCP Registry** - Browse/connect MCP servers

---

## 11. Resources

### Frameworks to Study
| Repo | Stars | Key Innovation |
|------|-------|----------------|
| langchain-ai/langgraph | 40k | Stateful graphs, checkpointing |
| openai/openai-agents-python | 28k | Lightweight, handoffs, guardrails |
| TransformerOptimus/SuperAGI | 17k | Autonomous, marketplace |
| NousResearch/hermes-agent | 234k | Self-improving, closed loop |
| modelcontextprotocol/python-sdk | 24k | Standard tool protocol |
| lastmile-ai/mcp-agent | 8k | MCP-native agents |

### Learning Resources
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Hermes Docs](https://hermes-agent.nousresearch.com/docs/)
- [AgentSkills.io](https://agentskills.io/)

### Papers
- ReAct: Synergizing Reasoning and Acting in Language Models
- Generative Agents: Interactive Simulacra of Human Behavior
- Language Agents with Structured State
- MCP: Model Context Protocol Specification