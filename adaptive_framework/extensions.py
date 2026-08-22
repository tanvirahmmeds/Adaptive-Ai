"""
Extension System - Dynamic plugin loading, user-defined capabilities, and growth.
"""

import importlib.util
import inspect
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type
from dataclasses import dataclass, field
import logging

from .core import Plugin, Framework, Event
from .memory import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class ExtensionManifest:
    """Manifest for an extension/plugin."""
    name: str
    version: str
    description: str
    author: str
    entry_point: str  # module:ClassName
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    auto_enable: bool = False


class ExtensionRegistry:
    """Registry for discovering and managing extensions."""
    
    def __init__(self, framework: Framework, extensions_dir: Path):
        self.framework = framework
        self.extensions_dir = Path(extensions_dir)
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        self.manifests: Dict[str, ExtensionManifest] = {}
        self.loaded_modules: Dict[str, Any] = {}
    
    def discover_extensions(self) -> List[ExtensionManifest]:
        """Scan extensions directory for manifests."""
        manifests = []
        for manifest_file in self.extensions_dir.glob("*/manifest.json"):
            try:
                with open(manifest_file) as f:
                    data = json.load(f)
                manifest = ExtensionManifest(**data)
                self.manifests[manifest.name] = manifest
                manifests.append(manifest)
            except Exception as e:
                logger.error(f"Failed to load manifest {manifest_file}: {e}")
        return manifests
    
    def load_extension(self, name: str) -> Optional[Plugin]:
        """Load an extension by name."""
        manifest = self.manifests.get(name)
        if not manifest:
            logger.error(f"Extension {name} not found in registry")
            return None
        
        # Parse entry point
        module_path, class_name = manifest.entry_point.split(":")
        module_file = self.extensions_dir / name / f"{module_path}.py"
        
        if not module_file.exists():
            logger.error(f"Module file not found: {module_file}")
            return None
        
        try:
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(module_path, module_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get plugin class
            plugin_class = getattr(module, class_name)
            
            # Verify it's a Plugin subclass
            if not issubclass(plugin_class, Plugin):
                logger.error(f"{class_name} is not a Plugin subclass")
                return None
            
            # Check dependencies
            for dep in manifest.dependencies:
                if dep not in self.framework.plugins:
                    logger.error(f"Missing dependency: {dep}")
                    return None
            
            # Instantiate plugin
            plugin = plugin_class(name, self.framework)
            plugin.configure(manifest.config_schema)
            
            self.loaded_modules[name] = module
            self.framework.register_plugin(plugin)
            
            logger.info(f"Loaded extension: {name} v{manifest.version}")
            return plugin
            
        except Exception as e:
            logger.error(f"Failed to load extension {name}: {e}")
            return None
    
    def create_extension_template(self, name: str, description: str = "") -> Path:
        """Create a new extension template."""
        ext_dir = self.extensions_dir / name
        ext_dir.mkdir(parents=True, exist_ok=True)
        
        # Manifest
        manifest = ExtensionManifest(
            name=name,
            version="0.1.0",
            description=description,
            author="user",
            entry_point=f"{name}_plugin:{name.title().replace('_', '')}Plugin",
            dependencies=[],
            config_schema={},
            auto_enable=False
        )
        with open(ext_dir / "manifest.json", "w") as f:
            json.dump(manifest.__dict__, f, indent=2)
        
        # Plugin template
        plugin_code = f'''"""
{name} - {description}
"""

from adaptive_framework.core import Plugin, Framework, Event


class {name.title().replace('_', '')}Plugin(Plugin):
    """Plugin for {name}."""
    
    @property
    def version(self) -> str:
        return "0.1.0"
    
    @property
    def capabilities(self) -> list:
        return ["{name}"]
    
    async def initialize(self) -> bool:
        # Subscribe to events
        self.framework.event_bus.subscribe("{name}.action", self._handle_action)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_action(self, event: Event):
        # Implement your capability here
        result = {{"status": "ok", "message": "Hello from {name}!"}}
        await self.framework.event_bus.publish(Event("{name}.result", {{
            "request_id": event.payload.get("request_id"),
            "result": result
        }}))


# For dynamic loading
__all__ = ["{name.title().replace('_', '')}Plugin"]
'''
        with open(ext_dir / f"{name}_plugin.py", "w") as f:
            f.write(plugin_code)
        
        # Config template
        with open(ext_dir / "config.json", "w") as f:
            json.dump({}, f, indent=2)
        
        logger.info(f"Created extension template at {ext_dir}")
        return ext_dir


class CapabilityBuilder:
    """Build new capabilities at runtime from user specifications."""
    
    def __init__(self, framework: Framework, memory: MemoryManager):
        self.framework = framework
        self.memory = memory
    
    async def create_skill_from_description(self, 
                                           name: str,
                                           description: str,
                                           examples: List[Dict[str, Any]] = None) -> str:
        """Create a new skill plugin from natural language description."""
        # This would use an LLM in practice - here's a template approach
        skill_code = f'''"""
Auto-generated skill: {name}
Description: {description}
"""

from adaptive_framework.core import Plugin, Framework, Event


class {name.title().replace(' ', '').replace('-', '')}Plugin(Plugin):
    """Auto-generated plugin for: {description}"""
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> list:
        return ["{name.lower().replace(' ', '_')}"]
    
    def __init__(self, name: str, framework: Framework):
        super().__init__(name, framework)
        self.description = "{description}"
        self.examples = {json.dumps(examples or [])}
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("{name.lower().replace(' ', '_')}.execute", self._handle_execute)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_execute(self, event: Event):
        # TODO: Implement based on description and examples
        # This is a template - user should customize
        params = event.payload.get("parameters", {{}})
        
        # Learn from this execution
        await self.framework.event_bus.publish(Event("learning.track", {{
            "data": {{
                "skill": "{name}",
                "parameters": params,
                "context": event.payload.get("context", {{}})
            }}
        }}))
        
        result = {{
            "status": "template",
            "message": f"Skill {{self.name}} executed with params: {{params}}",
            "note": "Customize this plugin to implement actual logic"
        }}
        
        await self.framework.event_bus.publish(Event("{name.lower().replace(' ', '_')}.result", {{
            "request_id": event.payload.get("request_id"),
            "result": result
        }}))
'''
        # Save as extension
        ext_dir = self.framework.data_dir / "extensions" / name.lower().replace(' ', '_')
        ext_dir.mkdir(parents=True, exist_ok=True)
        
        with open(ext_dir / f"{name.lower().replace(' ', '_')}_plugin.py", "w") as f:
            f.write(skill_code)
        
        # Create manifest
        manifest = ExtensionManifest(
            name=name.lower().replace(' ', '_'),
            version="1.0.0",
            description=description,
            author="auto-generated",
            entry_point=f"{name.lower().replace(' ', '_')}_plugin:{name.title().replace(' ', '').replace('-', '')}Plugin",
            dependencies=[],
            config_schema={},
            auto_enable=False
        )
        with open(ext_dir / "manifest.json", "w") as f:
            json.dump(manifest.__dict__, f, indent=2)
        
        return str(ext_dir)
    
    async def create_workflow_from_steps(self, 
                                        name: str,
                                        steps: List[Dict[str, Any]]) -> str:
        """Create a workflow plugin from step definitions."""
        # Each step: {"action": "plugin.capability", "parameters": {...}, "condition": "..."}
        safe_name = name.lower().replace(' ', '_')
        class_name = name.title().replace(' ', '').replace('-', '')
        
        workflow_code = f'''"""
Auto-generated workflow: {name}
"""

from adaptive_framework.core import Plugin, Framework, Event


class {class_name}WorkflowPlugin(Plugin):
    """Workflow: {name}"""
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> list:
        return ["workflow_{safe_name}"]
    
    def __init__(self, name: str, framework: Framework):
        super().__init__(name, framework)
        self.steps = {json.dumps(steps)}
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("workflow_{safe_name}.execute", self._handle_execute)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_execute(self, event: Event):
        request_id = event.payload.get("request_id")
        context = event.payload.get("context", {{}})
        results = {{}}
        
        for i, step in enumerate(self.steps):
            action = step.get("action")
            params = step.get("parameters", {{}})
            condition = step.get("condition")
            
            # Check condition
            if condition:
                # Simple condition evaluation
                try:
                    if not eval(condition, {{"context": context, "results": results}}):
                        continue
                except:
                    pass
            
            # Execute step via event bus
            step_event = Event(f"workflow.step.{{i}}", {{
                "request_id": request_id,
                "action": action,
                "parameters": params,
                "context": context
            }})
            await self.framework.event_bus.publish(step_event)
            
            # In real implementation, wait for result
            results[f"step_{{i}}"] = {{"action": action, "status": "dispatched"}}
        
        await self.framework.event_bus.publish(Event("workflow_{safe_name}.result", {{
            "request_id": request_id,
            "results": results
        }}))
'''
        ext_dir = self.framework.data_dir / "extensions" / f"workflow_{safe_name}"
        ext_dir.mkdir(parents=True, exist_ok=True)
        
        with open(ext_dir / f"workflow_{safe_name}_plugin.py", "w") as f:
            f.write(workflow_code)
        
        manifest = ExtensionManifest(
            name=f"workflow_{safe_name}",
            version="1.0.0",
            description=f"Workflow: {name}",
            author="auto-generated",
            entry_point=f"workflow_{safe_name}_plugin:{class_name}WorkflowPlugin",
            dependencies=[],
            config_schema={},
            auto_enable=False
        )
        with open(ext_dir / "manifest.json", "w") as f:
            json.dump(manifest.__dict__, f, indent=2)
        
        return str(ext_dir)


class GrowthManager:
    """Manages framework growth through user interaction."""
    
    def __init__(self, framework: Framework, memory: MemoryManager, registry: ExtensionRegistry):
        self.framework = framework
        self.memory = memory
        self.registry = registry
        self.builder = CapabilityBuilder(framework, memory)
    
    async def process_user_request(self, request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a user request, learning from it."""
        context = context or {}
        
        # Check if we have a relevant skill
        memories = await self.memory.recall(
            type="skill",
            context=context,
            tags={"capability"},
            min_confidence=0.4,
            limit=5
        )
        
        # Track the request
        await self.memory.learn_from_pattern(
            pattern_type="user_request",
            pattern_data={"request": request},
            context=context,
            confidence=0.6
        )
        
        # If no relevant skill, suggest creating one
        if not memories:
            return {
                "action": "suggest_new_capability",
                "request": request,
                "suggestion": f"No existing capability for '{request}'. Create a new skill?",
                "can_auto_create": True
            }
        
        return {
            "action": "use_existing",
            "skills": [m.content for m in memories]
        }
    
    async def auto_create_capability(self, 
                                    name: str,
                                    description: str,
                                    examples: List[Dict] = None) -> str:
        """Automatically create a new capability."""
        path = await self.builder.create_skill_from_description(name, description, examples)
        
        # Load the new extension
        ext_name = name.lower().replace(' ', '_')
        self.registry.manifests[ext_name] = ExtensionManifest(
            name=ext_name,
            version="1.0.0",
            description=description,
            author="auto-generated",
            entry_point=f"{ext_name}_plugin:{name.title().replace(' ', '').replace('-', '')}Plugin",
            dependencies=[]
        )
        
        plugin = self.registry.load_extension(ext_name)
        if plugin:
            await self.framework.enable_plugin(ext_name)
            return f"Created and enabled capability: {ext_name}"
        
        return f"Created capability at {path} but failed to load"
    
    async def evolve_from_feedback(self):
        """Evolve the framework based on accumulated feedback."""
        # Get low-confidence memories that need review
        needs_review = await self.memory.recall(tags={"needs_review"}, min_confidence=0.0)
        
        # Get frequent user corrections
        corrections = await self.memory.recall(type="correction", min_confidence=0.5)
        
        # Get common failed patterns
        failed_patterns = await self.memory.recall(
            type="pattern",
            tags={"skill_usage"},
            min_confidence=0.0
        )
        failed_patterns = [p for p in failed_patterns if not p.content.get("data", {}).get("success", True)]
        
        evolution_plan = {
            "memories_needing_review": len(needs_review),
            "user_corrections": len(corrections),
            "failed_patterns": len(failed_patterns),
            "suggestions": []
        }
        
        # Suggest new capabilities for common failed patterns
        if failed_patterns:
            skill_failures = {}
            for p in failed_patterns:
                skill = p.content.get("data", {}).get("skill", "unknown")
                skill_failures[skill] = skill_failures.get(skill, 0) + 1
            
            for skill, count in skill_failures.items():
                if count >= 3:
                    evolution_plan["suggestions"].append({
                        "type": "improve_skill",
                        "skill": skill,
                        "reason": f"Failed {count} times"
                    })
        
        # Suggest new capabilities from corrections
        for corr in corrections[:5]:
            evolution_plan["suggestions"].append({
                "type": "add_correction_handling",
                "correction": corr.content,
                "reason": "User explicitly corrected this"
            })
        
        return evolution_plan