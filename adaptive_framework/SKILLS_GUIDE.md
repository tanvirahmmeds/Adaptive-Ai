# Skills System - Comprehensive Tool Guide

## Overview

The Skills System is a powerful, extensible capability framework that allows you to define, register, and execute reusable capabilities (skills) within the Adaptive Framework. Skills are versioned, typed, and composable units of functionality that can be combined to create complex workflows.

---

## Core Concepts

### Skill Structure

```python
@dataclass
class Skill:
    metadata: SkillMetadata      # Identity, versioning, categorization
    parameters: List[SkillParameter]  # Input validation schema
    returns: Dict[str, Any]      # Output schema
    examples: List[SkillExample] # Usage examples
    implementation: str          # Executable code
    implementation_type: str     # python, javascript, shell, composite
    pre_conditions: List[str]    # Pre-execution checks
    post_conditions: List[str]   # Post-execution guarantees
    side_effects: List[str]      # Documented side effects
    timeout_seconds: int         # Execution timeout
    retry_policy: Dict           # Retry configuration
    rate_limit: int              # Calls per minute
    cache_ttl_seconds: int       # Result caching
```

### Skill Types

| Type | Description |
|------|-------------|
| `BUILTIN` | Core framework skills (read_file, shell_execute, etc.) |
| `USER_DEFINED` | User-created skills |
| `AUTO_GENERATED` | AI-generated from natural language |
| `EXTENSION` | Loaded from extension packages |
| `COMPOSITE` | Composed from multiple sub-skills |

### Skill Categories

| Category | Skills |
|----------|--------|
| `FILE_OPERATIONS` | read_file, write_file, list_files, search_files |
| `SHELL_COMMANDS` | shell_execute, pipeline, background_job |
| `DATA_PROCESSING` | json_process, text_process, csv_process |
| `WEB_API` | http_request, graphql_query, websocket |
| `AI_ML` | embed_text, classify_text, generate_text |
| `CODE_GENERATION` | code_analysis, generate_code, refactor |
| `SYSTEM_ADMIN` | process_manager, service_control, user_mgmt |
| `NETWORKING` | dns_lookup, port_scan, ssh_tunnel |
| `SECURITY` | encrypt, decrypt, hash, sign, verify |
| `MONITORING` | metrics_collect, log_analysis, alert |
| `AUTOMATION` | workflow, scheduler, trigger |
| `CUSTOM` | User-defined categories |

---

## Built-in Skills Reference

### File Operations

#### `builtin.read_file`
Read file contents with encoding and size limits.

```python
# Parameters
{
    "path": "/path/to/file.txt",        # required: file path
    "encoding": "utf-8",                # optional, default: utf-8
    "max_size": 10485760                # optional, default: 10MB
}

# Returns
{
    "content": "file contents",
    "size": 1234,
    "path": "/path/to/file.txt"
}
```

#### `builtin.write_file`
Write content to file with directory creation.

```python
# Parameters
{
    "path": "/path/to/file.txt",        # required
    "content": "Hello World",           # required
    "encoding": "utf-8",                # optional
    "create_dirs": true                 # optional, default: true
}

# Returns
{
    "success": true,
    "path": "/path/to/file.txt",
    "bytes_written": 11
}
```

#### `builtin.list_files`
List directory contents with filtering.

```python
# Parameters
{
    "path": ".",                        # optional, default: .
    "pattern": "*.py",                  # optional, default: *
    "recursive": false,                 # optional
    "include_dirs": true                # optional
}

# Returns
{
    "files": [
        {"name": "main.py", "path": "./main.py", "is_dir": false, "size": 1234},
        {"name": "subdir", "path": "./subdir", "is_dir": true, "size": 0}
    ],
    "count": 2
}
```

### Shell Commands

#### `builtin.shell_execute`
Execute shell commands with full control.

```python
# Parameters
{
    "command": "ls -la",                # required
    "cwd": "/home/user",                # optional, default: .
    "timeout": 60,                      # optional, seconds
    "env": {"VAR": "value"}             # optional, env vars
}

# Returns
{
    "stdout": "output...",
    "stderr": "errors...",
    "returncode": 0
}
```

### Web API

#### `builtin.http_request`
Make HTTP requests with full control.

```python
# Parameters
{
    "url": "https://api.example.com",   # required
    "method": "GET",                    # optional: GET, POST, PUT, DELETE, PATCH
    "headers": {"Authorization": "..."}, # optional
    "body": {"key": "value"},           # optional, for POST/PUT
    "params": {"page": 1},              # optional, query params
    "timeout": 30.0                     # optional
}

# Returns
{
    "status": 200,
    "headers": {...},
    "body": {...}
}
```

### Data Processing

#### `builtin.json_process`
Process JSON with multiple operations.

```python
# Operations: parse, stringify, query, merge, filter, map, reduce
{
    "operation": "query",               # required
    "data": {"users": [{"name": "John", "age": 30}]},
    "query": "users[?age>25].name"      # JMESPath query
}

# Returns: {"result": ["John"]}
```

#### `builtin.text_process`
Text manipulation operations.

```python
# Operations: split, join, replace, regex_replace, extract, upper, lower, trim, count, length
{
    "operation": "regex_replace",
    "text": "Hello World",
    "pattern": "World",
    "replacement": "Python",
    "flags": "i"                        # optional: i, m, s
}

# Returns: {"result": "Hello Python"}
```

### Code Analysis

#### `builtin.code_analysis`
Analyze code for metrics and structure.

```python
# Parameters
{
    "code": "def hello():\n    print('hi')",
    "language": "python",
    "checks": ["complexity", "imports", "functions", "classes"]
}

# Returns
{
    "analysis": {
        "imports": [],
        "functions": [{"name": "hello", "line": 1, "args": []}],
        "classes": [],
        "complexity": 1,
        "lines": 2,
        "chars": 28
    }
}
```

---

## Creating Custom Skills

### Skill Definition Format (JSON)

```json
{
  "metadata": {
    "id": "my.custom_skill",
    "name": "My Custom Skill",
    "version": "1.0.0",
    "type": "user_defined",
    "category": "custom",
    "author": "user",
    "description": "Process user data",
    "tags": ["data", "processing"],
    "dependencies": [],
    "required_tools": ["file_ops"],
    "required_permissions": []
  },
  "parameters": [
    {
      "name": "input_file",
      "type": "file_path",
      "description": "Input CSV file",
      "required": true
    },
    {
      "name": "output_format",
      "type": "enum",
      "description": "Output format",
      "required": false,
      "default": "json",
      "enum_values": ["json", "csv", "parquet"]
    }
  ],
  "returns": {"result": "object", "rows_processed": "integer"},
  "examples": [
    {
      "name": "Convert CSV to JSON",
      "description": "Convert a CSV file to JSON",
      "inputs": {"input_file": "data.csv"},
      "expected_output": {"result": [...], "rows_processed": 100},
      "explanation": "Reads CSV and converts to JSON"
    }
  ],
  "implementation": "async def main(inputs, context): ...",
  "implementation_type": "python",
  "pre_conditions": [],
  "post_conditions": [],
  "side_effects": ["writes output file"],
  "timeout_seconds": 300,
  "rate_limit": 60
}
```

### Python Implementation Template

```python
async def main(inputs, context):
    """
    Main skill function.
    
    Args:
        inputs: Validated input parameters
        context: Execution context with framework access
        
    Returns:
        Dictionary matching the returns schema
    """
    # Access validated inputs
    input_file = inputs["input_file"]
    output_format = inputs.get("output_format", "json")
    
    # Access framework capabilities
    fw = context.get("framework")
    
    # Read input file
    result = await fw.execute("file.read", {"path": input_file})
    if "error" in result:
        return {"error": result["error"]}
    
    # Process data
    import csv, json, io
    csv_data = list(csv.DictReader(io.StringIO(result["content"])))
    
    # Convert format
    if output_format == "json":
        output = json.dumps(csv_data, indent=2)
    elif output_format == "csv":
        output = csv_data  # Already in CSV format
    
    # Write output
    output_path = f"{input_file}.{output_format}"
    await fw.execute("file.write", {
        "path": output_path,
        "content": output if isinstance(output, str) else json.dumps(output)
    })
    
    return {
        "result": "success",
        "output_path": output_path,
        "rows_processed": len(csv_data)
    }
```

---

## Skill Management API

### Register a Skill

```python
# Via CLI
adaptive skill register --file my_skill.json

# Via Python API
await fw.execute("skill.register", {
    "skill": skill_data
})

# Via event
await fw.publish("skill.register", {
    "skill": skill_dict
})
```

### Execute a Skill

```python
# Via CLI
adaptive skill execute my.custom_skill --inputs '{"input_file": "data.csv"}'

# Via Python API
result = await fw.execute("skill.execute", {
    "skill_id": "my.custom_skill",
    "inputs": {"input_file": "data.csv"},
    "context": {}
})

# Direct execution with SkillExecutor
skill = registry.get_skill("my.custom_skill")
result = await executor.execute(skill, {"input_file": "data.csv"}, context)
```

### Search Skills

```python
# Search by query
skills = registry.search_skills("file process", limit=10)

# Filter by category
skills = registry.list_skills(category=SkillCategory.FILE_OPERATIONS)

# Filter by type
skills = registry.list_skills(skill_type=SkillType.USER_DEFINED)

# Filter by tags
skills = registry.list_skills(tags={"file", "csv"})
```

### Skill Statistics

```python
stats = registry.get_skill_stats()
# Returns:
# {
#     "total_skills": 25,
#     "by_category": {"file_operations": 8, "web_api": 5, ...},
#     "by_type": {"builtin": 15, "user_defined": 10},
#     "total_usage": 1250,
#     "experimental_count": 3,
#     "deprecated_count": 1
# }
```

---

## Skill Execution Features

### Input Validation
- Type checking (string, integer, float, boolean, array, object, file_path, etc.)
- Required/optional parameters
- Default values
- Enum validation
- Range validation (min/max)
- Length validation
- Regex pattern matching
- Custom validation via pre_conditions

### Rate Limiting
```python
skill.rate_limit = 60  # calls per minute
```

### Caching
```python
skill.cache_ttl_seconds = 3600  # Cache results for 1 hour
skill.cache_key_template = "{input_file}_{output_format}"
```

### Retry Policy
```python
skill.retry_policy = {
    "max_attempts": 3,
    "backoff_factor": 2.0,
    "retry_on": ["timeout", "network_error"]
}
```

### Timeouts
```python
skill.timeout_seconds = 300  # 5 minutes max
```

### Side Effects Documentation
```python
skill.side_effects = [
    "writes output file to disk",
    "makes HTTP request to external API",
    "modifies database records"
]
```

---

## Composite Skills (Workflows)

Compose multiple skills into workflows:

```json
{
  "metadata": {
    "id": "workflow.process_data",
    "type": "user_defined",
    "category": "automation"
  },
  "implementation_type": "composite",
  "implementation": {
    "steps": [
      {"skill": "builtin.read_file", "inputs": {"path": "{input_path}"}, "output": "file_content"},
      {"skill": "builtin.json_process", "inputs": {"operation": "parse", "data": "{file_content}"}, "output": "parsed_data"},
      {"skill": "builtin.text_process", "inputs": {"operation": "extract", "text": "{parsed_data}", "pattern": "email"}, "output": "emails"},
      {"skill": "builtin.write_file", "inputs": {"path": "{output_path}", "content": "{emails}"}, "output": "write_result"}
    ]
  }
}
```

---

## Skill Development Workflow

### 1. Create Skill Template
```bash
adaptive skill create --template python --name my_skill --category data_processing
```

### 2. Implement Logic
Edit the generated skill file with your implementation.

### 3. Test Locally
```bash
adaptive skill test my.custom_skill --inputs '{"param": "value"}'
```

### 3. Register
```bash
adaptive skill register --file my_skill.json
```

### 4. Test Execution
```bash
adaptive skill execute my.custom_skill --inputs '{"param": "test"}'
```

### 5. Publish (Optional)
```bash
adaptive skill publish my.custom_skill --registry community
```

---

## Best Practices

### 1. Parameter Design
- Use specific types (`file_path` not `string` for paths)
- Provide clear descriptions
- Set sensible defaults
- Include examples

### 2. Error Handling
- Return structured errors: `{"error": "descriptive message"}`
- Don't throw exceptions in implementation
- Document expected errors in examples

### 3. Side Effects
- Always document side effects
- Make idempotent when possible
- Use pre_conditions for validation

### 4. Testing
- Include multiple examples
- Test edge cases
- Validate output schema

### 5. Versioning
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Update `updated_at` on changes
- Deprecate gracefully with `replacement_skill_id`

---

## Skill Registry Statistics

```python
stats = registry.get_skill_stats()
# {
#     "total_skills": 25,
#     "by_category": {
#         "file_operations": 8,
#         "web_api": 5,
#         "data_processing": 4,
#         "shell_commands": 3,
#         "code_generation": 2,
#         "custom": 3
#     },
#     "by_type": {
#         "builtin": 15,
#         "user_defined": 8,
#         "auto_generated": 2
#     },
#     "total_usage": 1250,
#     "experimental_count": 3,
#     "deprecated_count": 1
# }
```

---

## Integration with Agent

Skills can be used directly by the autonomous agent:

```python
# Agent automatically discovers and uses skills
goal = await fw.execute("agent.run", {
    "goal": "Convert all CSV files in workspace to JSON",
    "success_criteria": ["All CSV files converted", "JSON files valid"]
})

# Agent will:
# 1. Use builtin.list_files to find CSV files
# 2. For each file, use custom skill to convert
# 3. Use builtin.write_file to save results
# 4. Track progress and report completion
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Skill not found" | Check skill ID spelling, ensure registered |
| "Input validation failed" | Check parameter types and required fields |
| "Precondition failed" | Verify pre_conditions are met |
| "Rate limit exceeded" | Wait or increase rate_limit |
| "Timeout" | Increase timeout_seconds or optimize code |
| "Module not found" | Install required dependencies |

### Debugging Skills

```python
# Enable debug logging
import logging
logging.getLogger("adaptive_framework.skills").setLevel(logging.DEBUG)

# Check execution history
for record in executor.execution_history:
    print(record)
```

---

## Extending the System

### Custom Implementation Types
```python
# Register custom executor
class MyCustomExecutor:
    async def execute(self, skill, inputs, context):
        # Custom execution logic
        pass

# Register with framework
framework.register_executor("my_type", MyCustomExecutor())
```

### Custom Parameter Types
```python
# Add to ParameterType enum
class ParameterType(Enum):
    # ... existing types ...
    COLOR = "color"
    COORDINATE = "coordinate"
```

### Custom Validation
```python
# Add custom validator
async def validate_color(value):
    if not re.match(r'^#[0-9a-fA-F]{6}$', value):
        raise ValueError("Invalid hex color")

# Use in parameter
SkillParameter(
    name="color",
    type=ParameterType.STRING,
    pattern=r'^#[0-9a-fA-F]{6}$'
)
```

---

## Quick Reference Card

| Command | Description |
|---------|-------------|
| `adaptive skill list` | List all skills |
| `adaptive skill search "query"` | Search skills |
| `adaptive skill get <id>` | Get skill details |
| `adaptive skill execute <id> --inputs '{}'` | Execute skill |
| `adaptive skill register --file skill.json` | Register skill |
| `adaptive skill create --template python --name my_skill` | Create template |
| `adaptive skill stats` | Show registry stats |
| `adaptive skill categories` | List categories |

---

The Skills System provides a powerful, extensible foundation for building reusable capabilities that can be composed into complex workflows, used by autonomous agents, and shared across teams.