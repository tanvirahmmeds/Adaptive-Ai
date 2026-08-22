"""
Main entry point - ties everything together.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from .core import Framework, Event
from .memory import SQLiteMemoryStore, MemoryManager, SkillMemory
from .plugins import (
    FileOperationsPlugin, 
    ShellPlugin, 
    MemoryPlugin, 
    LearningPlugin, 
    UserFeedbackPlugin
)
from .extensions import ExtensionRegistry, GrowthManager
from .mcp import MCPPlugin
from .vector_memory import create_vector_memory, VectorMemoryManager
from .agent_loop import AgentLoopPlugin
from .building_tools import BuildingTool, BuildingToolPlugin
from .skills import SkillPlugin, SkillRegistry, SkillExecutor
from .ai_providers import (
    ProviderRegistry, ProviderFactory, ModelManager, ProviderType,
    ModelInfo, ModelCapability, APIKey, CompletionRequest, CompletionResponse
)
from .device_tools import DeviceToolRegistry, DeviceInfo
from .building_tools import BuildingTool, BuildingToolPlugin, CodeFile, ProjectTemplate, BuildConfig

logger = logging.getLogger(__name__)


class AdaptiveFramework:
    """Main adaptive AI framework that grows with user needs."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path.home() / ".adaptive_framework"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Core framework
        self.framework = Framework(self.data_dir)
        
        # Memory system
        self.memory_store = SQLiteMemoryStore(self.data_dir / "memory.db")
        self.memory = MemoryManager(self.memory_store)
        self.skill_memory = SkillMemory(self.memory)
        
        # Vector memory (semantic search)
        self.vector_memory: Optional[VectorMemoryManager] = None
        
        # Extension system
        self.registry = ExtensionRegistry(self.framework, self.data_dir / "extensions")
        self.growth = GrowthManager(self.framework, self.memory, self.registry)
        
        # AI Providers
        self.provider_registry = ProviderRegistry(self.data_dir)
        self.provider_factory = ProviderFactory()
        self.model_manager = ModelManager(self.provider_registry)
        
        # Device Tools
        self.device_tools = DeviceToolRegistry()
        
        # Building Tools
        self.building_tool = BuildingTool(self.data_dir / "workspace")
        self.building_plugin: Optional[BuildingToolPlugin] = None
        
        # Skills System
        self.skill_registry = SkillRegistry(self.data_dir)
        self.skill_executor = SkillExecutor(self.framework)
        self.skill_registry.set_executor(self.skill_executor)
        
        # Agent loop
        self.agent_loop: Optional[AgentLoopPlugin] = None
        
        # Register built-in plugins
        self._register_builtin_plugins()
    
    def _register_builtin_plugins(self):
        """Register all built-in plugins."""
        plugins = [
            FileOperationsPlugin("file_ops", self.framework),
            ShellPlugin("shell", self.framework),
            MemoryPlugin("memory", self.framework, self.memory),
            LearningPlugin("learning", self.framework, self.memory),
            UserFeedbackPlugin("feedback", self.framework, self.memory),
            MCPPlugin("mcp", self.framework),
        ]
        
        for plugin in plugins:
            self.framework.register_plugin(plugin)
    
    async def start(self):
        """Start the framework."""
        # Initialize vector memory
        try:
            self.vector_memory = await create_vector_memory(self.data_dir)
            logger.info("Vector memory initialized")
        except Exception as e:
            logger.warning(f"Vector memory not available: {e}")
        
        # Initialize AI providers
        self._register_ai_providers()
        await self.model_manager.refresh_models()
        
        # Initialize agent loop
        self.agent_loop = AgentLoopPlugin("agent_loop", self.framework, self)
        self.framework.register_plugin(self.agent_loop)
        
        # Initialize building tools plugin
        self.building_plugin = BuildingToolPlugin("building", self.framework, self.data_dir / "workspace")
        self.framework.register_plugin(self.building_plugin)
        
        # Initialize skills plugin
        self.skill_plugin = SkillPlugin("skills", self.framework, self.data_dir)
        self.framework.register_plugin(self.skill_plugin)
        
        # Discover and load extensions
        self.registry.discover_extensions()
        for name in self.registry.manifests:
            if self.registry.manifests[name].auto_enable:
                self.registry.load_extension(name)
                await self.framework.enable_plugin(name)
        
        # Register built-in plugins (including new ones)
        self._register_builtin_plugins()
        
        # Enable core plugins
        await self.framework.enable_plugin("file_ops")
        await self.framework.enable_plugin("shell")
        await self.framework.enable_plugin("memory")
        await self.framework.enable_plugin("learning")
        await self.framework.enable_plugin("feedback")
        await self.framework.enable_plugin("mcp")
        await self.framework.enable_plugin("agent_loop")
        await self.framework.enable_plugin("building")
        await self.framework.enable_plugin("skills")
        
        await self.framework.start()
    
    def _register_ai_providers(self):
        """Register default AI providers."""
        # Register Ollama (local, no API key needed)
        ollama = self.provider_factory.create(ProviderType.OLLAMA)
        self.provider_registry.register_provider(ProviderType.OLLAMA, ollama)
        
        # Register Hermes provider
        hermes = self.provider_factory.create(ProviderType.HERMES)
        self.provider_registry.register_provider(ProviderType.HERMES, hermes)
        
        # Try to load saved API keys for other providers
        for key_id, api_key in self.provider_registry.api_keys.items():
            if api_key.is_active:
                provider_type = api_key.provider
                try:
                    provider = self.provider_factory.create(provider_type, api_key.key_hash)
                    self.provider_registry.register_provider(provider_type, provider)
                except Exception as e:
                    logger.warning(f"Failed to load provider {provider_type}: {e}")
        
        # Set default provider if not set
        if not self.provider_registry.default_provider:
            # Prefer local providers
            if ProviderType.OLLAMA in self.provider_registry.providers:
                self.provider_registry.set_default(ProviderType.OLLAMA)
            elif ProviderType.HERMES in self.provider_registry.providers:
                self.provider_registry.set_default(ProviderType.HERMES)
    
    async def start(self):
        """Start the framework."""
        # Initialize vector memory
        try:
            self.vector_memory = await create_vector_memory(self.data_dir)
            logger.info("Vector memory initialized")
        except Exception as e:
            logger.warning(f"Vector memory not available: {e}")
        
        # Initialize AI providers
        self._register_ai_providers()
        await self.model_manager.refresh_models()
        
        # Initialize agent loop
        self.agent_loop = AgentLoopPlugin("agent_loop", self.framework, self)
        self.framework.register_plugin(self.agent_loop)
        
        # Initialize building tools plugin
        self.building_plugin = BuildingToolPlugin("building", self.framework, self.data_dir / "workspace")
        self.framework.register_plugin(self.building_plugin)
        
        # Initialize skills plugin
        self.skill_plugin = SkillPlugin("skills", self.framework, self.data_dir)
        self.framework.register_plugin(self.skill_plugin)
        
        # Discover and load extensions
        self.registry.discover_extensions()
        for name in self.registry.manifests:
            if self.registry.manifests[name].auto_enable:
                self.registry.load_extension(name)
                await self.framework.enable_plugin(name)
        
        # Register built-in plugins (including new ones)
        self._register_builtin_plugins()
        
        # Enable core plugins
        await self.framework.enable_plugin("file_ops")
        await self.framework.enable_plugin("shell")
        await self.framework.enable_plugin("memory")
        await self.framework.enable_plugin("learning")
        await self.framework.enable_plugin("feedback")
        await self.framework.enable_plugin("mcp")
        await self.framework.enable_plugin("agent_loop")
        await self.framework.enable_plugin("building")
        await self.framework.enable_plugin("skills")
        
        await self.framework.start()
    
    async def stop(self):
        """Stop the framework."""
        await self.framework.stop()
    
    # ... (rest of the methods from the original __main__.py)
    
    # High-level API
    
    async def execute(self, action: str, parameters: dict = None, context: dict = None) -> dict:
        """Execute a capability."""
        request_id = __import__('uuid').uuid4().hex[:8]
        logger.info(f"Executing action: {action}, request_id: {request_id}")
        
        # Set up result waiting FIRST
        future = asyncio.get_event_loop().create_future()
        
        def handler(event):
            logger.info(f"Handler received event: {event.type}, request_id: {event.payload.get('request_id')}, expected: {request_id}")
            if event.payload.get("request_id") == request_id:
                logger.info(f"Setting future result for {request_id}")
                future.set_result(event.payload)
        
        result_event_type = f"{action}.result"
        self.framework.event_bus.subscribe(result_event_type, handler)
        logger.info(f"Subscribed to {result_event_type}")
        
        try:
            # NOW publish the execute event - merge parameters into payload for plugin compatibility
            payload = {
                "request_id": request_id,
            }
            if parameters:
                payload.update(parameters)
            if context:
                payload["context"] = context
                
            logger.info(f"Publishing event: {action} with payload: {payload}")
            await self.framework.event_bus.publish(Event(action, payload))
            
            # Wait for result with timeout
            logger.info(f"Waiting for result on {result_event_type}...")
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for result on {result_event_type}")
            return {"error": "Timeout waiting for result"}
        finally:
            self.framework.event_bus.unsubscribe(result_event_type, handler)
            logger.info(f"Unsubscribed from {result_event_type}")
    
    # Memory shortcuts
    
    async def remember(self, type: str, content: dict, context: dict = None, **kwargs):
        return await self.memory.remember(type, content, context, **kwargs)
    
    async def recall(self, **kwargs):
        return await self.memory.recall(**kwargs)
    
    async def feedback(self, entry_id: str, positive: bool, **kwargs):
        await self.memory.learn_from_feedback(entry_id, positive, **kwargs)
    
    async def set_preference(self, key: str, value: any, **kwargs):
        await self.memory.set_user_preference(key, value, **kwargs)
    
    async def get_preferences(self, **kwargs):
        return await self.memory.get_user_preferences(**kwargs)
    
    # Growth shortcuts
    
    async def process_request(self, request: str, context: dict = None):
        return await self.growth.process_user_request(request, context)
    
    async def create_capability(self, name: str, description: str, examples: list = None):
        return await self.growth.auto_create_capability(name, description, examples)
    
    async def evolve(self):
        return await self.growth.evolve_from_feedback()
    
    # Event publishing
    
    async def publish(self, event_type: str, payload: dict):
        await self.framework.event_bus.publish(Event(event_type, payload))
    
    def subscribe(self, event_type: str, handler):
        self.framework.event_bus.subscribe(event_type, handler)
    
    # AI Provider shortcuts
    
    def add_ai_provider(self, provider_type: ProviderType, api_key: str, name: str = "") -> APIKey:
        """Add an AI provider with API key."""
        api_key_obj = self.provider_registry.add_api_key(provider_type, api_key, name)
        provider = self.provider_factory.create(provider_type, api_key)
        self.provider_registry.register_provider(provider_type, provider)
        return api_key_obj
    
    def remove_ai_provider(self, key_id: str) -> bool:
        return self.provider_registry.remove_api_key(key_id)
    
    def list_ai_providers(self) -> Dict[str, Any]:
        return {
            "default": self.provider_registry.get_default(),
            "providers": list(self.provider_registry.providers.keys()),
            "api_keys": [
                {
                    "id": k.id,
                    "provider": k.provider.value,
                    "name": k.name,
                    "created_at": k.created_at.isoformat(),
                    "last_used": k.last_used.isoformat() if k.last_used else None,
                    "is_active": k.is_active,
                }
                for k in self.provider_registry.api_keys.values()
            ],
        }
    
    def set_default_provider(self, provider_type: ProviderType, model: str = None):
        self.provider_registry.set_default(provider_type, model)
    
    async def get_available_models(self) -> Dict[str, List[ModelInfo]]:
        return await self.provider_registry.get_available_models()
    
    async def recommend_model(self, task: str, budget: float = None, prefer_local: bool = False) -> Optional[ModelInfo]:
        return self.model_manager.recommend_model(task, budget, prefer_local)
    
    async def complete(self, model: str, messages: List[Dict[str, str]], **kwargs) -> CompletionResponse:
        """Complete using specified model."""
        model_info = self.model_manager.get_model(model)
        if not model_info:
            return CompletionResponse(
                id="",
                model=model,
                choices=[],
                usage={},
                created=0,
                provider=ProviderType.CUSTOM,
                latency_ms=0,
            )
        
        provider = self.provider_registry.get_provider(model_info.provider)
        if not provider:
            raise ValueError(f"Provider not available: {model_info.provider}")
        
        request = CompletionRequest(
            model=model,
            messages=messages,
            **kwargs
        )
        return await provider.complete(request)
    
    async def stream_complete(self, model: str, messages: List[Dict[str, str]], **kwargs):
        """Stream completion from model."""
        model_info = self.model_manager.get_model(model)
        if not model_info:
            yield {"error": "Model not found"}
            return
        
        provider = self.provider_registry.get_provider(model_info.provider)
        if not provider:
            raise ValueError(f"Provider not available: {model_info.provider}")
        
        request = CompletionRequest(
            model=model,
            messages=messages,
            stream=True,
        )
        async for chunk in provider.stream_complete(request):
            yield chunk
    
    # Device Tool shortcuts
    
    async def device_execute(self, tool_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a device tool action."""
        return await self.device_tools.execute(tool_name, action, params)
    
    def list_device_tools(self) -> Dict[str, Dict[str, Any]]:
        return self.device_tools.list_tools()
    
    async def get_device_info(self) -> DeviceInfo:
        return await self.device_tools.get_device_info()
    
    # Building Tool shortcuts
    
    async def create_project(self, template: str, project_name: str, destination: str = ".", variables: Dict[str, str] = None) -> Dict[str, Any]:
        return await self.building_tool.create_project(template, project_name, Path(destination), variables)
    
    async def build_project(self, config: str = "python", args: str = "", working_dir: str = None) -> Dict[str, Any]:
        return await self.building_tool.build(config, args, Path(working_dir) if working_dir else None)
    
    async def test_project(self, config: str = "python", args: str = "", working_dir: str = None) -> Dict[str, Any]:
        return await self.building_tool.test(config, args, Path(working_dir) if working_dir else None)
    
    async def lint_project(self, config: str = "python", args: str = "", working_dir: str = None) -> Dict[str, Any]:
        return await self.building_tool.lint(config, args, Path(working_dir) if working_dir else None)
    
    async def format_project(self, config: str = "python", args: str = "", working_dir: str = None) -> Dict[str, Any]:
        return await self.building_tool.format_code(config, args, Path(working_dir) if working_dir else None)
    
    def list_templates(self) -> Dict[str, Dict[str, Any]]:
        return self.building_tool.list_templates()
    
    async def analyze_code_file(self, file_path: str) -> CodeFile:
        return await self.building_tool.analyze_code(Path(file_path))
    
    async def generate_code(self, specification: str, language: str, framework: str = None) -> Dict[str, Any]:
        return await self.building_tool.generate_code(specification, language, framework)
    
    # Skill shortcuts
    
    async def register_skill(self, skill_data: Dict) -> bool:
        """Register a new skill."""
        skill = self.skill_plugin._deserialize_skill(skill_data)
        return self.skill_registry.register_skill(skill)
    
    async def execute_skill(self, skill_id: str, inputs: Dict[str, Any], context: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Execute a skill."""
        skill = self.skill_registry.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": f"Skill not found: {skill_id}"}
        
        return await self.skill_executor.execute(skill, inputs, context)
    
    def list_skills(self, category: str = None, skill_type: str = None, tags: List[str] = None) -> List[Dict]:
        """List skills with optional filtering."""
        cat = SkillCategory(category) if category else None
        typ = SkillType(skill_type) if skill_type else None
        tag_set = set(tags) if tags else None
        
        skills = self.skill_registry.list_skills(category=cat, skill_type=typ, tags=tag_set)
        return [self._serialize_skill(s) for s in skills]
    
    def search_skills(self, query: str, limit: int = 20) -> List[Dict]:
        """Search skills by query."""
        skills = self.skill_registry.search_skills(query, limit)
        return [self._serialize_skill(s) for s in skills]
    
    def get_skill_stats(self) -> Dict[str, Any]:
        return self.skill_registry.get_skill_stats()
    
    def _serialize_skill(self, skill) -> Dict[str, Any]:
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
    
    # Event publishing
    
    async def publish(self, event_type: str, payload: dict):
        await self.framework.event_bus.publish(Event(event_type, payload))
    
    def subscribe(self, event_type: str, handler):
        self.framework.event_bus.subscribe(event_type, handler)


# Convenience function
async def create_framework(data_dir: str = None) -> AdaptiveFramework:
    """Create and start a framework instance."""
    fw = AdaptiveFramework(data_dir)
    await fw.start()
    return fw