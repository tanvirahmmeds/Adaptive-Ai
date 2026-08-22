"""
Core framework - plugin architecture, event bus, and lifecycle management.
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Event in the system."""
    type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class EventBus:
    """Simple pub/sub event bus for decoupled communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: Callable):
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)
    
    async def publish(self, event: Event):
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.type}: {e}")


class Plugin(ABC):
    """Base class for all plugins."""
    
    def __init__(self, name: str, framework: 'Framework'):
        self.name = name
        self.framework = framework
        self.enabled = False
        self._config: Dict[str, Any] = {}
    
    @property
    @abstractmethod
    def version(self) -> str:
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """What this plugin can do."""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin. Return True if successful."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Cleanup on shutdown."""
        pass
    
    def configure(self, config: Dict[str, Any]):
        self._config = config
    
    def get_config(self, key: str, default=None):
        return self._config.get(key, default)


class Framework:
    """Main framework orchestrating plugins, memory, and learning."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.plugins: Dict[str, Plugin] = {}
        self.event_bus = EventBus()
        self.running = False
        self._startup_tasks: List[Callable] = []
        self._shutdown_tasks: List[Callable] = []
    
    def register_plugin(self, plugin: Plugin):
        """Register a plugin."""
        if plugin.name in self.plugins:
            logger.warning(f"Plugin {plugin.name} already registered, replacing")
        self.plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
    
    async def enable_plugin(self, name: str) -> bool:
        """Enable a plugin."""
        plugin = self.plugins.get(name)
        if not plugin:
            logger.error(f"Plugin {name} not found")
            return False
        
        if plugin.enabled:
            logger.warning(f"Plugin {name} already enabled")
            return True
        
        success = await plugin.initialize()
        if success:
            plugin.enabled = True
            await self.event_bus.publish(Event("plugin.enabled", {"plugin": name}))
            logger.info(f"Enabled plugin: {name}")
        else:
            logger.error(f"Failed to initialize plugin: {name}")
        return success
    
    async def disable_plugin(self, name: str):
        """Disable a plugin."""
        plugin = self.plugins.get(name)
        if not plugin or not plugin.enabled:
            return
        
        await plugin.shutdown()
        plugin.enabled = False
        await self.event_bus.publish(Event("plugin.disabled", {"plugin": name}))
        logger.info(f"Disabled plugin: {name}")
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self.plugins.get(name)
    
    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "version": p.version,
                "capabilities": p.capabilities,
                "enabled": p.enabled
            }
            for name, p in self.plugins.items()
        }
    
    def on_startup(self, func: Callable):
        self._startup_tasks.append(func)
    
    def on_shutdown(self, func: Callable):
        self._shutdown_tasks.append(func)
    
    async def start(self):
        """Start the framework."""
        self.running = True
        await self.event_bus.publish(Event("framework.starting", {}))
        
        for task in self._startup_tasks:
            try:
                if asyncio.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Startup task failed: {e}")
        
        await self.event_bus.publish(Event("framework.started", {}))
        logger.info("Framework started")
    
    async def stop(self):
        """Stop the framework."""
        await self.event_bus.publish(Event("framework.stopping", {}))
        
        for task in self._shutdown_tasks:
            try:
                if asyncio.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Shutdown task failed: {e}")
        
        for name in list(self.plugins.keys()):
            await self.disable_plugin(name)
        
        self.running = False
        await self.event_bus.publish(Event("framework.stopped", {}))
        logger.info("Framework stopped")