#!/usr/bin/env python3
"""
Claude Obsidian Second Brain - Main CLI Entry Point.

Transform Claude conversation history into a structured Obsidian Second Brain
using 10 coordinated AI agents.

Usage:
    python main.py run ./my-claude-export.json
    python main.py run ./exports/ --output ./my-vault
    python main.py validate ./export.json
    python main.py stats ./my-vault

Commands:
    run       - Process Claude exports and generate Obsidian vault
    validate  - Check export file format and structure
    stats     - Show statistics from an existing vault
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Initialize console for rich output
console = Console()


def print_banner() -> None:
    """Display the application banner."""
    banner = """
    [bold blue]Claude Obsidian Second Brain[/bold blue]
    [dim]Transform conversations into knowledge[/dim]
    """
    console.print(Panel(banner.strip(), border_style="blue"))


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


@click.group()
@click.version_option(version="1.0.0", prog_name="claude-obsidian")
def cli() -> None:
    """
    Claude Obsidian Second Brain - Transform Claude conversations into Obsidian notes.

    This tool processes Claude conversation exports and generates a structured
    Obsidian vault with tags, links, MOCs, and a knowledge graph.

    \b
    Examples:
        # Process a single export file
        python main.py run ./claude-export.json

        # Process all exports in a directory
        python main.py run ./exports/ --output ./my-vault

        # Validate an export file
        python main.py validate ./export.json

        # Show vault statistics
        python main.py stats ./my-vault
    """
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("./output"),
    help="Output directory for Obsidian vault (default: ./output)",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (default: config/settings.yaml)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate input without processing",
)
@click.option(
    "--resume",
    is_flag=True,
    default=False,
    help="Resume from last checkpoint if available",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
def run(
    input_path: Path,
    output_path: Path,
    config_path: Optional[Path],
    dry_run: bool,
    resume: bool,
    verbose: bool,
) -> None:
    """
    Process Claude exports and generate Obsidian vault.

    INPUT_PATH can be a single JSON export file or a directory containing
    multiple export files.

    \b
    Examples:
        python main.py run ./my-claude-export.json
        python main.py run ./exports/ --output ./my-vault
        python main.py run ./export.json --dry-run
        python main.py run ./exports/ --resume --verbose
    """
    print_banner()

    # Validate input path
    input_path = input_path.resolve()
    output_path = output_path.resolve()

    console.print(f"[cyan]Input:[/cyan]  {input_path}")
    console.print(f"[cyan]Output:[/cyan] {output_path}")

    if dry_run:
        console.print("\n[yellow]Dry run mode - validating input only[/yellow]")
        # Perform validation
        is_valid = _validate_input(input_path)
        if is_valid:
            console.print("[green]Input validation passed[/green]")
            sys.exit(0)
        else:
            console.print("[red]Input validation failed[/red]")
            sys.exit(1)

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Import and run orchestrator
    try:
        from agents import OrchestratorAgent

        config = config_path or Path("config/settings.yaml")
        orchestrator = OrchestratorAgent(config)
        result = asyncio.run(orchestrator.run(input_path, output_path))

        if result.success:
            console.print("\n[bold green]Pipeline completed successfully![/bold green]")
            sys.exit(0)
        else:
            console.print("\n[bold red]Pipeline completed with errors[/bold red]")
            sys.exit(1)

    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
        console.print("[yellow]Make sure all dependencies are installed:[/yellow]")
        console.print("  pip install -e .")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed validation results",
)
def validate(input_path: Path, verbose: bool) -> None:
    """
    Validate Claude export file format.

    Checks that the export file has the correct structure and contains
    valid conversation data.

    \b
    Examples:
        python main.py validate ./export.json
        python main.py validate ./export.json --verbose
    """
    print_banner()

    input_path = input_path.resolve()
    console.print(f"[cyan]Validating:[/cyan] {input_path}")
    console.print()

    if input_path.is_dir():
        # Validate all JSON files in directory
        json_files = list(input_path.glob("*.json"))
        if not json_files:
            console.print("[red]No JSON files found in directory[/red]")
            sys.exit(1)

        all_valid = True
        for json_file in json_files:
            is_valid = _validate_export_file(json_file, verbose)
            if not is_valid:
                all_valid = False

        if all_valid:
            console.print(f"\n[green]All {len(json_files)} files are valid[/green]")
            sys.exit(0)
        else:
            console.print("\n[red]Some files failed validation[/red]")
            sys.exit(1)
    else:
        is_valid = _validate_export_file(input_path, verbose)
        sys.exit(0 if is_valid else 1)


@cli.command()
@click.argument("vault_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--json",
    "-j",
    "output_json",
    is_flag=True,
    default=False,
    help="Output statistics as JSON",
)
def stats(vault_path: Path, output_json: bool) -> None:
    """
    Show statistics from an existing Obsidian vault.

    Analyzes the vault structure, counts notes, MOCs, tags, and links.

    \b
    Examples:
        python main.py stats ./my-vault
        python main.py stats ./my-vault --json
    """
    if not output_json:
        print_banner()

    vault_path = vault_path.resolve()

    if not vault_path.is_dir():
        console.print("[red]Vault path must be a directory[/red]")
        sys.exit(1)

    # Gather statistics
    stats_data = _gather_vault_stats(vault_path)

    if output_json:
        click.echo(json.dumps(stats_data, indent=2))
    else:
        _display_vault_stats(vault_path, stats_data)

    sys.exit(0)


def _validate_input(input_path: Path) -> bool:
    """Validate input path and contents."""
    if input_path.is_file():
        return _validate_export_file(input_path, verbose=False)
    elif input_path.is_dir():
        json_files = list(input_path.glob("*.json"))
        if not json_files:
            console.print("[red]No JSON files found in directory[/red]")
            return False
        return all(_validate_export_file(f, verbose=False) for f in json_files)
    return False


def _validate_export_file(file_path: Path, verbose: bool) -> bool:
    """
    Validate a single export file.

    Args:
        file_path: Path to the JSON file.
        verbose: Whether to show detailed output.

    Returns:
        True if valid, False otherwise.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON in {file_path.name}:[/red] {e}")
        return False
    except OSError as e:
        console.print(f"[red]Cannot read {file_path.name}:[/red] {e}")
        return False

    # Check structure
    if isinstance(data, list):
        conversations = data
    elif isinstance(data, dict):
        # Could be a single conversation or a wrapper
        if "conversations" in data:
            conversations = data["conversations"]
        elif "messages" in data:
            conversations = [data]
        else:
            errors.append("Unknown file structure - expected 'conversations' or 'messages' key")
            conversations = []
    else:
        errors.append("Invalid root element - expected list or object")
        conversations = []

    if not conversations:
        errors.append("No conversations found in file")

    # Validate conversations
    valid_count = 0
    for i, conv in enumerate(conversations):
        conv_errors = _validate_conversation(conv, i)
        if conv_errors:
            errors.extend(conv_errors)
        else:
            valid_count += 1

    # Display results
    if errors:
        console.print(f"[red]INVALID[/red] {file_path.name}")
        if verbose:
            for error in errors:
                console.print(f"  [red]-[/red] {error}")
        return False
    else:
        console.print(f"[green]VALID[/green]   {file_path.name} ({valid_count} conversations)")
        if warnings and verbose:
            for warning in warnings:
                console.print(f"  [yellow]-[/yellow] {warning}")
        return True


def _validate_conversation(conv: Any, index: int) -> list[str]:
    """
    Validate a single conversation structure.

    Args:
        conv: Conversation data.
        index: Index in the file.

    Returns:
        List of error messages.
    """
    errors: list[str] = []

    if not isinstance(conv, dict):
        errors.append(f"Conversation {index}: not an object")
        return errors

    # Check for messages
    messages = conv.get("messages", conv.get("chat_messages", []))
    if not messages:
        errors.append(f"Conversation {index}: no messages found")
        return errors

    # Validate messages
    for j, msg in enumerate(messages):
        if not isinstance(msg, dict):
            errors.append(f"Conversation {index}, message {j}: not an object")
            continue

        # Check for role/sender
        role = msg.get("role", msg.get("sender", msg.get("type")))
        if not role:
            errors.append(f"Conversation {index}, message {j}: missing role/sender")

        # Check for content
        content = msg.get("content", msg.get("text", msg.get("message")))
        if content is None:
            errors.append(f"Conversation {index}, message {j}: missing content")

    return errors


def _gather_vault_stats(vault_path: Path) -> dict[str, Any]:
    """
    Gather statistics from an Obsidian vault.

    Args:
        vault_path: Path to the vault directory.

    Returns:
        Dictionary of statistics.
    """
    stats: dict[str, Any] = {
        "total_files": 0,
        "markdown_files": 0,
        "moc_files": 0,
        "folders": 0,
        "tags": {},
        "total_links": 0,
        "total_words": 0,
        "total_size_bytes": 0,
        "file_types": {},
        "oldest_file": None,
        "newest_file": None,
    }

    # Count files and folders
    for item in vault_path.rglob("*"):
        if item.is_file():
            stats["total_files"] += 1
            stats["total_size_bytes"] += item.stat().st_size

            # Track file types
            suffix = item.suffix.lower()
            stats["file_types"][suffix] = stats["file_types"].get(suffix, 0) + 1

            if suffix == ".md":
                stats["markdown_files"] += 1

                # Check if MOC
                if "moc" in item.stem.lower() or "index" in item.stem.lower():
                    stats["moc_files"] += 1

                # Parse markdown content
                try:
                    content = item.read_text(encoding="utf-8")

                    # Count words
                    words = len(content.split())
                    stats["total_words"] += words

                    # Extract tags
                    import re

                    tags = re.findall(r"#([\w/]+)", content)
                    for tag in tags:
                        stats["tags"][tag] = stats["tags"].get(tag, 0) + 1

                    # Count links
                    links = re.findall(r"\[\[(.*?)\]\]", content)
                    stats["total_links"] += len(links)

                except Exception:
                    pass

                # Track file dates
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if stats["oldest_file"] is None or mtime < stats["oldest_file"]:
                    stats["oldest_file"] = mtime
                if stats["newest_file"] is None or mtime > stats["newest_file"]:
                    stats["newest_file"] = mtime

        elif item.is_dir():
            stats["folders"] += 1

    # Convert dates to strings for JSON serialization
    if stats["oldest_file"]:
        stats["oldest_file"] = stats["oldest_file"].isoformat()
    if stats["newest_file"]:
        stats["newest_file"] = stats["newest_file"].isoformat()

    return stats


def _display_vault_stats(vault_path: Path, stats: dict[str, Any]) -> None:
    """Display vault statistics in a formatted table."""
    console.print(f"[cyan]Vault:[/cyan] {vault_path}")
    console.print()

    # Main stats table
    table = Table(title="Vault Statistics", border_style="blue")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white", justify="right")

    table.add_row("Total Files", str(stats["total_files"]))
    table.add_row("Markdown Files", str(stats["markdown_files"]))
    table.add_row("MOC Files", str(stats["moc_files"]))
    table.add_row("Folders", str(stats["folders"]))
    table.add_row("Total Links", str(stats["total_links"]))
    table.add_row("Total Words", f"{stats['total_words']:,}")
    table.add_row("Unique Tags", str(len(stats["tags"])))

    # Format size
    size_mb = stats["total_size_bytes"] / (1024 * 1024)
    if size_mb < 1:
        size_str = f"{stats['total_size_bytes'] / 1024:.1f} KB"
    else:
        size_str = f"{size_mb:.2f} MB"
    table.add_row("Total Size", size_str)

    if stats["oldest_file"]:
        table.add_row("Oldest File", stats["oldest_file"][:10])
    if stats["newest_file"]:
        table.add_row("Newest File", stats["newest_file"][:10])

    console.print(table)

    # Top tags
    if stats["tags"]:
        console.print()
        tag_table = Table(title="Top 10 Tags", border_style="blue")
        tag_table.add_column("Tag", style="cyan")
        tag_table.add_column("Count", style="white", justify="right")

        sorted_tags = sorted(stats["tags"].items(), key=lambda x: x[1], reverse=True)[:10]
        for tag, count in sorted_tags:
            tag_table.add_row(f"#{tag}", str(count))

        console.print(tag_table)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
