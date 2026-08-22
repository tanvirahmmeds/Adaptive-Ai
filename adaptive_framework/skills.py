"""
Skills System - Reusable, versioned capabilities with tool integration.
"""

import asyncio
import json
import hashlib
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable, Union
from typing_extensions import TypedDict
import logging
import inspect

logger = logging.getLogger(__name__)


class SkillType(Enum):
    """Types of skills."""
    BUILTIN = "builtin"           # Core framework skills
    USER_DEFINED = "user_defined" # User-created skills
    AUTO_GENERATED = "auto_generated" # AI-generated skills
    EXTENSION = "extension"       # From extensions
    COMPOSITE = "composite"       # Composed from other skills


class SkillCategory(Enum):
    """Skill categories for organization."""
    FILE_OPERATIONS = "file_operations"
    SHELL_COMMANDS = "shell_commands"
    DATA_PROCESSING = "data_processing"
    WEB_API = "web_api"
    AI_ML = "ai_ml"
    CODE_GENERATION = "code_generation"
    SYSTEM_ADMIN = "system_admin"
    NETWORKING = "networking"
    SECURITY = "security"
    MONITORING = "monitoring"
    AUTOMATION = "automation"
    CUSTOM = "custom"


class ParameterType(Enum):
    """Parameter types for skill inputs."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE_PATH = "file_path"
    DIRECTORY_PATH = "directory_path"
    URL = "url"
    EMAIL = "email"
    REGEX = "regex"
    JSON = "json"
    BASE64 = "base64"
    ENUM = "enum"


@dataclass
class SkillParameter:
    """Skill parameter definition."""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum_values: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    examples: List[Any] = field(default_factory=list)


@dataclass
class SkillExample:
    """Example usage of a skill."""
    name: str
    description: str
    inputs: Dict[str, Any]
    expected_output: Dict[str, Any]
    explanation: str = ""


@dataclass
class SkillMetadata:
    """Skill metadata."""
    id: str
    name: str
    version: str
    type: SkillType
    category: SkillCategory
    author: str
    created_at: datetime
    updated_at: datetime
    description: str
    long_description: str = ""
    tags: Set[str] = field(default_factory=set)
    dependencies: List[str] = field(default_factory=list)  # Other skill IDs
    required_tools: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    min_framework_version: str = "0.1.0"
    max_framework_version: Optional[str] = None
    is_experimental: bool = False
    is_deprecated: bool = False
    replacement_skill_id: Optional[str] = None
    usage_count: int = 0
    success_rate: float = 1.0
    average_latency_ms: float = 0.0


@dataclass
class Skill:
    """Complete skill definition."""
    metadata: SkillMetadata
    parameters: List[SkillParameter] = field(default_factory=list)
    returns: Dict[str, Any] = field(default_factory=dict)  # Output schema
    examples: List[SkillExample] = field(default_factory=list)
    implementation: str = ""  # Python code or reference
    implementation_type: str = "python"  # python, javascript, shell, wasm, etc.
    pre_conditions: List[str] = field(default_factory=list)
    post_conditions: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    rate_limit: Optional[int] = None  # calls per minute
    cache_ttl_seconds: Optional[int] = None
    cache_key_template: Optional[str] = None


class SkillExecutor:
    """Executes skills with proper isolation and monitoring."""
    
    def __init__(self, framework):
        self.framework = framework
        self.execution_history: List[Dict[str, Any]] = []
        self.active_executions: Dict[str, asyncio.Task] = {}
    
    async def execute(self, skill: Skill, inputs: Dict[str, Any], 
                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a skill with given inputs."""
        execution_id = hashlib.md5(f"{skill.metadata.id}{datetime.now()}".encode()).hexdigest()[:12]
        start_time = asyncio.get_event_loop().time()
        
        # Validate inputs
        validation_result = self._validate_inputs(skill, inputs)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": f"Input validation failed: {validation_result['errors']}",
                "execution_id": execution_id
            }
        
        # Check preconditions
        pre_check = await self._check_preconditions(skill, inputs, context)
        if not pre_check["passed"]:
            return {
                "success": False,
                "error": f"Precondition failed: {pre_check['reason']}",
                "execution_id": execution_id
            }
        
        # Check rate limit
        if skill.rate_limit:
            recent_calls = sum(1 for h in self.execution_history 
                             if h["skill_id"] == skill.metadata.id 
                             and (asyncio.get_event_loop().time() - h["timestamp"]) < 60)
            if recent_calls >= skill.rate_limit:
                return {
                    "success": False,
                    "error": f"Rate limit exceeded: {skill.rate_limit} calls/minute",
                    "execution_id": execution_id
                }
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                self._execute_implementation(skill, inputs, context),
                timeout=skill.timeout_seconds
            )
            
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Record execution
            execution_record = {
                "execution_id": execution_id,
                "skill_id": skill.metadata.id,
                "timestamp": asyncio.get_event_loop().time(),
                "duration_ms": execution_time,
                "success": True,
                "inputs": inputs,
                "outputs": result
            }
            self.execution_history.append(execution_record)
            
            # Update skill metadata
            skill.metadata.usage_count += 1
            skill.metadata.average_latency_ms = (
                (skill.metadata.average_latency_ms * (skill.metadata.usage_count - 1) + execution_time) 
                / skill.metadata.usage_count
            )
            
            return {
                "success": True,
                "result": result,
                "execution_id": execution_id,
                "duration_ms": execution_time
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Skill timed out after {skill.timeout_seconds}s",
                "execution_id": execution_id
            }
        except Exception as e:
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            execution_record = {
                "execution_id": execution_id,
                "skill_id": skill.metadata.id,
                "timestamp": asyncio.get_event_loop().time(),
                "duration_ms": execution_time,
                "success": False,
                "error": str(e),
                "inputs": inputs
            }
            self.execution_history.append(execution_record)
            
            # Update success rate
            skill.metadata.success_rate = (
                (skill.metadata.success_rate * (skill.metadata.usage_count) + 0) 
                / (skill.metadata.usage_count + 1)
            )
            skill.metadata.usage_count += 1
            
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution_id,
                "duration_ms": execution_time
            }
    
    async def _execute_implementation(self, skill: Skill, inputs: Dict[str, Any], 
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute the skill implementation."""
        if skill.implementation_type == "python":
            return await self._execute_python(skill, inputs, context)
        elif skill.implementation_type == "shell":
            return await self._execute_shell(skill, inputs, context)
        elif skill.implementation_type == "javascript":
            return await self._execute_javascript(skill, inputs, context)
        elif skill.implementation_type == "composite":
            return await self._execute_composite(skill, inputs, context)
        else:
            raise ValueError(f"Unknown implementation type: {skill.implementation_type}")
    
    async def _execute_python(self, skill: Skill, inputs: Dict[str, Any], 
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute Python implementation."""
        # Create execution namespace
        namespace = {
            "inputs": inputs,
            "context": context or {},
            "framework": self.framework,
            "asyncio": asyncio,
            "json": json,
            "os": __import__("os"),
            "pathlib": __import__("pathlib"),
            "datetime": __import__("datetime"),
            "hashlib": __import__("hashlib"),
            "re": __import__("re"),
            "base64": __import__("base64"),
            "typing": __import__("typing"),
        }
        
        # Add framework shortcuts if available
        if hasattr(self.framework, 'execute'):
            namespace["fw_execute"] = self.framework.execute
        if hasattr(self.framework, 'remember'):
            namespace["fw_remember"] = self.framework.remember
        if hasattr(self.framework, 'recall'):
            namespace["fw_recall"] = self.framework.recall
        if hasattr(self.framework, 'device_execute'):
            namespace["fw_device"] = self.framework.device_execute
        
        # Execute the code
        exec(skill.implementation, namespace)
        
        # Call the main function if it exists
        if "main" in namespace:
            result = namespace["main"](inputs, context or {})
            if asyncio.iscoroutine(result):
                result = await result
            return result
        elif "execute" in namespace:
            result = namespace["execute"](inputs, context or {})
            if asyncio.iscoroutine(result):
                result = await result
            return result
        else:
            # Return the namespace for inspection
            return {"namespace_keys": list(namespace.keys())}
    
    async def _execute_shell(self, skill: Skill, inputs: Dict[str, Any], 
                            context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute shell implementation."""
        # Prepare environment
        env = os.environ.copy()
        for key, value in inputs.items():
            if isinstance(value, str):
                env[f"SKILL_INPUT_{key.upper()}"] = value
        
        # Execute
        proc = await asyncio.create_subprocess_shell(
            skill.implementation,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await proc.communicate()
        
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": proc.returncode
        }
    
    async def _execute_javascript(self, skill: Skill, inputs: Dict[str, Any], 
                                 context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute JavaScript implementation (requires Node.js)."""
        # Write temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            js_code = f"""
const inputs = {json.dumps(inputs)};
const context = {json.dumps(context or {})};

{skill.implementation}

async function run() {{
    return await main(inputs, context);
}}
run().then(result => console.log(JSON.stringify(result))).catch(err => console.error(JSON.stringify({{error: err.message}})));
"""
            f.write(js_code)
            temp_path = f.name
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise Exception(f"JS execution failed: {stderr.decode()}")
            
            return json.loads(stdout.decode())
        finally:
            os.unlink(temp_path)
    
    async def _execute_composite(self, skill: Skill, inputs: Dict[str, Any], 
                                context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute composite skill (sequence of sub-skills)."""
        # Implementation would parse skill.implementation as a workflow definition
        # For now, return placeholder
        return {"composite_execution": "not_implemented"}
    
    def _validate_inputs(self, skill: Skill, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate inputs against skill parameters."""
        errors = []
        
        # Check required parameters
        for param in skill.parameters:
            if param.required and param.name not in inputs:
                errors.append(f"Required parameter missing: {param.name}")
                continue
            
            if param.name in inputs:
                value = inputs[param.name]
                
                # Type validation
                if param.type == ParameterType.STRING and not isinstance(value, str):
                    errors.append(f"Parameter {param.name} must be a string")
                elif param.type == ParameterType.INTEGER and not isinstance(value, int):
                    errors.append(f"Parameter {param.name} must be an integer")
                elif param.type == ParameterType.FLOAT and not isinstance(value, (int, float)):
                    errors.append(f"Parameter {param.name} must be a number")
                elif param.type == ParameterType.BOOLEAN and not isinstance(value, bool):
                    errors.append(f"Parameter {param.name} must be a boolean")
                elif param.type == ParameterType.ARRAY and not isinstance(value, list):
                    errors.append(f"Parameter {param.name} must be an array")
                elif param.type == ParameterType.OBJECT and not isinstance(value, dict):
                    errors.append(f"Parameter {param.name} must be an object")
                
                # Range validation
                if param.min_value is not None and isinstance(value, (int, float)):
                    if value < param.min_value:
                        errors.append(f"Parameter {param.name} must be >= {param.min_value}")
                if param.max_value is not None and isinstance(value, (int, float)):
                    if value > param.max_value:
                        errors.append(f"Parameter {param.name} must be <= {param.max_value}")
                
                # Length validation
                if param.min_length is not None and hasattr(value, '__len__'):
                    if len(value) < param.min_length:
                        errors.append(f"Parameter {param.name} must have length >= {param.min_length}")
                if param.max_length is not None and hasattr(value, '__len__'):
                    if len(value) > param.max_length:
                        errors.append(f"Parameter {param.name} must have length <= {param.max_length}")
                
                # Pattern validation
                if param.pattern and isinstance(value, str):
                    import re
                    if not re.match(param.pattern, value):
                        errors.append(f"Parameter {param.name} doesn't match pattern: {param.pattern}")
                
                # Enum validation
                if param.enum_values and value not in param.enum_values:
                    errors.append(f"Parameter {param.name} must be one of: {param.enum_values}")
        
        # Check for unexpected parameters
        param_names = {p.name for p in skill.parameters}
        for key in inputs:
            if key not in param_names:
                errors.append(f"Unexpected parameter: {key}")
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    async def _check_preconditions(self, skill: Skill, inputs: Dict[str, Any], 
                                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Check skill preconditions."""
        for condition in skill.pre_conditions:
            # Simple condition evaluation
            try:
                # Could evaluate as Python expression
                result = eval(condition, {"inputs": inputs, "context": context or {}})
                if not result:
                    return {"passed": False, "reason": f"Precondition failed: {condition}"}
            except Exception as e:
                return {"passed": False, "reason": f"Precondition error: {e}"}
        
        return {"passed": True}


class SkillRegistry:
    """Registry for managing skills."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.skills_dir = self.data_dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        self.skills: Dict[str, Skill] = {}
        self.executor: Optional[SkillExecutor] = None
        self._load_skills()
        self._register_builtin_skills()
    
    def set_executor(self, executor: SkillExecutor):
        self.executor = executor
    
    def register_skill(self, skill: Skill) -> bool:
        """Register a new skill."""
        # Validate skill
        if not self._validate_skill(skill):
            return False
        
        # Check for conflicts
        if skill.metadata.id in self.skills:
            existing = self.skills[skill.metadata.id]
            if existing.metadata.version == skill.metadata.version:
                logger.warning(f"Skill {skill.metadata.id} v{skill.metadata.version} already registered")
                return False
        
        # Save to disk
        self._save_skill(skill)
        
        # Register in memory
        self.skills[skill.metadata.id] = skill
        
        logger.info(f"Registered skill: {skill.metadata.id} v{skill.metadata.version}")
        return True
    
    def unregister_skill(self, skill_id: str) -> bool:
        """Unregister a skill."""
        if skill_id not in self.skills:
            return False
        
        # Remove from disk
        skill_file = self.skills_dir / f"{skill_id}.json"
        if skill_file.exists():
            skill_file.unlink()
        
        # Remove from memory
        del self.skills[skill_id]
        
        logger.info(f"Unregistered skill: {skill_id}")
        return True
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self.skills.get(skill_id)
    
    def list_skills(self, category: SkillCategory = None, 
                   skill_type: SkillType = None,
                   tags: Set[str] = None) -> List[Skill]:
        skills = list(self.skills.values())
        
        if category:
            skills = [s for s in skills if s.metadata.category == category]
        if skill_type:
            skills = [s for s in skills if s.metadata.type == skill_type]
        if tags:
            skills = [s for s in skills if tags.issubset(s.metadata.tags)]
        
        return skills
    
    def search_skills(self, query: str, limit: int = 20) -> List[Skill]:
        """Search skills by name, description, tags."""
        query_lower = query.lower()
        results = []
        
        for skill in self.skills.values():
            score = 0
            if query_lower in skill.metadata.name.lower():
                score += 10
            if query_lower in skill.metadata.description.lower():
                score += 5
            if any(query_lower in tag.lower() for tag in skill.metadata.tags):
                score += 3
            if query_lower in skill.metadata.category.value.lower():
                score += 2
            
            if score > 0:
                results.append((score, skill))
        
        results.sort(key=lambda x: -x[0])
        return [s for _, s in results[:limit]]
    
    def get_skill_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        by_category = {}
        by_type = {}
        total_usage = 0
        
        for skill in self.skills.values():
            cat = skill.metadata.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            
            typ = skill.metadata.type.value
            by_type[typ] = by_type.get(typ, 0) + 1
            
            total_usage += skill.metadata.usage_count
        
        return {
            "total_skills": len(self.skills),
            "by_category": by_category,
            "by_type": by_type,
            "total_usage": total_usage,
            "experimental_count": sum(1 for s in self.skills.values() if s.metadata.is_experimental),
            "deprecated_count": sum(1 for s in self.skills.values() if s.metadata.is_deprecated),
        }
    
    def _validate_skill(self, skill: Skill) -> bool:
        """Validate skill definition."""
        # Check required metadata fields
        if not skill.metadata.id or not skill.metadata.name:
            logger.error("Skill must have id and name")
            return False
        
        if not skill.metadata.description:
            logger.error("Skill must have description")
            return False
        
        # Validate parameter names are unique
        param_names = [p.name for p in skill.parameters]
        if len(param_names) != len(set(param_names)):
            logger.error("Duplicate parameter names")
            return False
        
        return True
    
    def _save_skill(self, skill: Skill):
        """Save skill to disk."""
        skill_file = self.skills_dir / f"{skill.metadata.id}.json"
        
        # Convert to dict for JSON serialization
        data = {
            "metadata": {
                **asdict(skill.metadata),
                "created_at": skill.metadata.created_at.isoformat(),
                "updated_at": skill.metadata.updated_at.isoformat(),
                "tags": list(skill.metadata.tags),
                "type": skill.metadata.type.value,
                "category": skill.metadata.category.value,
            },
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum_values": p.enum_values,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "pattern": p.pattern,
                    "min_length": p.min_length,
                    "max_length": p.max_length,
                    "examples": p.examples,
                }
                for p in skill.parameters
            ],
            "returns": skill.returns,
            "examples": [
                {
                    "name": e.name,
                    "description": e.description,
                    "inputs": e.inputs,
                    "expected_output": e.expected_output,
                    "explanation": e.explanation,
                }
                for e in skill.examples
            ],
            "implementation": skill.implementation,
            "implementation_type": skill.implementation_type,
            "pre_conditions": skill.pre_conditions,
            "post_conditions": skill.post_conditions,
            "side_effects": skill.side_effects,
            "timeout_seconds": skill.timeout_seconds,
            "retry_policy": skill.retry_policy,
            "rate_limit": skill.rate_limit,
            "cache_ttl_seconds": skill.cache_ttl_seconds,
            "cache_key_template": skill.cache_key_template,
        }
        
        with open(skill_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_skills(self):
        """Load skills from disk."""
        for skill_file in self.skills_dir.glob("*.json"):
            try:
                with open(skill_file) as f:
                    data = json.load(f)
                
                skill = self._deserialize_skill(data)
                self.skills[skill.metadata.id] = skill
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_file}: {e}")
    
    def _deserialize_skill(self, data: Dict) -> Skill:
        """Deserialize skill from JSON."""
        meta = data["metadata"]
        metadata = SkillMetadata(
            id=meta["id"],
            name=meta["name"],
            version=meta["version"],
            type=SkillType(meta["type"]),
            category=SkillCategory(meta["category"]),
            author=meta["author"],
            created_at=datetime.fromisoformat(meta["created_at"]),
            updated_at=datetime.fromisoformat(meta["updated_at"]),
            description=meta["description"],
            long_description=meta.get("long_description", ""),
            tags=set(meta.get("tags", [])),
            dependencies=meta.get("dependencies", []),
            required_tools=meta.get("required_tools", []),
            required_permissions=meta.get("required_permissions", []),
            min_framework_version=meta.get("min_framework_version", "0.1.0"),
            max_framework_version=meta.get("max_framework_version"),
            is_experimental=meta.get("is_experimental", False),
            is_deprecated=meta.get("is_deprecated", False),
            replacement_skill_id=meta.get("replacement_skill_id"),
            usage_count=meta.get("usage_count", 0),
            success_rate=meta.get("success_rate", 1.0),
            average_latency_ms=meta.get("average_latency_ms", 0.0),
        )
        
        parameters = [
            SkillParameter(
                name=p["name"],
                type=ParameterType(p["type"]),
                description=p["description"],
                required=p.get("required", True),
                default=p.get("default"),
                enum_values=p.get("enum_values"),
                min_value=p.get("min_value"),
                max_value=p.get("max_value"),
                pattern=p.get("pattern"),
                min_length=p.get("min_length"),
                max_length=p.get("max_length"),
                examples=p.get("examples", []),
            )
            for p in data.get("parameters", [])
        ]
        
        examples = [
            SkillExample(
                name=e["name"],
                description=e["description"],
                inputs=e["inputs"],
                expected_output=e["expected_output"],
                explanation=e.get("explanation", ""),
            )
            for e in data.get("examples", [])
        ]
        
        return Skill(
            metadata=metadata,
            parameters=parameters,
            returns=data.get("returns", {}),
            examples=examples,
            implementation=data.get("implementation", ""),
            implementation_type=data.get("implementation_type", "python"),
            pre_conditions=data.get("pre_conditions", []),
            post_conditions=data.get("post_conditions", []),
            side_effects=data.get("side_effects", []),
            timeout_seconds=data.get("timeout_seconds", 300),
            retry_policy=data.get("retry_policy", {}),
            rate_limit=data.get("rate_limit"),
            cache_ttl_seconds=data.get("cache_ttl_seconds"),
            cache_key_template=data.get("cache_key_template"),
        )
    
    def _register_builtin_skills(self):
        """Register built-in skills."""
        builtin_skills = [
            self._create_read_file_skill(),
            self._create_write_file_skill(),
            self._create_list_files_skill(),
            self._create_shell_execute_skill(),
            self._create_http_request_skill(),
            self._create_json_process_skill(),
            self._create_text_process_skill(),
            self._create_code_analysis_skill(),
        ]
        
        for skill in builtin_skills:
            if skill.metadata.id not in self.skills:
                self.register_skill(skill)
    
    def _create_read_file_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.read_file",
                name="Read File",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.FILE_OPERATIONS,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Read contents of a file",
                tags={"file", "read", "builtin"},
                required_tools=["file_ops"],
            ),
            parameters=[
                SkillParameter(
                    name="path",
                    type=ParameterType.FILE_PATH,
                    description="Path to the file to read",
                    required=True,
                ),
                SkillParameter(
                    name="encoding",
                    type=ParameterType.STRING,
                    description="File encoding",
                    required=False,
                    default="utf-8",
                ),
                SkillParameter(
                    name="max_size",
                    type=ParameterType.INTEGER,
                    description="Maximum file size in bytes",
                    required=False,
                    default=10485760,  # 10MB
                ),
            ],
            returns={"content": "string", "size": "integer", "path": "string"},
            implementation='''
async def main(inputs, context):
    path = inputs["path"]
    encoding = inputs.get("encoding", "utf-8")
    max_size = inputs.get("max_size", 10485760)
    
    fw = context.get("framework")
    if not fw:
        return {"error": "Framework not available"}
    
    result = await fw.execute("file.read", {"path": path})
    if "error" in result:
        return {"error": result["error"]}
    
    content = result.get("content", "")
    if len(content) > max_size:
        return {"error": f"File exceeds max size of {max_size} bytes"}
    
    return {"content": content, "size": len(content), "path": path}
''',
            examples=[
                SkillExample(
                    name="Read a text file",
                    description="Read a simple text file",
                    inputs={"path": "/path/to/file.txt"},
                    expected_output={"content": "file contents", "size": 123, "path": "/path/to/file.txt"},
                    explanation="Reads the entire file content as text"
                ),
            ],
        )
    
    def _create_write_file_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.write_file",
                name="Write File",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.FILE_OPERATIONS,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Write content to a file",
                tags={"file", "write", "builtin"},
                required_tools=["file_ops"],
            ),
            parameters=[
                SkillParameter(
                    name="path",
                    type=ParameterType.FILE_PATH,
                    description="Path to the file to write",
                    required=True,
                ),
                SkillParameter(
                    name="content",
                    type=ParameterType.STRING,
                    description="Content to write",
                    required=True,
                ),
                SkillParameter(
                    name="encoding",
                    type=ParameterType.STRING,
                    description="File encoding",
                    required=False,
                    default="utf-8",
                ),
                SkillParameter(
                    name="create_dirs",
                    type=ParameterType.BOOLEAN,
                    description="Create parent directories if they don't exist",
                    required=False,
                    default=True,
                ),
            ],
            returns={"success": "boolean", "path": "string", "bytes_written": "integer"},
            implementation='''
async def main(inputs, context):
    path = inputs["path"]
    content = inputs["content"]
    encoding = inputs.get("encoding", "utf-8")
    create_dirs = inputs.get("create_dirs", True)
    
    fw = context.get("framework")
    if not fw:
        return {"error": "Framework not available"}
    
    result = await fw.execute("file.write", {
        "path": path,
        "content": content
    })
    
    if "error" in result:
        return {"error": result["error"]}
    
    return {"success": True, "path": path, "bytes_written": len(content.encode("utf-8"))}
''',
        )
    
    def _create_list_files_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.list_files",
                name="List Files",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.FILE_OPERATIONS,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="List files in a directory",
                tags={"file", "list", "directory", "builtin"},
                required_tools=["file_ops"],
            ),
            parameters=[
                SkillParameter(
                    name="path",
                    type=ParameterType.DIRECTORY_PATH,
                    description="Directory path",
                    required=False,
                    default=".",
                ),
                SkillParameter(
                    name="pattern",
                    type=ParameterType.STRING,
                    description="Glob pattern",
                    required=False,
                    default="*",
                ),
                SkillParameter(
                    name="recursive",
                    type=ParameterType.BOOLEAN,
                    description="Recurse into subdirectories",
                    required=False,
                    default=False,
                ),
                SkillParameter(
                    name="include_dirs",
                    type=ParameterType.BOOLEAN,
                    description="Include directories in results",
                    required=False,
                    default=True,
                ),
            ],
            returns={"files": "array"},
            implementation='''
async def main(inputs, context):
    path = inputs.get("path", ".")
    pattern = inputs.get("pattern", "*")
    recursive = inputs.get("recursive", False)
    include_dirs = inputs.get("include_dirs", True)
    
    fw = context.get("framework")
    if not fw:
        return {"error": "Framework not available"}
    
    if recursive:
        # Use glob with **
        full_pattern = f"**/{pattern}"
        result = await fw.execute("file.list", {"path": path, "pattern": full_pattern})
    else:
        result = await fw.execute("file.list", {"path": path, "pattern": pattern})
    
    if "error" in result:
        return {"error": result["error"]}
    
    files = result.get("files", [])
    if not include_dirs:
        files = [f for f in files if not f.get("is_dir", False)]
    
    return {"files": files, "count": len(files)}
''',
        )
    
    def _create_shell_execute_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.shell_execute",
                name="Execute Shell Command",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.SHELL_COMMANDS,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Execute a shell command",
                tags={"shell", "execute", "command", "builtin"},
                required_tools=["shell"],
                required_permissions=["shell_execute"],
            ),
            parameters=[
                SkillParameter(
                    name="command",
                    type=ParameterType.STRING,
                    description="Shell command to execute",
                    required=True,
                ),
                SkillParameter(
                    name="cwd",
                    type=ParameterType.DIRECTORY_PATH,
                    description="Working directory",
                    required=False,
                    default=".",
                ),
                SkillParameter(
                    name="timeout",
                    type=ParameterType.INTEGER,
                    description="Timeout in seconds",
                    required=False,
                    default=60,
                ),
                SkillParameter(
                    name="env",
                    type=ParameterType.OBJECT,
                    description="Environment variables",
                    required=False,
                    default={},
                ),
            ],
            returns={"stdout": "string", "stderr": "string", "returncode": "integer"},
            implementation='''
async def main(inputs, context):
    command = inputs["command"]
    cwd = inputs.get("cwd", ".")
    timeout = inputs.get("timeout", 60)
    env = inputs.get("env", {})
    
    fw = context.get("framework")
    if not fw:
        return {"error": "Framework not available"}
    
    result = await fw.execute("shell.execute", {
        "command": command,
        "cwd": cwd,
        "timeout": timeout,
        "env": env
    })
    
    if "error" in result:
        return {"error": result["error"]}
    
    return {
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", -1)
    }
''',
            examples=[
                SkillExample(
                    name="List directory",
                    description="List files using shell",
                    inputs={"command": "ls -la", "cwd": "/tmp"},
                    expected_output={"stdout": "file list...", "stderr": "", "returncode": 0},
                    explanation="Execute ls command in /tmp directory"
                ),
            ],
        )
    
    def _create_http_request_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.http_request",
                name="HTTP Request",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.WEB_API,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Make HTTP requests",
                tags={"http", "api", "request", "builtin"},
                required_tools=["httpx"],
            ),
            parameters=[
                SkillParameter(
                    name="url",
                    type=ParameterType.URL,
                    description="Request URL",
                    required=True,
                ),
                SkillParameter(
                    name="method",
                    type=ParameterType.ENUM,
                    description="HTTP method",
                    required=False,
                    default="GET",
                    enum_values=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                ),
                SkillParameter(
                    name="headers",
                    type=ParameterType.OBJECT,
                    description="Request headers",
                    required=False,
                    default={},
                ),
                SkillParameter(
                    name="body",
                    type=ParameterType.OBJECT,
                    description="Request body (for POST/PUT/PATCH)",
                    required=False,
                    default=None,
                ),
                SkillParameter(
                    name="params",
                    type=ParameterType.OBJECT,
                    description="Query parameters",
                    required=False,
                    default={},
                ),
                SkillParameter(
                    name="timeout",
                    type=ParameterType.FLOAT,
                    description="Request timeout in seconds",
                    required=False,
                    default=30.0,
                ),
            ],
            returns={"status": "integer", "headers": "object", "body": "object"},
            implementation='''
async def main(inputs, context):
    import httpx
    
    url = inputs["url"]
    method = inputs.get("method", "GET")
    headers = inputs.get("headers", {})
    body = inputs.get("body")
    params = inputs.get("params", {})
    timeout = inputs.get("timeout", 30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                params=params
            )
            
            return {
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            }
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {str(e)}"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}
''',
        )
    
    def _create_json_process_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.json_process",
                name="JSON Process",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.DATA_PROCESSING,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Process JSON data (parse, query, transform)",
                tags={"json", "data", "process", "builtin"},
            ),
            parameters=[
                SkillParameter(
                    name="operation",
                    type=ParameterType.ENUM,
                    description="Operation to perform",
                    required=True,
                    enum_values=["parse", "stringify", "query", "merge", "filter", "map", "reduce"],
                ),
                SkillParameter(
                    name="data",
                    type=ParameterType.JSON,
                    description="Input JSON data",
                    required=True,
                ),
                SkillParameter(
                    name="query",
                    type=ParameterType.STRING,
                    description="JSONPath or JMESPath query (for query operation)",
                    required=False,
                ),
                SkillParameter(
                    name="filter_expr",
                    type=ParameterType.STRING,
                    description="Filter expression (for filter operation)",
                    required=False,
                ),
                SkillParameter(
                    name="map_expr",
                    type=ParameterType.STRING,
                    description="Map expression (for map operation)",
                    required=False,
                ),
            ],
            returns={"result": "any"},
            implementation='''
async def main(inputs, context):
    import json
    from pathlib import Path
    
    operation = inputs["operation"]
    data = inputs["data"]
    
    if operation == "parse":
        if isinstance(data, str):
            return {"result": json.loads(data)}
        return {"result": data}
    
    elif operation == "stringify":
        return {"result": json.dumps(data, indent=2)}
    
    elif operation == "query":
        query = inputs.get("query", "")
        try:
            import jmespath
            result = jmespath.search(query, data)
            return {"result": result}
        except ImportError:
            return {"error": "jmespath not installed"}
    
    elif operation == "filter":
        filter_expr = inputs.get("filter_expr", "")
        if isinstance(data, list):
            filtered = [item for item in data if eval(filter_expr, {"item": item, "data": data})]
            return {"result": filtered}
        return {"error": "Filter requires array input"}
    
    elif operation == "map":
        map_expr = inputs.get("map_expr", "")
        if isinstance(data, list):
            mapped = [eval(map_expr, {"item": item, "data": data}) for item in data]
            return {"result": mapped}
        return {"error": "Map requires array input"}
    
    elif operation == "reduce":
        reduce_expr = inputs.get("reduce_expr", "")
        initial = inputs.get("initial")
        if isinstance(data, list):
            from functools import reduce
            result = reduce(lambda acc, item: eval(reduce_expr, {"acc": acc, "item": item, "data": data}), data, initial)
            return {"result": result}
        return {"error": "Reduce requires array input"}
    
    return {"error": f"Unknown operation: {operation}"}
''',
        )
    
    def _create_text_process_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.text_process",
                name="Text Process",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.DATA_PROCESSING,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Process text data (split, join, replace, regex, etc.)",
                tags={"text", "string", "process", "builtin"},
            ),
            parameters=[
                SkillParameter(
                    name="operation",
                    type=ParameterType.ENUM,
                    description="Operation to perform",
                    required=True,
                    enum_values=["split", "join", "replace", "regex_replace", "extract", "upper", "lower", "trim", "count", "length"],
                ),
                SkillParameter(
                    name="text",
                    type=ParameterType.STRING,
                    description="Input text",
                    required=True,
                ),
                SkillParameter(
                    name="pattern",
                    type=ParameterType.STRING,
                    description="Pattern (separator, regex, etc.)",
                    required=False,
                ),
                SkillParameter(
                    name="replacement",
                    type=ParameterType.STRING,
                    description="Replacement string",
                    required=False,
                ),
                SkillParameter(
                    name="flags",
                    type=ParameterType.STRING,
                    description="Regex flags (i, m, s, etc.)",
                    required=False,
                    default="",
                ),
            ],
            returns={"result": "any"},
            implementation='''
async def main(inputs, context):
    import re
    
    operation = inputs["operation"]
    text = inputs["text"]
    pattern = inputs.get("pattern", "")
    replacement = inputs.get("replacement", "")
    flags = inputs.get("flags", "")
    
    if operation == "split":
        sep = pattern if pattern else " "
        return {"result": text.split(sep)}
    
    elif operation == "join":
        if isinstance(text, list):
            sep = pattern if pattern else ""
            return {"result": sep.join(text)}
        return {"error": "Join requires list input"}
    
    elif operation == "replace":
        return {"result": text.replace(pattern, replacement)}
    
    elif operation == "regex_replace":
        regex_flags = 0
        if "i" in flags: flags |= re.IGNORECASE
        if "m" in flags: flags |= re.MULTILINE
        if "s" in flags: flags |= re.DOTALL
        result = re.sub(pattern, replacement, text, flags=flags)
        return {"result": result}
    
    elif operation == "extract":
        matches = re.findall(pattern, text)
        return {"result": matches}
    
    elif operation == "upper":
        return {"result": text.upper()}
    
    elif operation == "lower":
        return {"result": text.lower()}
    
    elif operation == "trim":
        return {"result": text.strip()}
    
    elif operation == "count":
        if pattern:
            return {"result": len(re.findall(pattern, text))}
        return {"result": len(text)}
    
    elif operation == "length":
        return {"result": len(text)}
    
    return {"error": f"Unknown operation: {operation}"}
''',
        )
    
    def _create_code_analysis_skill(self) -> Skill:
        return Skill(
            metadata=SkillMetadata(
                id="builtin.code_analysis",
                name="Code Analysis",
                version="1.0.0",
                type=SkillType.BUILTIN,
                category=SkillCategory.CODE_GENERATION,
                author="framework",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                description="Analyze code for complexity, issues, metrics",
                tags={"code", "analysis", "ast", "builtin"},
            ),
            parameters=[
                SkillParameter(
                    name="code",
                    type=ParameterType.STRING,
                    description="Source code to analyze",
                    required=True,
                ),
                SkillParameter(
                    name="language",
                    type=ParameterType.ENUM,
                    description="Programming language",
                    required=False,
                    default="python",
                    enum_values=["python", "javascript", "typescript", "rust", "go"],
                ),
                SkillParameter(
                    name="checks",
                    type=ParameterType.ARRAY,
                    description="Analysis checks to run",
                    required=False,
                    default=["complexity", "imports", "functions", "classes"],
                ),
            ],
            returns={"analysis": "object"},
            implementation='''
async def main(inputs, context):
    import ast
    
    code = inputs["code"]
    language = inputs.get("language", "python")
    checks = inputs.get("checks", ["complexity", "imports", "functions", "classes"])
    
    if language != "python":
        return {"error": f"Language {language} not supported yet"}
    
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}
    
    result = {}
    
    if "imports" in checks:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        result["imports"] = imports
    
    if "functions" in checks:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": [a.arg for a in node.args.args],
                    "returns": ast.unparse(node.returns) if node.returns else None,
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                })
        result["functions"] = functions
    
    if "classes" in checks:
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "bases": [ast.unparse(b) for b in node.bases],
                    "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                })
        result["classes"] = classes
    
    if "complexity" in checks:
        # Simple cyclomatic complexity
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        result["complexity"] = complexity
    
    result["lines"] = code.count("\\n") + 1
    result["chars"] = len(code)
    
    return {"analysis": result}
''',
        )


class SkillPlugin:
    """Plugin for skills system integration."""
    
    def __init__(self, name: str, framework, data_dir: Path):
        self.name = name
        self.framework = framework
        self.data_dir = data_dir
        self.registry = SkillRegistry(data_dir)
        self.executor = SkillExecutor(framework)
        self.registry.set_executor(self.executor)
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "register_skill",
            "unregister_skill",
            "get_skill",
            "list_skills",
            "search_skills",
            "execute_skill",
            "create_skill",
            "update_skill",
            "delete_skill",
            "list_categories",
            "get_stats",
        ]
    
    async def initialize(self) -> bool:
        self.registry.set_executor(self.executor)
        self.executor.framework = self.framework
        
        self.framework.event_bus.subscribe("skill.register", self._handle_register)
        self.framework.event_bus.subscribe("skill.unregister", self._handle_unregister)
        self.framework.event_bus.subscribe("skill.get", self._handle_get)
        self.framework.event_bus.subscribe("skill.list", self._handle_list)
        self.framework.event_bus.subscribe("skill.search", self._handle_search)
        self.framework.event_bus.subscribe("skill.execute", self._handle_execute)
        self.framework.event_bus.subscribe("skill.create", self._handle_create)
        self.framework.event_bus.subscribe("skill.update", self._handle_update)
        self.framework.event_bus.subscribe("skill.delete", self._handle_delete)
        self.framework.event_bus.subscribe("skill.stats", self._handle_stats)
        self.framework.event_bus.subscribe("skill.categories", self._handle_categories)
        
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_register(self, event):
        skill_data = event.payload.get("skill")
        if not skill_data:
            await self.framework.event_bus.publish(Event("skill.register.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill data required"
            }))
            return
        
        skill = self._deserialize_skill(skill_data)
        success = self.registry.register_skill(skill)
        
        await self.framework.event_bus.publish(Event("skill.register.result", {
            "request_id": event.payload.get("request_id"),
            "success": success,
            "skill_id": skill.metadata.id if success else None
        }))
    
    async def _handle_unregister(self, event):
        skill_id = event.payload.get("skill_id")
        if not skill_id:
            await self.framework.event_bus.publish(Event("skill.unregister.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill_id required"
            }))
            return
        
        success = self.registry.unregister_skill(skill_id)
        
        await self.framework.event_bus.publish(Event("skill.unregister.result", {
            "request_id": event.payload.get("request_id"),
            "success": success
        }))
    
    async def _handle_get(self, event):
        skill_id = event.payload.get("skill_id")
        if not skill_id:
            await self.framework.event_bus.publish(Event("skill.get.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill_id required"
            }))
            return
        
        skill = self.registry.get_skill(skill_id)
        
        await self.framework.event_bus.publish(Event("skill.get.result", {
            "request_id": event.payload.get("request_id"),
            "success": skill is not None,
            "skill": self._serialize_skill(skill) if skill else None
        }))
    
    async def _handle_list(self, event):
        category = event.payload.get("category")
        skill_type = event.payload.get("type")
        tags = event.payload.get("tags")
        
        cat = SkillCategory(category) if category else None
        typ = SkillType(skill_type) if skill_type else None
        tag_set = set(tags) if tags else None
        
        skills = self.registry.list_skills(category=cat, skill_type=typ, tags=tag_set)
        
        await self.framework.event_bus.publish(Event("skill.list.result", {
            "request_id": event.payload.get("request_id"),
            "skills": [self._serialize_skill(s) for s in skills]
        }))
    
    async def _handle_search(self, event):
        query = event.payload.get("query", "")
        limit = event.payload.get("limit", 20)
        
        if not query:
            await self.framework.event_bus.publish(Event("skill.search.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "query required"
            }))
            return
        
        skills = self.registry.search_skills(query, limit)
        
        await self.framework.event_bus.publish(Event("skill.search.result", {
            "request_id": event.payload.get("request_id"),
            "skills": [self._serialize_skill(s) for s in skills]
        }))
    
    async def _handle_execute(self, event):
        skill_id = event.payload.get("skill_id")
        inputs = event.payload.get("inputs", {})
        context = event.payload.get("context", {})
        
        if not skill_id:
            await self.framework.event_bus.publish(Event("skill.execute.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill_id required"
            }))
            return
        
        skill = self.registry.get_skill(skill_id)
        if not skill:
            await self.framework.event_bus.publish(Event("skill.execute.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": f"Skill not found: {skill_id}"
            }))
            return
        
        result = await self.executor.execute(skill, inputs, context)
        
        await self.framework.event_bus.publish(Event("skill.execute.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_create(self, event):
        skill_data = event.payload.get("skill")
        if not skill_data:
            await self.framework.event_bus.publish(Event("skill.create.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill data required"
            }))
            return
        
        skill = self._deserialize_skill(skill_data)
        success = self.registry.register_skill(skill)
        
        await self.framework.event_bus.publish(Event("skill.create.result", {
            "request_id": event.payload.get("request_id"),
            "success": success,
            "skill_id": skill.metadata.id if success else None
        }))
    
    async def _handle_update(self, event):
        skill_id = event.payload.get("skill_id")
        updates = event.payload.get("updates", {})
        
        if not skill_id:
            await self.framework.event_bus.publish(Event("skill.update.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill_id required"
            }))
            return
        
        skill = self.registry.get_skill(skill_id)
        if not skill:
            await self.framework.event_bus.publish(Event("skill.update.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": f"Skill not found: {skill_id}"
            }))
            return
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(skill.metadata, key):
                setattr(skill.metadata, key, value)
            elif key == "parameters":
                skill.parameters = [SkillParameter(**p) for p in value]
            elif key == "examples":
                skill.examples = [SkillExample(**e) for e in value]
            elif key == "implementation":
                skill.implementation = value
            elif key == "implementation_type":
                skill.implementation_type = value
        
        skill.metadata.updated_at = datetime.now()
        
        success = self.registry.register_skill(skill)  # Re-register with updates
        
        await self.framework.event_bus.publish(Event("skill.update.result", {
            "request_id": event.payload.get("request_id"),
            "success": success
        }))
    
    async def _handle_delete(self, event):
        skill_id = event.payload.get("skill_id")
        if not skill_id:
            await self.framework.event_bus.publish(Event("skill.delete.result", {
                "request_id": event.payload.get("request_id"),
                "success": False,
                "error": "skill_id required"
            }))
            return
        
        success = self.registry.unregister_skill(skill_id)
        
        await self.framework.event_bus.publish(Event("skill.delete.result", {
            "request_id": event.payload.get("request_id"),
            "success": success
        }))
    
    async def _handle_stats(self, event):
        stats = self.registry.get_skill_stats()
        
        await self.framework.event_bus.publish(Event("skill.stats.result", {
            "request_id": event.payload.get("request_id"),
            "stats": stats
        }))
    
    async def _handle_categories(self, event):
        categories = [
            {"value": c.value, "name": c.name.replace("_", " ").title()}
            for c in SkillCategory
        ]
        
        await self.framework.event_bus.publish(Event("skill.categories.result", {
            "request_id": event.payload.get("request_id"),
            "categories": categories
        }))
    
    def _serialize_skill(self, skill: Skill) -> Dict[str, Any]:
        return {
            "metadata": {
                "id": skill.metadata.id,
                "name": skill.metadata.name,
                "version": skill.metadata.version,
                "type": skill.metadata.type.value,
                "category": skill.metadata.category.value,
                "author": skill.metadata.author,
                "created_at": skill.metadata.created_at.isoformat(),
                "updated_at": skill.metadata.updated_at.isoformat(),
                "description": skill.metadata.description,
                "long_description": skill.metadata.long_description,
                "tags": list(skill.metadata.tags),
                "dependencies": skill.metadata.dependencies,
                "required_tools": skill.metadata.required_tools,
                "required_permissions": skill.metadata.required_permissions,
                "is_experimental": skill.metadata.is_experimental,
                "is_deprecated": skill.metadata.is_deprecated,
                "usage_count": skill.metadata.usage_count,
                "success_rate": skill.metadata.success_rate,
                "average_latency_ms": skill.metadata.average_latency_ms,
            },
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum_values": p.enum_values,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "pattern": p.pattern,
                    "min_length": p.min_length,
                    "max_length": p.max_length,
                    "examples": p.examples,
                }
                for p in skill.parameters
            ],
            "returns": skill.returns,
            "examples": [
                {
                    "name": e.name,
                    "description": e.description,
                    "inputs": e.inputs,
                    "expected_output": e.expected_output,
                    "explanation": e.explanation,
                }
                for e in skill.examples
            ],
            "implementation": skill.implementation,
            "implementation_type": skill.implementation_type,
            "pre_conditions": skill.pre_conditions,
            "post_conditions": skill.post_conditions,
            "side_effects": skill.side_effects,
            "timeout_seconds": skill.timeout_seconds,
            "retry_policy": skill.retry_policy,
            "rate_limit": skill.rate_limit,
            "cache_ttl_seconds": skill.cache_ttl_seconds,
            "cache_key_template": skill.cache_key_template,
        }
    
    def _deserialize_skill(self, data: Dict) -> Skill:
        meta = data["metadata"]
        metadata = SkillMetadata(
            id=meta["id"],
            name=meta["name"],
            version=meta["version"],
            type=SkillType(meta["type"]),
            category=SkillCategory(meta["category"]),
            author=meta["author"],
            created_at=datetime.fromisoformat(meta["created_at"]),
            updated_at=datetime.fromisoformat(meta["updated_at"]),
            description=meta["description"],
            long_description=meta.get("long_description", ""),
            tags=set(meta.get("tags", [])),
            dependencies=meta.get("dependencies", []),
            required_tools=meta.get("required_tools", []),
            required_permissions=meta.get("required_permissions", []),
            min_framework_version=meta.get("min_framework_version", "0.1.0"),
            max_framework_version=meta.get("max_framework_version"),
            is_experimental=meta.get("is_experimental", False),
            is_deprecated=meta.get("is_deprecated", False),
            replacement_skill_id=meta.get("replacement_skill_id"),
            usage_count=meta.get("usage_count", 0),
            success_rate=meta.get("success_rate", 1.0),
            average_latency_ms=meta.get("average_latency_ms", 0.0),
        )
        
        parameters = [
            SkillParameter(
                name=p["name"],
                type=ParameterType(p["type"]),
                description=p["description"],
                required=p.get("required", True),
                default=p.get("default"),
                enum_values=p.get("enum_values"),
                min_value=p.get("min_value"),
                max_value=p.get("max_value"),
                pattern=p.get("pattern"),
                min_length=p.get("min_length"),
                max_length=p.get("max_length"),
                examples=p.get("examples", []),
            )
            for p in data.get("parameters", [])
        ]
        
        examples = [
            SkillExample(
                name=e["name"],
                description=e["description"],
                inputs=e["inputs"],
                expected_output=e["expected_output"],
                explanation=e.get("explanation", ""),
            )
            for e in data.get("examples", [])
        ]
        
        return Skill(
            metadata=metadata,
            parameters=parameters,
            returns=data.get("returns", {}),
            examples=examples,
            implementation=data.get("implementation", ""),
            implementation_type=data.get("implementation_type", "python"),
            pre_conditions=data.get("pre_conditions", []),
            post_conditions=data.get("post_conditions", []),
            side_effects=data.get("side_effects", []),
            timeout_seconds=data.get("timeout_seconds", 300),
            retry_policy=data.get("retry_policy", {}),
            rate_limit=data.get("rate_limit"),
            cache_ttl_seconds=data.get("cache_ttl_seconds"),
            cache_key_template=data.get("cache_key_template"),
        )