"""
my_custom_tool - A custom tool for specific tasks
"""

from adaptive_framework.core import Plugin, Framework, Event


class MyCustomToolPlugin(Plugin):
    """Plugin for my_custom_tool."""
    
    @property
    def version(self) -> str:
        return "0.1.0"
    
    @property
    def capabilities(self) -> list:
        return ["my_custom_tool"]
    
    async def initialize(self) -> bool:
        # Subscribe to events
        self.framework.event_bus.subscribe("my_custom_tool.action", self._handle_action)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_action(self, event: Event):
        # Implement your capability here
        result = {"status": "ok", "message": "Hello from my_custom_tool!"}
        await self.framework.event_bus.publish(Event("my_custom_tool.result", {
            "request_id": event.payload.get("request_id"),
            "result": result
        }))


# For dynamic loading
__all__ = ["MyCustomToolPlugin"]
