#!/usr/bin/env python3
"""
Adaptive Framework CLI - Cross-platform command line interface.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from adaptive_framework import create_framework, AdaptiveFramework

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="adaptive")
@click.option("--data-dir", type=click.Path(), help="Data directory path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx, data_dir: Optional[str], verbose: bool):
    """Adaptive AI Framework - Self-improving agent with MCP, vector memory, and autonomous capabilities."""
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["verbose"] = verbose
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8080, help="Port to bind")
@click.option("--reload", is_flag=True, help="Auto-reload on changes")
@click.pass_context
def web(ctx, host: str, port: int, reload: bool):
    """Start the Web UI server."""
    console.print(f"[green]Starting Web UI on http://{host}:{port}[/green]")
    
    try:
        from adaptive_framework.webui import run_webui
        run_webui(host=host, port=port, reload=reload, data_dir=ctx.obj["data_dir"])
    except ImportError:
        console.print("[red]Web UI dependencies not installed. Run: pip install adaptive-framework[web][/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def gui(ctx):
    """Start the Desktop GUI application."""
    console.print("[green]Starting Desktop GUI...[/green]")
    
    try:
        from adaptive_framework.gui import run_gui
        run_gui(data_dir=ctx.obj["data_dir"])
    except ImportError:
        console.print("[red]GUI dependencies not installed. Run: pip install adaptive-framework[gui][/red]")
        sys.exit(1)


@cli.command()
@click.argument("goal", required=False)
@click.option("--max-iterations", "-i", default=20, help="Maximum iterations")
@click.option("--interactive", is_flag=True, help="Interactive mode")
@click.pass_context
def run(ctx, goal: Optional[str], max_iterations: int, interactive: bool):
    """Run the autonomous agent with a goal."""
    
    async def _run():
        console.print("[green]Starting Adaptive Framework...[/green]")
        fw = await create_framework(ctx.obj["data_dir"])
        
        try:
            if goal:
                console.print(f"[cyan]Goal:[/cyan] {goal}")
                result = await fw.execute("agent.run", {
                    "goal": {"description": goal, "success_criteria": ["Task completed"]},
                    "max_iterations": max_iterations
                })
                state = result.get("state", {})
                console.print(f"[green]Status:[/green] {state.get('status')}")
                console.print(f"[green]Iterations:[/green] {state.get('iteration')}")
                
                for task in state.get("tasks", []):
                    status_color = "green" if task.get("status") == "completed" else "red"
                    console.print(f"  [{status_color}]{task.get('description')}: {task.get('status')}[/{status_color}]")
            elif interactive:
                await _interactive_mode(fw)
            else:
                console.print("[yellow]No goal specified. Use --interactive or provide a goal.[/yellow]")
        finally:
            await fw.stop()
            console.print("[green]Framework stopped.[/green]")
    
    asyncio.run(_run())


async def _interactive_mode(fw: AdaptiveFramework):
    """Interactive REPL mode."""
    console.print(Panel("[bold]Adaptive Framework Interactive Mode[/bold]\nType 'help' for commands, 'exit' to quit"))
    
    while True:
        try:
            cmd = Prompt.ask("[bold cyan]adaptive>[/bold cyan]")
            
            if cmd in ("exit", "quit", "q"):
                break
            elif cmd in ("help", "h", "?"):
                console.print("""
[bold]Available Commands:[/bold]
  goal <description>     - Set a goal for the agent
  status                 - Show agent status
  memory <query>         - Search memory
  vector <query>         - Semantic search
  mcp connect <name> <cmd> - Connect MCP server
  help                   - Show this help
  exit                   - Exit interactive mode
                """)
            elif cmd.startswith("goal "):
                goal_desc = cmd[5:].strip()
                result = await fw.execute("agent.run", {
                    "goal": {"description": goal_desc, "success_criteria": ["Task completed"]},
                    "max_iterations": 10
                })
                state = result.get("state", {})
                console.print(f"Status: {state.get('status')}")
            elif cmd == "status":
                result = await fw.execute("agent.state", {})
                state = result.get("state", {})
                console.print(f"Status: {state.get('status')}")
                console.print(f"Iteration: {state.get('iteration')}")
            elif cmd.startswith("memory "):
                query = cmd[7:].strip()
                memories = await fw.recall(type="fact", limit=5)
                for m in memories:
                    console.print(f"  {m.content}")
            elif cmd.startswith("vector "):
                query = cmd[7:].strip()
                results = await fw.vector_memory.search(query, limit=5)
                for entry, score in results:
                    console.print(f"  [{score:.3f}] {entry.text[:80]}...")
            elif cmd.startswith("mcp connect "):
                parts = cmd[12:].split(" ", 1)
                if len(parts) == 2:
                    name, command = parts
                    result = await fw.execute("mcp.connect", {
                        "name": name,
                        "command": command.split()
                    })
                    console.print(f"MCP: {result}")
                else:
                    console.print("[red]Usage: mcp connect <name> <command>[/red]")
            else:
                console.print(f"[red]Unknown command: {cmd}[/red]")
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.option("--name", prompt="Extension name", help="Extension name")
@click.option("--description", prompt="Description", help="Extension description")
@click.pass_context
def create_extension(ctx, name: str, description: str):
    """Create a new extension template."""
    fw = AdaptiveFramework(ctx.obj["data_dir"])
    ext_dir = fw.registry.create_extension_template(name, description)
    console.print(f"[green]Created extension template at:[/green] {ext_dir}")


@cli.command()
@click.pass_context
def list_plugins(ctx):
    """List all registered plugins."""
    # This would need a running framework
    console.print("[yellow]Run 'adaptive run' first to see plugins[/yellow]")


@cli.command()
@click.pass_context
def doctor(ctx):
    """Check system health and dependencies."""
    console.print(Panel("[bold]Adaptive Framework Health Check[/bold]"))
    
    # Check Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"Python: {py_version} {'✓' if sys.version_info >= (3, 10) else '✗'}")
    
    # Check dependencies
    deps = [
        ("pydantic", "2.0"),
        ("pyyaml", "6.0"),
        ("rich", "13.0"),
        ("click", "8.0"),
        ("aiofiles", "23.0"),
    ]
    
    for dep, min_ver in deps:
        try:
            mod = __import__(dep)
            ver = getattr(mod, "__version__", "unknown")
            console.print(f"  {dep}: {ver} ✓")
        except ImportError:
            console.print(f"  {dep}: MISSING ✗")
    
    # Check optional dependencies
    optional = [
        ("fastapi", "web"),
        ("sentence_transformers", "ml"),
        ("faiss", "ml"),
        ("PyQt6", "gui"),
    ]
    
    console.print("\n[bold]Optional Dependencies:[/bold]")
    for dep, feature in optional:
        try:
            __import__(dep.lower().replace("-", "_"))
            console.print(f"  {dep}: ✓ ({feature})")
        except ImportError:
            console.print(f"  {dep}: ✗ ({feature})")
    
    # Check data directory
    data_dir = Path(ctx.obj["data_dir"]) if ctx.obj["data_dir"] else Path.home() / ".adaptive_framework"
    console.print(f"\nData directory: {data_dir}")
    console.print(f"  Exists: {data_dir.exists()} ✓" if data_dir.exists() else f"  Exists: ✗ (will be created)")
    console.print(f"  Writable: {os.access(data_dir.parent, os.W_OK)} ✓")


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize the framework data directory."""
    data_dir = Path(ctx.obj["data_dir"]) if ctx.obj["data_dir"] else Path.home() / ".adaptive_framework"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "extensions").mkdir(exist_ok=True)
    console.print(f"[green]Initialized data directory at:[/green] {data_dir}")


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()