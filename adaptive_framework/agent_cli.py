#!/usr/bin/env python3
"""
Adaptive Framework Agent CLI - Run autonomous agent with goals.
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout

from adaptive_framework import create_framework, AdaptiveFramework

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="adaptive-agent")
@click.option("--data-dir", type=click.Path(), help="Data directory path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx, data_dir: Optional[str], verbose: bool):
    """Adaptive Agent CLI - Run autonomous agent with goals."""
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["verbose"] = verbose
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.argument("goal", required=True)
@click.option("--max-iterations", "-i", default=20, help="Maximum iterations")
@click.option("--criteria", "-c", multiple=True, help="Success criteria")
@click.option("--output", "-o", type=click.Path(), help="Output file for results")
@click.option("--watch", "-w", is_flag=True, help="Watch mode - show progress live")
@click.pass_context
def run(ctx, goal: str, max_iterations: int, criteria: tuple, output: Optional[str], watch: bool):
    """Run the autonomous agent with a goal."""
    
    async def _run():
        console.print(f"[green]Starting agent with goal:[/green] {goal}")
        
        fw = await create_framework(ctx.obj["data_dir"])
        
        try:
            success_criteria = list(criteria) if criteria else ["Task completed"]
            
            if watch:
                # Live progress mode
                with Live(console=console, refresh_per_second=4) as live:
                    async def progress_callback(state):
                        layout = Layout()
                        layout.split_column(
                            Layout(Panel(f"[bold]Goal:[/bold] {goal}", title="Goal")),
                            Layout(Panel(f"Status: {state.get('status')}\nIteration: {state.get('iteration')}/{max_iterations}", title="Progress")),
                        )
                        live.update(layout)
                    
                    result = await fw.execute("agent.run", {
                        "goal": {"description": goal, "success_criteria": success_criteria},
                        "max_iterations": max_iterations
                    })
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Running agent...", total=max_iterations)
                    
                    result = await fw.execute("agent.run", {
                        "goal": {"description": goal, "success_criteria": success_criteria},
                        "max_iterations": max_iterations
                    })
                    
                    progress.update(task, completed=max_iterations)
            
            state = result.get("state", {})
            
            # Display results
            console.print(f"\n[bold]Result:[/bold] {state.get('status', 'unknown')}")
            console.print(f"[bold]Iterations:[/bold] {state.get('iteration', 0)}")
            
            if state.get("error"):
                console.print(f"[red]Error:[/red] {state.get('error')}")
            
            # Task table
            table = Table(title="Tasks")
            table.add_column("Description", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Action", style="yellow")
            table.add_column("Error", style="red")
            
            for task in state.get("tasks", []):
                table.add_row(
                    task.get("description", ""),
                    task.get("status", ""),
                    task.get("action", ""),
                    task.get("error", "")[:50] if task.get("error") else ""
                )
            
            console.print(table)
            
            # Save output if requested
            if output:
                output_path = Path(output)
                output_path.write_text(json.dumps(result, indent=2))
                console.print(f"[green]Results saved to:[/green] {output}")
            
        finally:
            await fw.stop()
    
    asyncio.run(_run())


@cli.command()
@click.argument("goal", required=True)
@click.option("--iterations", "-i", default=10, help="Iterations per step")
@click.pass_context
def step(ctx, goal: str, iterations: int):
    """Run agent step by step with manual confirmation."""
    
    async def _step():
        fw = await create_framework(ctx.obj["data_dir"])
        
        try:
            console.print(f"[green]Starting step-by-step agent:[/green] {goal}")
            
            # Start agent
            result = await fw.execute("agent.run", {
                "goal": {"description": goal, "success_criteria": ["Task completed"]},
                "max_iterations": iterations
            })
            
            state = result.get("state", {})
            
            while state.get("status") == "running":
                console.print(f"\n[bold]Iteration {state.get('iteration')}[/bold]")
                
                # Show current task
                current_task = state.get("current_task")
                if current_task:
                    console.print(f"Task: {current_task.get('description')}")
                    console.print(f"Action: {current_task.get('action')}")
                
                # Ask for confirmation
                if not click.confirm("Continue to next step?"):
                    break
                
                # Get next state
                result = await fw.execute("agent.state", {})
                state = result.get("state", {})
            
            console.print(f"\n[bold]Final Status:[/bold] {state.get('status')}")
            
        finally:
            await fw.stop()
    
    asyncio.run(_step())


@cli.command()
@click.pass_context
def interactive(ctx):
    """Interactive agent session."""
    
    async def _interactive():
        fw = await create_framework(ctx.obj["data_dir"])
        
        console.print(Panel("[bold]Adaptive Agent Interactive Mode[/bold]\nCommands: goal, status, memory, vector, mcp, help, exit"))
        
        while True:
            try:
                cmd = console.input("[bold cyan]agent>[/bold cyan] ").strip()
                
                if cmd in ("exit", "quit", "q"):
                    break
                elif cmd in ("help", "h", "?"):
                    console.print("""
[bold]Commands:[/bold]
  goal <description>     - Set a new goal
  status                 - Show agent status
  pause                  - Pause agent
  resume                 - Resume agent
  memory <query>         - Search memory
  vector <query>         - Semantic search
  mcp connect <name> <cmd> - Connect MCP server
  mcp list               - List MCP servers
  execute <action> [json] - Execute capability
  help                   - Show this help
  exit                   - Exit
                    """)
                elif cmd.startswith("goal "):
                    goal_desc = cmd[5:].strip()
                    result = await fw.execute("agent.run", {
                        "goal": {"description": goal_desc, "success_criteria": ["Task completed"]},
                        "max_iterations": 10
                    })
                    state = result.get("state", {})
                    console.print(f"Status: {state.get('status')}")
                    console.print(f"Iterations: {state.get('iteration')}")
                elif cmd == "status":
                    result = await fw.execute("agent.state", {})
                    state = result.get("state", {})
                    console.print(f"Status: {state.get('status')}")
                    console.print(f"Iteration: {state.get('iteration')}")
                elif cmd == "pause":
                    await fw.execute("agent.pause", {})
                    console.print("Agent paused")
                elif cmd == "resume":
                    await fw.execute("agent.resume", {})
                    console.print("Agent resumed")
                elif cmd.startswith("memory "):
                    query = cmd[7:].strip()
                    memories = await fw.recall(limit=5)
                    for m in memories:
                        console.print(f"  {m.type}: {m.content}")
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
                elif cmd == "mcp list":
                    result = await fw.execute("mcp.list_servers", {})
                    console.print(json.dumps(result, indent=2))
                elif cmd.startswith("execute "):
                    parts = cmd[8:].split(" ", 1)
                    action = parts[0]
                    params = json.loads(parts[1]) if len(parts) > 1 else {}
                    result = await fw.execute(action, params)
                    console.print(json.dumps(result, indent=2))
                else:
                    console.print(f"[red]Unknown command: {cmd}[/red]")
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        await fw.stop()
    
    asyncio.run(_interactive())


@cli.command()
@click.argument("action")
@click.argument("params", required=False)
@click.pass_context
def execute(ctx, action: str, params: Optional[str]):
    """Execute a single capability."""
    
    async def _execute():
        fw = await create_framework(ctx.obj["data_dir"])
        
        try:
            parameters = json.loads(params) if params else {}
            result = await fw.execute(action, parameters)
            console.print(json.dumps(result, indent=2))
        finally:
            await fw.stop()
    
    asyncio.run(_execute())


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8080, help="Port to bind")
@click.pass_context
def serve(ctx, host: str, port: int):
    """Run as API server."""
    console.print(f"[green]Starting API server on http://{host}:{port}[/green]")
    
    try:
        from adaptive_framework.webui import run_webui
        run_webui(host=host, port=port, data_dir=ctx.obj["data_dir"])
    except ImportError:
        console.print("[red]Web UI dependencies not installed. Run: pip install adaptive-framework[web][/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def doctor(ctx):
    """Check system health."""
    console.print(Panel("[bold]Adaptive Agent Health Check[/bold]"))
    
    # Check Python
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"Python: {py_version} {'✓' if sys.version_info >= (3, 10) else '✗'}")
    
    # Check deps
    deps = ["pydantic", "pyyaml", "rich", "click", "aiofiles", "httpx"]
    for dep in deps:
        try:
            mod = __import__(dep)
            ver = getattr(mod, "__version__", "unknown")
            console.print(f"  {dep}: {ver} ✓")
        except ImportError:
            console.print(f"  {dep}: MISSING ✗")


def main():
    """Entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()