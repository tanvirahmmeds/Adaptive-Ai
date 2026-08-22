"""
Building Tools - Code generation, project scaffolding, build systems, and development tools.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProjectTemplate:
    """Project template definition."""
    name: str
    description: str
    language: str
    framework: Optional[str] = None
    files: Dict[str, str] = field(default_factory=dict)  # path -> content template
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)
    scripts: Dict[str, str] = field(default_factory=dict)
    post_create_commands: List[str] = field(default_factory=list)


@dataclass
class BuildConfig:
    """Build configuration."""
    name: str
    language: str
    build_command: str
    test_command: Optional[str] = None
    lint_command: Optional[str] = None
    format_command: Optional[str] = None
    run_command: Optional[str] = None
    output_dir: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)


@dataclass
class CodeFile:
    """Code file representation."""
    path: str
    content: str
    language: str
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    complexity: int = 0
    lines: int = 0


class BuildingTool:
    """Main building tool for code generation and project management."""
    
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.templates = self._load_templates()
        self.build_configs = self._load_build_configs()
    
    def _load_templates(self) -> Dict[str, ProjectTemplate]:
        """Load project templates."""
        templates = {}
        
        # Python templates
        templates["python-basic"] = ProjectTemplate(
            name="python-basic",
            description="Basic Python project with modern tooling",
            language="python",
            files={
                "pyproject.toml": """[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
authors = ["{{author}}"]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.10"
dependencies = {{dependencies}}

[project.optional-dependencies]
dev = {{dev_dependencies}}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
""",
                "README.md": """# {{project_name}}

{{description}}

## Installation

```bash
pip install {{project_name}}
```

## Usage

```python
from {{project_name}} import main

main()
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Format
black .

# Type check
mypy .
""",
                "src/{{project_name}}/__init__.py": "\"\"\"\n{{project_name}} - {{description}}\n\"\"\"\n\n__version__ = \"0.1.0\"\n\n\ndef main():\n    print(\"Hello from {{project_name}}!\")\n\n\nif __name__ == \"__main__\":\n    main()\n",
                "tests/__init__.py": "",
                "tests/test_main.py": """import pytest\nfrom {{project_name}} import main\n\n\ndef test_main():\n    # Test main function\n    assert main() is None\n""",
                ".gitignore": """__pycache__/
*.py[cod]
*$py.class
*.so
.env
.venv
venv/
ENV/
build/
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.DS_Store
""",
            },
            dependencies=[],
            dev_dependencies=["pytest>=7.0", "ruff>=0.1", "black>=23.0", "mypy>=1.0"],
            scripts={
                "test": "pytest",
                "lint": "ruff check .",
                "format": "black .",
                "typecheck": "mypy .",
            },
            post_create_commands=["pip install -e \".[dev]\""]
        )
        
        templates["python-fastapi"] = ProjectTemplate(
            name="python-fastapi",
            description="FastAPI web service with modern tooling",
            language="python",
            framework="fastapi",
            files={
                "pyproject.toml": """[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
authors = ["{{author}}"]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.100",
    "uvicorn>=0.23",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "httpx>=0.25",
    "ruff>=0.1",
    "black>=23.0",
    "mypy>=1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100

[tool.black]
line-length = 100

[tool.pytest.ini_options]
asyncio_mode = "auto"
""",
                "README.md": """# {{project_name}}

{{description}}

## Quick Start

```bash
pip install -e ".[dev]"
{{project_name}}-server
```

## API Docs

Open http://localhost:8000/docs for Swagger UI.
""",
                "src/{{project_name}}/__init__.py": "\"\"\"\n{{project_name}} - {{description}}\n\"\"\"\n\n__version__ = \"0.1.0\"\n",
                "src/{{project_name}}/main.py": """from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="{{project_name}}",
    description="{{description}}",
    version="0.1.0",
    lifespan=lifespan,
)


class HealthResponse(BaseModel):
    status: str = "ok"


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@app.get("/")
async def root():
    return {"message": "Welcome to {{project_name}}", "docs": "/docs"}
""",
                "src/{{project_name}}/config.py": """from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    class Config:
        env_file = ".env"


settings = Settings()
""",
                "src/{{project_name}}/server.py": """import uvicorn
from .config import settings
from .main import app


def main():
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
""",
                "tests/__init__.py": "",
                "tests/test_health.py": """import pytest
from httpx import AsyncClient
from {{project_name}}.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
""",
                ".gitignore": """__pycache__/
*.py[cod]
*$py.class
.env
.venv
venv/
ENV/
build/
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
""",
            },
            dependencies=["fastapi>=0.100", "uvicorn>=0.23", "pydantic>=2.0", "pydantic-settings>=2.0"],
            dev_dependencies=["pytest>=7.0", "pytest-asyncio>=0.21", "httpx>=0.25", "ruff>=0.1", "black>=23.0", "mypy>=1.0"],
            scripts={
                "dev": "uvicorn {{project_name}}.main:app --reload",
                "start": "python -m {{project_name}}.server",
                "test": "pytest",
                "lint": "ruff check .",
                "format": "black .",
            },
            post_create_commands=["pip install -e \".[dev]\""]
        )
        
        # Node.js templates
        templates["node-basic"] = ProjectTemplate(
            name="node-basic",
            description="Basic Node.js project with TypeScript",
            language="javascript",
            framework="node",
            files={
                "package.json": """{
  "name": "{{project_name}}",
  "version": "0.1.0",
  "description": "{{description}}",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "dev": "tsx watch src/index.ts",
    "start": "node dist/index.js",
    "test": "vitest run",
    "lint": "eslint src --ext .ts",
    "format": "prettier --write \"src/**/*.ts\""
  },
  "keywords": [],
  "author": "{{author}}",
  "license": "MIT",
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.0",
    "tsx": "^4.0",
    "vitest": "^1.0",
    "eslint": "^8.0",
    "prettier": "^3.0",
    "@types/node": "^20.0"
  }
}
""",
                "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
""",
                "src/index.ts": """/**
 * {{project_name}} - {{description}}
 */

export function main(): void {
  console.log("Hello from {{project_name}}!");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
""",
                "tests/index.test.ts": """import { describe, it, expect } from "vitest";
import { main } from "../src/index";

describe("main", () => {
  it("should run without errors", () => {
    expect(() => main()).not.toThrow();
  });
});
""",
                ".gitignore": """node_modules/
dist/
.env
*.log
.DS_Store
""",
                ".prettierrc": """{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5"
}
""",
                ".eslintrc.json": """{
  "env": { "es2022": true, "node": true },
  "extends": ["eslint:recommended"],
  "parser": "@typescript-eslint/parser",
  "parserOptions": { "ecmaVersion": "latest", "sourceType": "module" },
  "rules": {}
}
""",
            },
            dependencies=[],
            dev_dependencies=["typescript", "tsx", "vitest", "eslint", "prettier", "@types/node"],
            scripts={
                "build": "tsc",
                "dev": "tsx watch src/index.ts",
                "start": "node dist/index.js",
                "test": "vitest run",
                "lint": "eslint src --ext .ts",
                "format": "prettier --write \"src/**/*.ts\"",
            },
            post_create_commands=["npm install"]
        )
        
        templates["node-express"] = ProjectTemplate(
            name="node-express",
            description="Express.js web server with TypeScript",
            language="javascript",
            framework="express",
            files={
                "package.json": """{
  "name": "{{project_name}}",
  "version": "0.1.0",
  "description": "{{description}}",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "dev": "tsx watch src/index.ts",
    "start": "node dist/index.js",
    "test": "vitest run",
    "lint": "eslint src --ext .ts"
  },
  "dependencies": {
    "express": "^4.18",
    "cors": "^2.8",
    "helmet": "^7.0",
    "morgan": "^1.10",
    "dotenv": "^16.0"
  },
  "devDependencies": {
    "typescript": "^5.0",
    "tsx": "^4.0",
    "vitest": "^1.0",
    "eslint": "^8.0",
    "@types/node": "^20.0",
    "@types/express": "^4.17",
    "@types/cors": "^2.8",
    "@types/morgan": "^1.9"
  }
}
""",
                "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
""",
                "src/index.ts": """import express, { Request, Response, NextFunction } from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json());

// Health check
app.get("/health", (req: Request, res: Response) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// Root
app.get("/", (req: Request, res: Response) => {
  res.json({ message: "Welcome to {{project_name}}", docs: "/api-docs" });
});

// Error handling
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  console.error(err);
  res.status(500).json({ error: "Internal server error" });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
""",
                ".env.example": """PORT=3000
NODE_ENV=development
""",
            },
            dependencies=["express", "cors", "helmet", "morgan", "dotenv"],
            dev_dependencies=["typescript", "tsx", "vitest", "eslint", "@types/node", "@types/express", "@types/cors", "@types/morgan"],
            scripts={
                "build": "tsc",
                "dev": "tsx watch src/index.ts",
                "start": "node dist/index.js",
                "test": "vitest run",
                "lint": "eslint src --ext .ts",
            },
            post_create_commands=["npm install", "cp .env.example .env"]
        )
        
        return templates
    
    def _load_build_configs(self) -> Dict[str, BuildConfig]:
        """Load build configurations for different languages."""
        return {
            "python": BuildConfig(
                name="python",
                language="python",
                build_command="python -m py_compile {file}",
                test_command="pytest {args}",
                lint_command="ruff check {args}",
                format_command="black {args}",
                run_command="python {file}",
            ),
            "javascript": BuildConfig(
                name="javascript",
                language="javascript",
                build_command="tsc",
                test_command="vitest run {args}",
                lint_command="eslint {args}",
                format_command="prettier --write {args}",
                run_command="node {file}",
            ),
            "rust": BuildConfig(
                name="rust",
                language="rust",
                build_command="cargo build {args}",
                test_command="cargo test {args}",
                lint_command="cargo clippy {args}",
                format_command="cargo fmt {args}",
                run_command="cargo run {args}",
            ),
            "go": BuildConfig(
                name="go",
                language="go",
                build_command="go build {args}",
                test_command="go test {args}",
                lint_command="golangci-lint run {args}",
                format_command="go fmt {args}",
                run_command="go run {file}",
            ),
        }
    
    def list_templates(self) -> Dict[str, Dict[str, Any]]:
        """List available project templates."""
        return {
            name: {
                "name": t.name,
                "description": t.description,
                "language": t.language,
                "framework": t.framework,
                "dependencies": t.dependencies,
                "dev_dependencies": t.dev_dependencies,
            }
            for name, t in self.templates.items()
        }
    
    async def create_project(self, 
                           template_name: str,
                           project_name: str,
                           destination: Path,
                           variables: Dict[str, str] = None) -> Dict[str, Any]:
        """Create a new project from a template."""
        template = self.templates.get(template_name)
        if not template:
            return {"success": False, "error": f"Template not found: {template_name}"}
        
        # Prepare variables
        vars_dict = {
            "project_name": project_name,
            "description": f"A {template.language} project",
            "author": "User",
            "dependencies": json.dumps(template.dependencies, indent=2),
            "dev_dependencies": json.dumps(template.dev_dependencies, indent=2),
        }
        if variables:
            vars_dict.update(variables)
        
        try:
            destination = Path(destination) / project_name
            destination.mkdir(parents=True, exist_ok=True)
            
            # Create files
            for file_path, content in template.files.items():
                # Render template
                rendered_content = self._render_template(content, vars_dict)
                rendered_path = self._render_template(file_path, vars_dict)
                
                full_path = destination / rendered_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(rendered_content)
            
            # Run post-create commands
            for cmd in template.post_create_commands:
                rendered_cmd = self._render_template(cmd, vars_dict)
                try:
                    subprocess.run(rendered_cmd, shell=True, cwd=destination, check=True)
                except subprocess.CalledProcessError as e:
                    return {"success": False, "error": f"Post-create command failed: {cmd}, error: {e}"}
            
            return {"success": True, "path": str(destination)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _render_template(self, content: str, variables: Dict[str, str]) -> str:
        """Render a template with variables."""
        result = content
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result
    
    async def build(self, config_name: str, args: str = "", working_dir: Path = None) -> Dict[str, Any]:
        """Build project using configured build command."""
        config = self.build_configs.get(config_name)
        if not config:
            return {"success": False, "error": f"Build config not found: {config_name}"}
        
        working_dir = working_dir or self.workspace
        command = config.build_command.format(args=args)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, **config.environment}
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Build timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test(self, config_name: str, args: str = "", working_dir: Path = None) -> Dict[str, Any]:
        """Run tests."""
        config = self.build_configs.get(config_name)
        if not config or not config.test_command:
            return {"success": False, "error": f"Test command not configured for {config_name}"}
        
        working_dir = working_dir or self.workspace
        command = config.test_command.format(args=args)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, **config.environment}
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def lint(self, config_name: str, args: str = "", working_dir: Path = None) -> Dict[str, Any]:
        """Run linter."""
        config = self.build_configs.get(config_name)
        if not config or not config.lint_command:
            return {"success": False, "error": f"Lint command not configured for {config_name}"}
        
        working_dir = working_dir or self.workspace
        command = config.lint_command.format(args=args)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, **config.environment}
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def format_code(self, config_name: str, args: str = "", working_dir: Path = None) -> Dict[str, Any]:
        """Format code."""
        config = self.build_configs.get(config_name)
        if not config or not config.format_command:
            return {"success": False, "error": f"Format command not configured for {config_name}"}
        
        working_dir = working_dir or self.workspace
        command = config.format_command.format(args=args)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, **config.environment}
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def analyze_code(self, file_path: Path) -> CodeFile:
        """Analyze a code file."""
        content = file_path.read_text()
        language = file_path.suffix.lstrip('.')
        
        # Simple analysis
        lines = content.split('\n')
        imports = [line.strip() for line in lines if line.strip().startswith(('import ', 'from ', 'require(', 'import '))]
        
        # Simple function/class detection
        functions = [line.strip() for line in lines if line.strip().startswith(('def ', 'function ', 'fn ', 'func '))]
        classes = [line.strip() for line in lines if line.strip().startswith(('class ', 'class '))]
        
        return CodeFile(
            path=str(file_path),
            content=content,
            language=language,
            imports=imports,
            functions=functions,
            classes=classes,
            complexity=len(functions) + len(classes),
            lines=len(lines),
        )
    
    async def generate_code(self, 
                          specification: str,
                          language: str,
                          framework: str = None) -> Dict[str, Any]:
        """Generate code from natural language specification."""
        # This would integrate with an LLM in practice
        # For now, return a template-based response
        
        if language == "python":
            if "api" in specification.lower() or "fastapi" in specification.lower():
                template = self.templates.get("python-fastapi")
                if template:
                    return await self.create_project("python-fastapi", "generated_api", Path.cwd() / "generated")
        
        return {"success": False, "error": "Code generation requires LLM integration"}


class BuildToolPlugin:
    """Plugin for building tools integration."""
    
    def __init__(self, name: str, framework, workspace: Path):
        self.name = name
        self.framework = framework
        self.building_tool = BuildingTool(workspace)
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "create_project",
            "build",
            "test",
            "lint",
            "format",
            "analyze_code",
            "list_templates",
            "generate_code",
        ]
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("building.create_project", self._handle_create_project)
        self.framework.event_bus.subscribe("building.build", self._handle_build)
        self.framework.event_bus.subscribe("building.test", self._handle_test)
        self.framework.event_bus.subscribe("building.lint", self._handle_lint)
        self.framework.event_bus.subscribe("building.format", self._handle_format)
        self.framework.event_bus.subscribe("building.analyze", self._handle_analyze)
        self.framework.event_bus.subscribe("building.list_templates", self._handle_list_templates)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_create_project(self, event):
        template = event.payload.get("template")
        project_name = event.payload.get("project_name")
        destination = event.payload.get("destination", ".")
        variables = event.payload.get("variables", {})
        
        result = await self.building_tool.create_project(template, project_name, Path(destination), variables)
        
        await self.framework.event_bus.publish(Event("building.create_project.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_build(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.build(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.build.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_test(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.test(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.test.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_lint(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.lint(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.lint.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_format(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.format_code(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.format.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_analyze(self, event):
        file_path = event.payload.get("file_path")
        if not file_path:
            await self.framework.event_bus.publish(Event("building.analyze.result", {
                "request_id": event.payload.get("request_id"),
                "error": "file_path required"
            }))
            return
        
        code_file = await self.building_tool.analyze_code(Path(file_path))
        
        await self.framework.event_bus.publish(Event("building.analyze.result", {
            "request_id": event.payload.get("request_id"),
            "file": {
                "path": code_file.path,
                "language": code_file.language,
                "imports": code_file.imports,
                "functions": code_file.functions,
                "classes": code_file.classes,
                "complexity": code_file.complexity,
                "lines": code_file.lines,
            }
        }))
    
    async def _handle_list_templates(self, event):
        templates = self.building_tool.list_templates()
        
        await self.framework.event_bus.publish(Event("building.list_templates.result", {
            "request_id": event.payload.get("request_id"),
            "templates": templates
        }))


class BuildingToolPlugin:
    """Plugin for building tools integration."""
    
    def __init__(self, name: str, framework, workspace: Path):
        self.name = name
        self.framework = framework
        self.building_tool = BuildingTool(workspace)
        self.enabled = False  # Plugin starts disabled
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "create_project",
            "build",
            "test",
            "lint",
            "format",
            "analyze_code",
            "list_templates",
            "generate_code",
        ]
    
    async def initialize(self) -> bool:
        self.framework.event_bus.subscribe("building.create_project", self._handle_create_project)
        self.framework.event_bus.subscribe("building.build", self._handle_build)
        self.framework.event_bus.subscribe("building.test", self._handle_test)
        self.framework.event_bus.subscribe("building.lint", self._handle_lint)
        self.framework.event_bus.subscribe("building.format", self._handle_format)
        self.framework.event_bus.subscribe("building.analyze", self._handle_analyze)
        self.framework.event_bus.subscribe("building.list_templates", self._handle_list_templates)
        return True
    
    async def shutdown(self):
        pass
    
    async def _handle_create_project(self, event):
        template = event.payload.get("template")
        project_name = event.payload.get("project_name")
        destination = event.payload.get("destination", ".")
        variables = event.payload.get("variables", {})
        
        result = await self.building_tool.create_project(template, project_name, Path(destination), variables)
        
        await self.framework.event_bus.publish(Event("building.create_project.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_build(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.build(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.build.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_test(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.test(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.test.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_lint(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.lint(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.lint.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_format(self, event):
        config = event.payload.get("config", "python")
        args = event.payload.get("args", "")
        working_dir = event.payload.get("working_dir")
        
        result = await self.building_tool.format_code(config, args, Path(working_dir) if working_dir else None)
        
        await self.framework.event_bus.publish(Event("building.format.result", {
            "request_id": event.payload.get("request_id"),
            **result
        }))
    
    async def _handle_analyze(self, event):
        file_path = event.payload.get("file_path")
        if not file_path:
            await self.framework.event_bus.publish(Event("building.analyze.result", {
                "request_id": event.payload.get("request_id"),
                "error": "file_path required"
            }))
            return
        
        code_file = await self.building_tool.analyze_code(Path(file_path))
        
        await self.framework.event_bus.publish(Event("building.analyze.result", {
            "request_id": event.payload.get("request_id"),
            "file": {
                "path": code_file.path,
                "language": code_file.language,
                "imports": code_file.imports,
                "functions": code_file.functions,
                "classes": code_file.classes,
                "complexity": code_file.complexity,
                "lines": code_file.lines,
            }
        }))
    
    async def _handle_list_templates(self, event):
        templates = self.building_tool.list_templates()
        
        await self.framework.event_bus.publish(Event("building.list_templates.result", {
            "request_id": event.payload.get("request_id"),
            "templates": templates
        }))