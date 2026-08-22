# Adaptive AI Framework

An extensible AI framework that grows and learns with user needs. Built on a plugin architecture with persistent memory, feedback-driven learning, and dynamic capability creation.

## Features

- **Plugin Architecture** - Modular capabilities that can be enabled/disabled at runtime
- **Persistent Memory** - SQLite-backed memory with confidence scoring and access tracking
- **Feedback Learning** - Explicit and implicit feedback adjusts memory confidence
- **Pattern Recognition** - Automatically learns patterns from interactions
- **Dynamic Extensions** - Create new capabilities at runtime from descriptions
- **Workflows** - Chain multiple capabilities into automated workflows
- **Evolution** - Framework suggests improvements based on usage patterns

## Installation

```bash
# No external dependencies - pure Python 3.8+
cd /path/to/adaptive_framework
```

## Quick Start

```python
import asyncio
from adaptive_framework import create_framework

async def main():
    # Create and start framework
    fw = await create_framework("~/.my_adaptive_framework")
    
    # Execute capabilities
    await fw.execute("file.write", {"path": "test.txt", "content": "Hello!"})
    result = await fw.execute("file.read", {"path": "test.txt"})
    print(result["content"])  # "Hello!"
    
    # Remember and recall
    await fw.remember("fact", {"topic": "AI", "info": "Adaptive frameworks learn"})
    facts = await fw.recall(type="fact")
    
    # Learn from feedback
    entry = await fw.remember("preference", {"key": "style", "value": "concise"})
    await fw.feedback(entry.id, True)  # Positive feedback increases confidence
    
    # Process user request - auto-suggests new capabilities
    result = await fw.process_request("translate text to Spanish")
    # Returns suggestion to create new capability if none exists
    
    # Auto-create capability from description
    await fw.create_capability(
        "translate",
        "Translate text between languages",
        examples=[{"input": {"text": "hello", "target": "es"}, "output": "hola"}]
    )
    
    # Evolve framework from accumulated feedback
    evolution = await fw.evolve()
    print(evolution["suggestions"])  # Improvement suggestions
    
    await fw.stop()

asyncio.run(main())
```

## Architecture

```
adaptive_framework/
├── core.py          # Framework, EventBus, Plugin base class
├── memory.py        # MemoryManager, SQLiteMemoryStore, SkillMemory
├── plugins.py       # Built-in plugins (file, shell, memory, learning, feedback)
├── extensions.py    # ExtensionRegistry, CapabilityBuilder, GrowthManager
├── __main__.py      # AdaptiveFramework main class
└── demo.py          # Usage examples
```

## Core Concepts

### Plugins
Capabilities are implemented as plugins. Built-in plugins:
- **file_ops** - Read/write/list/search files
- **shell** - Execute commands (sync and background)
- **memory** - Remember/recall/feedback/preferences
- **learning** - Track interactions, analyze patterns, suggest improvements
- **feedback** - Collect user feedback and corrections

### Memory System
- **MemoryEntry** - Typed memories (fact, preference, pattern, skill, correction)
- **Confidence scoring** - 0.0 to 1.0, adjusted by feedback
- **Context-aware recall** - Query by type, tags, context similarity
- **Access tracking** - Frequently accessed memories stay relevant

### Learning
- **Explicit feedback** - User rates responses (positive/negative)
- **Implicit learning** - Pattern detection from interaction sequences
- **Corrections** - High-confidence user corrections override memories
- **Skill tracking** - Records skill usage patterns for optimization

### Extensions
- **Manifest-based** - JSON manifest defines plugin metadata
- **Dynamic loading** - Load/unload at runtime
- **Template generation** - Create new extension scaffolding
- **Auto-capability creation** - Generate plugins from descriptions

### Growth Manager
- Processes user requests and suggests new capabilities
- Auto-creates capabilities from natural language
- Evolution engine analyzes feedback and suggests improvements

## Built-in Capabilities

| Action | Parameters | Description |
|--------|------------|-------------|
| `file.read` | `path` | Read file content |
| `file.write` | `path`, `content` | Write file |
| `file.list` | `path`, `pattern` | List files |
| `file.search` | `path`, `query` | Search file contents |
| `shell.execute` | `command`, `cwd`, `timeout` | Run shell command |
| `shell.background` | `command`, `cwd` | Start background process |
| `memory.remember` | `type`, `content`, `context`, `confidence` | Store memory |
| `memory.recall` | `type`, `context`, `tags`, `min_confidence` | Retrieve memories |
| `memory.feedback` | `entry_id`, `positive`, `weight` | Provide feedback |
| `learning.track` | `data` | Track interaction for learning |
| `learning.analyze` | - | Get pattern analysis |
| `feedback.submit` | `target_id`, `positive`, `comment` | Submit feedback |
| `feedback.correction` | `correction`, `context` | Submit correction |

## Creating Custom Extensions

```python
# 1. Create template
ext_dir = fw.registry.create_extension_template("my_tool", "Does something useful")

# 2. Edit the generated plugin file at ext_dir/my_tool_plugin.py

# 3. Load and enable
plugin = fw.registry.load_extension("my_tool")
await fw.framework.enable_plugin("my_tool")

# 4. Use it
await fw.execute("my_tool.action", {"param": "value"})
```

## Auto-Creating Capabilities

```python
# From description
await fw.create_capability(
    "analyze_code",
    "Analyze Python code for complexity and issues",
    examples=[
        {"input": {"code": "def foo(): pass"}, "output": {"complexity": 1}}
    ]
)

# From workflow steps
steps = [
    {"action": "file.list", "parameters": {"path": ".", "pattern": "*.py"}},
    {"action": "shell.execute", "parameters": {"command": "python -m py_compile {{results.step_0.files[0].path}}"}}
]
await fw.growth.builder.create_workflow_from_steps("lint_python", steps)
```

## Memory Types

| Type | Use Case | Example |
|------|----------|---------|
| `fact` | General knowledge | `{"topic": "python", "info": "indentation matters"}` |
| `preference` | User preferences | `{"key": "theme", "value": "dark"}` |
| `pattern` | Learned patterns | `{"pattern_type": "skill_usage", "data": {...}}` |
| `skill` | Capability definitions | `{"name": "translate", "description": "..."}` |
| `correction` | User corrections | `{"issue": "wrong", "fix": "correct"}` |

## Event System

Plugins communicate via events:
```python
# Subscribe to events
fw.subscribe("file.read.result", handler)

# Publish events
await fw.publish("custom.event", {"data": "value"})
```

## Persistence

All data stored in `data_dir`:
- `memory.db` - SQLite memory database
- `extensions/` - User-created extensions
- `plugins/` - Built-in plugin data

## Running Demos

```bash
python -m adaptive_framework.demo
```

## Extending the Framework

1. **Add a plugin** - Subclass `Plugin`, implement `initialize`/`shutdown`
2. **Add memory type** - Use `memory.remember(type="custom", ...)`
3. **Add learning signal** - Register handler with `memory.register_learning_handler()`
4. **Create extension** - Add manifest.json and plugin in `extensions/name/`

## License

MIT