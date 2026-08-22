"""
AI Provider System - Multi-provider support with API key management and model validation.
"""

import asyncio
import json
import os
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union
import logging

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported AI provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    MISTRAL = "mistral"
    GROQ = "groq"
    TOGETHER = "together"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"
    HERMES = "hermes"  # Hermes built-in


class ModelCapability(Enum):
    """Model capabilities."""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"


@dataclass
class ModelInfo:
    """Information about a model."""
    id: str
    name: str
    provider: ProviderType
    capabilities: Set[ModelCapability] = field(default_factory=set)
    context_window: int = 4096
    max_output_tokens: int = 2048
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    is_local: bool = False
    requires_api_key: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKey:
    """API key with metadata."""
    id: str
    provider: ProviderType
    key_hash: str  # Stored as hash for security
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True
    rate_limit: Optional[int] = None  # requests per minute
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionRequest:
    """Request for model completion."""
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None
    stream: bool = False
    response_format: Optional[Dict] = None
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None
    user: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Response from model completion."""
    id: str
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    created: int
    provider: ProviderType
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        self.api_key = api_key
        self.config = config or {}
        self._models_cache: Optional[List[ModelInfo]] = None
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        pass
    
    @property
    @abstractmethod
    def default_base_url(self) -> str:
        pass
    
    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        pass
    
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        pass
    
    @abstractmethod
    async def stream_complete(self, request: CompletionRequest) -> AsyncGenerator[Dict[str, Any], None]:
        pass
    
    @abstractmethod
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        pass
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        pass
    
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model info by ID."""
        if self._models_cache is None:
            # This would be async in practice, but we keep it simple
            return None
        for model in self._models_cache:
            if model.id == model_id:
                return model
        return None


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI
    
    @property
    def default_base_url(self) -> str:
        return "https://api.openai.com/v1"
    
    async def list_models(self) -> List[ModelInfo]:
        # Return known models - in production would fetch from API
        return [
            ModelInfo(
                id="gpt-4o",
                name="GPT-4o",
                provider=ProviderType.OPENAI,
                capabilities={ModelCapability.CHAT, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING, ModelCapability.JSON_MODE},
                context_window=128000,
                max_output_tokens=4096,
                cost_per_1k_input=0.005,
                cost_per_1k_output=0.015,
            ),
            ModelInfo(
                id="gpt-4o-mini",
                name="GPT-4o Mini",
                provider=ProviderType.OPENAI,
                capabilities={ModelCapability.CHAT, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING, ModelCapability.JSON_MODE},
                context_window=128000,
                max_output_tokens=16384,
                cost_per_1k_input=0.00015,
                cost_per_1k_output=0.0006,
            ),
            ModelInfo(
                id="gpt-4-turbo",
                name="GPT-4 Turbo",
                provider=ProviderType.OPENAI,
                capabilities={ModelCapability.CHAT, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING, ModelCapability.JSON_MODE},
                context_window=128000,
                max_output_tokens=4096,
                cost_per_1k_input=0.01,
                cost_per_1k_output=0.03,
            ),
            ModelInfo(
                id="gpt-3.5-turbo",
                name="GPT-3.5 Turbo",
                provider=ProviderType.OPENAI,
                capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING, ModelCapability.JSON_MODE},
                context_window=16384,
                max_output_tokens=4096,
                cost_per_1k_input=0.0005,
                cost_per_1k_output=0.0015,
            ),
            ModelInfo(
                id="text-embedding-3-small",
                name="Text Embedding 3 Small",
                provider=ProviderType.OPENAI,
                capabilities={ModelCapability.EMBEDDING},
                context_window=8191,
                cost_per_1k_input=0.00002,
            ),
            ModelInfo(
                id="text-embedding-3-large",
                name="Text Embedding 3 Large",
                provider=ProviderType.OPENAI,
                capabilities={ModelCapability.EMBEDDING},
                context_window=8191,
                cost_per_1k_input=0.00013,
            ),
        ]
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import httpx
        start_time = asyncio.get_event_loop().time()
        
        base_url = self.config.get("base_url", self.default_base_url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stream": request.stream,
        }
        
        if request.stop:
            payload["stop"] = request.stop
        if request.response_format:
            payload["response_format"] = request.response_format
        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = request.tool_choice or "auto"
        if request.user:
            payload["user"] = request.user
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", request.model),
            choices=data.get("choices", []),
            usage=data.get("usage", {}),
            created=data.get("created", int(datetime.now().timestamp())),
            provider=ProviderType.OPENAI,
            latency_ms=latency_ms,
        )
    
    async def stream_complete(self, request: CompletionRequest) -> AsyncGenerator[Dict[str, Any], None]:
        import httpx
        base_url = self.config.get("base_url", self.default_base_url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stream": True,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", f"{base_url}/chat/completions", headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            yield json.loads(data_str)
                        except json.JSONDecodeError:
                            pass
    
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        import httpx
        base_url = self.config.get("base_url", self.default_base_url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/embeddings",
                headers=headers,
                json={"model": model, "input": texts}
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
    
    async def validate_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception as e:
            logger.error(f"OpenAI connection validation failed: {e}")
            return False


class AnthropicProvider(AIProvider):
    """Anthropic API provider."""
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC
    
    @property
    def default_base_url(self) -> str:
        return "https://api.anthropic.com/v1"
    
    async def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(
                id="claude-3-5-sonnet-20241022",
                name="Claude 3.5 Sonnet",
                provider=ProviderType.ANTHROPIC,
                capabilities={ModelCapability.CHAT, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING},
                context_window=200000,
                max_output_tokens=8192,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
            ),
            ModelInfo(
                id="claude-3-5-haiku-20241022",
                name="Claude 3.5 Haiku",
                provider=ProviderType.ANTHROPIC,
                capabilities={ModelCapability.CHAT, ModelCapability.VISION, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING},
                context_window=200000,
                max_output_tokens=8192,
                cost_per_1k_input=0.0008,
                cost_per_1k_output=0.004,
            ),
            ModelInfo(
                id="claude-3-opus-20240229",
                name="Claude 3 Opus",
                provider=ProviderType.ANTHROPIC,
                capabilities={ModelCapability.CHAT, ModelCapability.VISION, ModelCapability.STREAMING},
                context_window=200000,
                max_output_tokens=4096,
                cost_per_1k_input=0.015,
                cost_per_1k_output=0.075,
            ),
        ]
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import httpx
        start_time = asyncio.get_event_loop().time()
        
        base_url = self.config.get("base_url", self.default_base_url)
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        # Convert messages format
        system_message = None
        messages = []
        for msg in request.messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                messages.append(msg)
        
        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream,
        }
        
        if system_message:
            payload["system"] = system_message
        if request.stop:
            payload["stop_sequences"] = request.stop
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", request.model),
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": data.get("content", [{}])[0].get("text", "")},
                "finish_reason": data.get("stop_reason", "stop")
            }],
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
            },
            created=int(datetime.now().timestamp()),
            provider=ProviderType.ANTHROPIC,
            latency_ms=latency_ms,
        )
    
    async def stream_complete(self, request: CompletionRequest) -> AsyncGenerator[Dict[str, Any], None]:
        # Simplified - would need full implementation
        yield {"type": "text", "text": "Streaming not fully implemented for Anthropic"}
    
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # Anthropic doesn't have embeddings API
        raise NotImplementedError("Anthropic doesn't provide embeddings API")
    
    async def validate_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False


class OllamaProvider(AIProvider):
    """Ollama local provider."""
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OLLAMA
    
    @property
    def default_base_url(self) -> str:
        return "http://localhost:11434"
    
    async def list_models(self) -> List[ModelInfo]:
        import httpx
        base_url = self.config.get("base_url", self.default_base_url)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                
                models = []
                for model_data in data.get("models", []):
                    name = model_data.get("name", "")
                    models.append(ModelInfo(
                        id=name,
                        name=name,
                        provider=ProviderType.OLLAMA,
                        capabilities={ModelCapability.CHAT, ModelCapability.STREAMING},
                        context_window=model_data.get("details", {}).get("context_length", 4096),
                        is_local=True,
                        requires_api_key=False,
                        description=f"Ollama model: {name}",
                    ))
                return models
        except Exception:
            return []
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import httpx
        start_time = asyncio.get_event_loop().time()
        
        base_url = self.config.get("base_url", self.default_base_url)
        
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                "top_p": request.top_p,
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return CompletionResponse(
            id="ollama-" + hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8],
            model=request.model,
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": data.get("message", {}).get("content", "")},
                "finish_reason": data.get("done_reason", "stop")
            }],
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
            created=int(datetime.now().timestamp()),
            provider=ProviderType.OLLAMA,
            latency_ms=latency_ms,
        )
    
    async def stream_complete(self, request: CompletionRequest) -> AsyncGenerator[Dict[str, Any], None]:
        import httpx
        base_url = self.config.get("base_url", self.default_base_url)
        
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                "top_p": request.top_p,
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            pass
    
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        import httpx
        base_url = self.config.get("base_url", self.default_base_url)
        
        embeddings = []
        for text in texts:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data.get("embedding", []))
        return embeddings
    
    async def validate_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False


class HermesProvider(AIProvider):
    """Hermes built-in provider - uses local models via Hermes."""
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.HERMES
    
    @property
    def default_base_url(self) -> str:
        return "hermes://local"
    
    async def list_models(self) -> List[ModelInfo]:
        # Would integrate with Hermes model manager
        return [
            ModelInfo(
                id="hermes-3-70b",
                name="Hermes 3 70B",
                provider=ProviderType.HERMES,
                capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING},
                context_window=8192,
                is_local=True,
                requires_api_key=False,
                description="Hermes 3 70B via Nous Portal",
            ),
            ModelInfo(
                id="hermes-3-8b",
                name="Hermes 3 8B",
                provider=ProviderType.HERMES,
                capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.STREAMING},
                context_window=8192,
                is_local=True,
                requires_api_key=False,
                description="Hermes 3 8B via Nous Portal",
            ),
        ]
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Would integrate with Hermes model runner
        # For now, return mock response
        return CompletionResponse(
            id="hermes-" + hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8],
            model=request.model,
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": "[Hermes response would go here]"},
                "finish_reason": "stop"
            }],
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            created=int(datetime.now().timestamp()),
            provider=ProviderType.HERMES,
            latency_ms=0,
        )
    
    async def stream_complete(self, request: CompletionRequest) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "text", "text": "[Hermes streaming response]"}
    
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # Would use Hermes embeddings
        return [[0.0] * 384 for _ in texts]
    
    async def validate_connection(self) -> bool:
        return True  # Always available locally


class ProviderRegistry:
    """Registry for managing AI providers and API keys."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.providers: Dict[ProviderType, AIProvider] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.default_provider: Optional[ProviderType] = None
        self.default_model: Optional[str] = None
        
        # Load saved configuration
        self._load_config()
    
    def register_provider(self, provider_type: ProviderType, provider: AIProvider):
        """Register an AI provider."""
        self.providers[provider_type] = provider
        logger.info(f"Registered provider: {provider_type.value}")
    
    def get_provider(self, provider_type: ProviderType) -> Optional[AIProvider]:
        return self.providers.get(provider_type)
    
    def add_api_key(self, provider: ProviderType, api_key: str, name: str = "") -> APIKey:
        """Add an API key for a provider."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        
        api_key_obj = APIKey(
            id=hashlib.md5(f"{provider.value}{name}{datetime.now()}".encode()).hexdigest()[:8],
            provider=provider,
            key_hash=key_hash,
            name=name or f"{provider.value} key",
            created_at=datetime.now(),
        )
        
        self.api_keys[api_key_obj.id] = api_key_obj
        self._save_config()
        
        # Update provider with new key
        if provider in self.providers:
            self.providers[provider].api_key = api_key
        
        return api_key_obj
    
    def remove_api_key(self, key_id: str) -> bool:
        if key_id in self.api_keys:
            del self.api_keys[key_id]
            self._save_config()
            return True
        return False
    
    def get_api_key(self, key_id: str) -> Optional[APIKey]:
        return self.api_keys.get(key_id)
    
    def get_keys_for_provider(self, provider: ProviderType) -> List[APIKey]:
        return [k for k in self.api_keys.values() if k.provider == provider and k.is_active]
    
    def set_default(self, provider: ProviderType, model: str = None):
        self.default_provider = provider
        if model:
            self.default_model = model
        self._save_config()
    
    def get_default(self) -> tuple:
        return (self.default_provider, self.default_model)
    
    async def get_available_models(self) -> Dict[ProviderType, List[ModelInfo]]:
        """Get all available models from all providers."""
        models = {}
        for provider_type, provider in self.providers.items():
            try:
                models[provider_type] = await provider.list_models()
            except Exception as e:
                logger.error(f"Failed to list models for {provider_type}: {e}")
                models[provider_type] = []
        return models
    
    def _save_config(self):
        config = {
            "default_provider": self.default_provider.value if self.default_provider else None,
            "default_model": self.default_model,
            "api_keys": {
                k: {
                    "id": v.id,
                    "provider": v.provider.value,
                    "key_hash": v.key_hash,
                    "name": v.name,
                    "created_at": v.created_at.isoformat(),
                    "last_used": v.last_used.isoformat() if v.last_used else None,
                    "is_active": v.is_active,
                    "rate_limit": v.rate_limit,
                    "metadata": v.metadata,
                }
                for k, v in self.api_keys.items()
            }
        }
        config_path = self.data_dir / "ai_providers.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    
    def _load_config(self):
        config_path = self.data_dir / "ai_providers.json"
        if not config_path.exists():
            return
        
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            self.default_provider = ProviderType(config["default_provider"]) if config.get("default_provider") else None
            self.default_model = config.get("default_model")
            
            for k, v in config.get("api_keys", {}).items():
                self.api_keys[k] = APIKey(
                    id=v["id"],
                    provider=ProviderType(v["provider"]),
                    key_hash=v["key_hash"],
                    name=v["name"],
                    created_at=datetime.fromisoformat(v["created_at"]),
                    last_used=datetime.fromisoformat(v["last_used"]) if v.get("last_used") else None,
                    is_active=v.get("is_active", True),
                    rate_limit=v.get("rate_limit"),
                    metadata=v.get("metadata", {}),
                )
        except Exception as e:
            logger.error(f"Failed to load AI provider config: {e}")


class ModelManager:
    """High-level model management with validation and selection."""
    
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry
        self.model_cache: Dict[str, ModelInfo] = {}
    
    async def refresh_models(self):
        """Refresh model cache from all providers."""
        all_models = await self.registry.get_available_models()
        self.model_cache = {}
        for provider_models in all_models.values():
            for model in provider_models:
                self.model_cache[model.id] = model
    
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        return self.model_cache.get(model_id)
    
    def list_models(self, 
                   provider: Optional[ProviderType] = None,
                   capability: Optional[ModelCapability] = None,
                   local_only: bool = False,
                   max_cost: Optional[float] = None) -> List[ModelInfo]:
        """List models with filtering."""
        models = list(self.model_cache.values())
        
        if provider:
            models = [m for m in models if m.provider == provider]
        if capability:
            models = [m for m in models if capability in m.capabilities]
        if local_only:
            models = [m for m in models if m.is_local]
        if max_cost is not None:
            models = [m for m in models if m.cost_per_1k_input <= max_cost]
        
        return models
    
    def recommend_model(self, 
                       task: str,
                       budget: Optional[float] = None,
                       prefer_local: bool = False) -> Optional[ModelInfo]:
        """Recommend a model for a task."""
        models = list(self.model_cache.values())
        
        if prefer_local:
            models = [m for m in models if m.is_local]
        
        if budget:
            models = [m for m in models if m.cost_per_1k_input <= budget]
        
        # Simple task-based recommendation
        task_lower = task.lower()
        
        if "vision" in task_lower or "image" in task_lower:
            models = [m for m in models if ModelCapability.VISION in m.capabilities]
        elif "code" in task_lower or "function" in task_lower:
            models = [m for m in models if ModelCapability.FUNCTION_CALLING in m.capabilities]
        elif "embed" in task_lower:
            models = [m for m in models if ModelCapability.EMBEDDING in m.capabilities]
        elif "chat" in task_lower or "conversation" in task_lower:
            models = [m for m in models if ModelCapability.CHAT in m.capabilities]
        
        if not models:
            return None
        
        # Sort by cost (cheapest first) unless local preferred
        if prefer_local:
            models.sort(key=lambda m: (not m.is_local, m.cost_per_1k_input))
        else:
            models.sort(key=lambda m: m.cost_per_1k_input)
        
        return models[0]
    
    async def validate_model(self, model_id: str) -> bool:
        """Validate that a model exists and is accessible."""
        model = self.get_model(model_id)
        if not model:
            return False
        
        provider = self.registry.get_provider(model.provider)
        if not provider:
            return False
        
        try:
            return await provider.validate_connection()
        except Exception:
            return False


# Factory for creating providers
class ProviderFactory:
    """Factory for creating AI providers."""
    
    _providers = {
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.HERMES: HermesProvider,
    }
    
    @classmethod
    def create(cls, provider_type: ProviderType, api_key: str = "", config: Dict = None) -> AIProvider:
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(api_key, config or {})
    
    @classmethod
    def register(cls, provider_type: ProviderType, provider_class: type):
        cls._providers[provider_type] = provider_class
    
    @classmethod
    def available_providers(cls) -> List[ProviderType]:
        return list(cls._providers.keys())