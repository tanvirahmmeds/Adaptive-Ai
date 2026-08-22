"""
Device Tools - Access to device capabilities (sensors, camera, clipboard, notifications, etc.)
"""

import asyncio
import base64
import json
import os
import platform
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Device information."""
    platform: str
    version: str
    device_name: str
    architecture: str
    memory_total: int
    memory_available: int
    storage_total: int
    storage_available: int
    battery_level: Optional[float] = None
    battery_charging: Optional[bool] = None
    network_type: Optional[str] = None
    screen_size: Optional[tuple] = None
    dpi: Optional[int] = None
    sensors: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class SensorReading:
    """Sensor reading data."""
    sensor_type: str
    value: Any
    unit: str
    timestamp: datetime
    accuracy: Optional[float] = None


@dataclass
class Notification:
    """Notification data."""
    title: str
    body: str
    icon: Optional[str] = None
    actions: List[Dict[str, str]] = field(default_factory=list)
    priority: str = "normal"  # low, normal, high, urgent
    category: Optional[str] = None
    sound: Optional[str] = None
    vibration: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeviceTool(ABC):
    """Abstract device tool."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
    
    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        pass


class ClipboardTool(DeviceTool):
    """Clipboard access tool."""
    
    @property
    def name(self) -> str:
        return "clipboard"
    
    @property
    def description(self) -> str:
        return "Read and write clipboard content"
    
    @property
    def capabilities(self) -> List[str]:
        return ["read_text", "write_text", "read_image", "write_image", "clear"]
    
    async def is_available(self) -> bool:
        return True  # Most platforms have clipboard
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "read_text":
            return await self._read_text()
        elif action == "write_text":
            return await self._write_text(params.get("text", ""))
        elif action == "clear":
            return await self._clear()
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _read_text(self) -> Dict[str, Any]:
        try:
            system = platform.system().lower()
            if system == "darwin":  # macOS
                result = subprocess.run(["pbpaste"], capture_output=True, text=True)
                return {"success": True, "text": result.stdout}
            elif system == "linux":
                # Try xclip, xsel, wl-paste
                for cmd in [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b"]]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                        if result.returncode == 0:
                            return {"success": True, "text": result.stdout}
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
                return {"success": False, "error": "No clipboard tool found"}
            elif system == "windows":
                import ctypes
                ctypes.windll.user32.OpenClipboard(0)
                data = ctypes.windll.user32.GetClipboardData(1)  # CF_TEXT
                ctypes.windll.user32.CloseClipboard()
                if data:
                    return {"success": True, "text": ctypes.c_char_p(data).value.decode()}
                return {"success": False, "error": "No text in clipboard"}
            else:
                return {"success": False, "error": f"Unsupported platform: {system}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _write_text(self, text: str) -> Dict[str, Any]:
        try:
            system = platform.system().lower()
            if system == "darwin":
                subprocess.run(["pbcopy"], input=text.encode(), check=True)
                return {"success": True}
            elif system == "linux":
                for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]]:
                    try:
                        subprocess.run(cmd, input=text.encode(), check=True, timeout=2)
                        return {"success": True}
                    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        continue
                return {"success": False, "error": "No clipboard tool found"}
            elif system == "windows":
                import ctypes
                ctypes.windll.user32.OpenClipboard(0)
                ctypes.windll.user32.EmptyClipboard()
                hglobal = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(text) + 1)
                ctypes.memmove(hglobal, text.encode() + b'\0', len(text) + 1)
                ctypes.windll.user32.SetClipboardData(1, hglobal)
                ctypes.windll.user32.CloseClipboard()
                return {"success": True}
            else:
                return {"success": False, "error": f"Unsupported platform: {system}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _clear(self) -> Dict[str, Any]:
        return await self._write_text("")


class NotificationTool(DeviceTool):
    """System notification tool."""
    
    @property
    def name(self) -> str:
        return "notification"
    
    @property
    def description(self) -> str:
        return "Send system notifications"
    
    @property
    def capabilities(self) -> List[str]:
        return ["send", "schedule", "cancel", "list"]
    
    async def is_available(self) -> bool:
        system = platform.system().lower()
        if system == "darwin":
            return True
        elif system == "linux":
            # Check for notify-send, kdialog, zenity
            for cmd in ["notify-send", "kdialog", "zenity"]:
                try:
                    subprocess.run(["which", cmd], capture_output=True)
                    return True
                except:
                    continue
        elif system == "windows":
            return True
        return False
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "send":
            return await self._send(params)
        elif action == "schedule":
            return await self._schedule(params)
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        notification = Notification(
            title=params.get("title", "Notification"),
            body=params.get("body", ""),
            icon=params.get("icon"),
            priority=params.get("priority", "normal"),
            sound=params.get("sound"),
            vibration=params.get("vibration", False),
        )
        
        try:
            system = platform.system().lower()
            if system == "darwin":
                script = f'display notification "{notification.body}" with title "{notification.title}"'
                if notification.sound:
                    script += f' sound name "{notification.sound}"'
                subprocess.run(["osascript", "-e", script], check=True)
            elif system == "linux":
                cmd = ["notify-send", notification.title, notification.body]
                if notification.icon:
                    cmd.extend(["-i", notification.icon])
                if notification.priority == "low":
                    cmd.extend(["-u", "low"])
                elif notification.priority == "high":
                    cmd.extend(["-u", "critical"])
                subprocess.run(cmd, check=True)
            elif system == "windows":
                # Use PowerShell for Windows notifications
                ps_script = f"""
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
                $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
                $text = $xml.GetElementsByTagName("text")
                $text[0].AppendChild($xml.CreateTextNode("{notification.title}")) | Out-Null
                $text[1].AppendChild($xml.CreateTextNode("{notification.body}")) | Out-Null
                $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Adaptive Framework").Show($toast)
                """
                subprocess.run(["powershell", "-Command", ps_script], check=True)
            else:
                return {"success": False, "error": f"Unsupported platform: {system}"}
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _schedule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Would need a scheduler - simplified
        return {"success": False, "error": "Scheduling not implemented yet"}


class CameraTool(DeviceTool):
    """Camera access tool."""
    
    @property
    def name(self) -> str:
        return "camera"
    
    @property
    def description(self) -> str:
        return "Capture photos and videos"
    
    @property
    def capabilities(self) -> List[str]:
        return ["capture_photo", "capture_video", "list_devices", "scan_qr"]
    
    async def is_available(self) -> bool:
        # Check for camera access
        return True  # Most devices have cameras
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "capture_photo":
            return await self._capture_photo(params)
        elif action == "scan_qr":
            return await self._scan_qr(params)
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _capture_photo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            output_path = params.get("output_path", tempfile.mktemp(suffix=".jpg"))
            system = platform.system().lower()
            
            if system == "darwin":
                subprocess.run(["imagesnap", "-q", output_path], check=True)
            elif system == "linux":
                subprocess.run(["fswebcam", "-r", "1280x720", "--no-banner", output_path], check=True)
            elif system == "windows":
                # Use PowerShell
                ps = f"""
                Add-Type -AssemblyName System.Drawing
                $camera = New-Object System.Drawing.Bitmap(640, 480)
                $graphics = [System.Drawing.Graphics]::FromImage($camera)
                $graphics.CopyFromScreen(0, 0, 0, 0, $camera.Size)
                $camera.Save("{output_path}", [System.Drawing.Imaging.ImageFormat]::Jpeg)
                """
                subprocess.run(["powershell", "-Command", ps], check=True)
            else:
                return {"success": False, "error": f"Unsupported platform: {system}"}
            
            # Read and encode as base64
            with open(output_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            return {"success": True, "path": output_path, "base64": image_data}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _scan_qr(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Would use a QR code library
        return {"success": False, "error": "QR scanning not implemented yet"}


class SensorTool(DeviceTool):
    """Sensor access tool (accelerometer, gyroscope, GPS, etc.)"""
    
    @property
    def name(self) -> str:
        return "sensor"
    
    @property
    def description(self) -> str:
        return "Access device sensors (accelerometer, gyroscope, GPS, etc.)"
    
    @property
    def capabilities(self) -> List[str]:
        return ["get_accelerometer", "get_gyroscope", "get_gps", "get_compass", "list_sensors"]
    
    async def is_available(self) -> bool:
        return True
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Simplified - would use platform-specific APIs
        return {"success": False, "error": "Sensor access requires platform-specific implementation"}


class FileSystemTool(DeviceTool):
    """Extended file system access with device-specific paths."""
    
    @property
    def name(self) -> str:
        return "filesystem"
    
    @property
    def description(self) -> str:
        return "Access device file system with platform-specific paths"
    
    @property
    def capabilities(self) -> List[str]:
        return ["get_special_paths", "open_file", "share_file", "pick_file", "pick_folder"]
    
    async def is_available(self) -> bool:
        return True
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "get_special_paths":
            return await self._get_special_paths()
        elif action == "open_file":
            return await self._open_file(params.get("path", ""))
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _get_special_paths(self) -> Dict[str, Any]:
        system = platform.system().lower()
        home = Path.home()
        
        paths = {
            "home": str(home),
            "desktop": str(home / "Desktop"),
            "documents": str(home / "Documents"),
            "downloads": str(home / "Downloads"),
            "pictures": str(home / "Pictures"),
            "music": str(home / "Music"),
            "videos": str(home / "Videos"),
        }
        
        if system == "darwin":
            paths.update({
                "applications": "/Applications",
                "library": str(home / "Library"),
            })
        elif system == "windows":
            paths.update({
                "appdata": os.environ.get("APPDATA", ""),
                "localappdata": os.environ.get("LOCALAPPDATA", ""),
            })
        elif system == "linux":
            paths.update({
                "config": os.environ.get("XDG_CONFIG_HOME", str(home / ".config")),
                "data": os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share")),
                "cache": os.environ.get("XDG_CACHE_HOME", str(home / ".cache")),
            })
        
        return {"success": True, "paths": paths}
    
    async def _open_file(self, path: str) -> Dict[str, Any]:
        try:
            system = platform.system().lower()
            if system == "darwin":
                subprocess.run(["open", path], check=True)
            elif system == "linux":
                subprocess.run(["xdg-open", path], check=True)
            elif system == "windows":
                subprocess.run(["start", "", path], shell=True, check=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


class NetworkTool(DeviceTool):
    """Network information and control."""
    
    @property
    def name(self) -> str:
        return "network"
    
    @property
    def description(self) -> str:
        return "Network information and control"
    
    @property
    def capabilities(self) -> List[str]:
        return ["get_info", "ping", "scan_wifi", "get_ip", "speed_test"]
    
    async def is_available(self) -> bool:
        return True
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "get_info":
            return await self._get_info()
        elif action == "ping":
            return await self._ping(params.get("host", "8.8.8.8"))
        elif action == "get_ip":
            return await self._get_ip()
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _get_info(self) -> Dict[str, Any]:
        try:
            import socket
            import psutil
            
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            interfaces = {}
            for interface, addrs in psutil.net_if_addrs().items():
                interfaces[interface] = [{"family": str(addr.family), "address": addr.address} for addr in addrs]
            
            stats = psutil.net_io_counters()
            
            return {
                "success": True,
                "hostname": hostname,
                "local_ip": local_ip,
                "interfaces": interfaces,
                "bytes_sent": stats.bytes_sent,
                "bytes_recv": stats.bytes_recv,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _ping(self, host: str) -> Dict[str, Any]:
        try:
            system = platform.system().lower()
            if system == "windows":
                cmd = ["ping", "-n", "4", host]
            else:
                cmd = ["ping", "-c", "4", host]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_ip(self) -> Dict[str, Any]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://api.ipify.org?format=json")
                return {"success": True, "ip": response.json().get("ip")}
        except Exception as e:
            return {"success": False, "error": str(e)}


class BatteryTool(DeviceTool):
    """Battery information."""
    
    @property
    def name(self) -> str:
        return "battery"
    
    @property
    def description(self) -> str:
        return "Battery level and charging status"
    
    @property
    def capabilities(self) -> List[str]:
        return ["get_status", "monitor"]
    
    async def is_available(self) -> bool:
        try:
            import psutil
            return psutil.sensors_battery() is not None
        except:
            return False
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "get_status":
            return await self._get_status()
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _get_status(self) -> Dict[str, Any]:
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "success": True,
                    "percent": battery.percent,
                    "charging": battery.power_plugged,
                    "time_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                }
            return {"success": False, "error": "No battery found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ProcessTool(DeviceTool):
    """Process and system monitoring."""
    
    @property
    def name(self) -> str:
        return "process"
    
    @property
    def description(self) -> str:
        return "Process management and system monitoring"
    
    @property
    def capabilities(self) -> List[str]:
        return ["list_processes", "get_process_info", "kill_process", "get_system_stats"]
    
    async def is_available(self) -> bool:
        return True
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "list_processes":
            return await self._list_processes(params.get("limit", 20))
        elif action == "get_system_stats":
            return await self._get_system_stats()
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _list_processes(self, limit: int = 20) -> Dict[str, Any]:
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU usage
            processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
            return {"success": True, "processes": processes[:limit]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_system_stats(self) -> Dict[str, Any]:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "success": True,
                "cpu_percent": cpu,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": (disk.total - disk.free) / disk.total * 100,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class DeviceToolRegistry:
    """Registry for device tools."""
    
    def __init__(self):
        self.tools: Dict[str, DeviceTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register all default device tools."""
        tools = [
            ClipboardTool(),
            NotificationTool(),
            CameraTool(),
            SensorTool(),
            FileSystemTool(),
            NetworkTool(),
            BatteryTool(),
            ProcessTool(),
        ]
        
        for tool in tools:
            self.register_tool(tool)
    
    def register_tool(self, tool: DeviceTool):
        self.tools[tool.name] = tool
        logger.info(f"Registered device tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[DeviceTool]:
        return self.tools.get(name)
    
    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "capabilities": tool.capabilities,
            }
            for name, tool in self.tools.items()
        }
    
    async def get_device_info(self) -> DeviceInfo:
        """Get comprehensive device information."""
        import psutil
        
        system = platform.system()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()
        
        info = DeviceInfo(
            platform=platform.system(),
            version=platform.version(),
            device_name=platform.node(),
            architecture=platform.machine(),
            memory_total=memory.total,
            memory_available=memory.available,
            storage_total=disk.total,
            storage_available=disk.free,
        )
        
        if battery:
            info.battery_level = battery.percent
            info.battery_charging = battery.power_plugged
        
        return info
    
    async def execute(self, tool_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a device tool action."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {tool_name}"}
        
        if not await tool.is_available():
            return {"success": False, "error": f"Tool not available: {tool_name}"}
        
        try:
            return await tool.execute(action, params)
        except Exception as e:
            logger.error(f"Device tool {tool_name}.{action} failed: {e}")
            return {"success": False, "error": str(e)}