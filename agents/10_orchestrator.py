"""
Agent 10: OrchestratorAgent - Pipeline Coordinator.

Coordinates all 9 agents and manages the complete processing pipeline
for transforming Claude conversations into an Obsidian vault.

Pipeline stages:
1. Parse - Extract conversations from export files
2. Clean - Normalize and clean conversation content
3. Tag - Apply taxonomy-based tagging
4. Extract - Pull insights, decisions, and key points
5. Graph - Build knowledge graph from relationships
6. Link - Create wikilinks between notes
7. MOC - Generate Maps of Content
8. Format - Write Obsidian-formatted markdown files
9. Index - Create master index and navigation

Features:
- Rich console UI with live progress display
- Stage-by-stage progress tracking with estimated time
- Error handling with configurable retries
- Checkpoint/resume capability
- Graceful shutdown handling (SIGINT/SIGTERM)
- Detailed logging to file and console
- Summary statistics at completion
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import yaml
from rich.console import Console
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

# Type variable for generic agent results
T = TypeVar("T")


@dataclass
class StageResult:
    """Result from a single pipeline stage."""

    stage_name: str
    success: bool
    duration_seconds: float
    items_processed: int = 0
    items_output: int = 0
    errors: list[str] = field(default_factory=list)
    data: Any = None


@dataclass
class PipelineResult:
    """Final result from the complete pipeline run."""

    success: bool
    stages_completed: list[str]
    total_conversations: int
    total_notes: int
    total_mocs: int
    duration_seconds: float
    errors: list[str]
    stage_results: dict[str, StageResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "stages_completed": self.stages_completed,
            "total_conversations": self.total_conversations,
            "total_notes": self.total_notes,
            "total_mocs": self.total_mocs,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
            "timestamp": datetime.now().isoformat(),
        }


@dataclass
class CheckpointData:
    """Data saved at checkpoints for resume capability."""

    last_completed_stage: str
    timestamp: str
    stage_results: dict[str, dict[str, Any]]
    intermediate_data: dict[str, Any]


class OrchestratorAgent:
    """
    Main pipeline orchestrator coordinating all processing agents.

    Manages the complete flow from parsing Claude exports to generating
    a fully-linked Obsidian vault with MOCs and indexes.

    Attributes:
        config: Loaded configuration dictionary
        console: Rich console for output
        logger: Configured logger instance
        agents: Dictionary of initialized agent instances
        shutdown_requested: Flag for graceful shutdown
    """

    # Pipeline stage definitions in execution order
    STAGES: list[tuple[str, str]] = [
        ("parse", "Parsing export files"),
        ("clean", "Cleaning conversations"),
        ("tag", "Applying tags"),
        ("extract", "Extracting insights"),
        ("graph", "Building knowledge graph"),
        ("link", "Creating wikilinks"),
        ("moc", "Generating MOCs"),
        ("format", "Formatting notes"),
        ("index", "Creating index"),
    ]

    def __init__(self, config_path: Path = Path("config/settings.yaml")) -> None:
        """
        Initialize the orchestrator with configuration.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self.config_path = Path(config_path)
        self.config: dict[str, Any] = {}
        self.console = Console()
        self.logger: logging.Logger = logging.getLogger("orchestrator")
        self.agents: dict[str, Any] = {}
        self.shutdown_requested = False
        self._checkpoint_path: Optional[Path] = None
        self._max_retries = 3
        self._retry_delay = 2.0

        # Load configuration
        self._load_config()

        # Setup logging
        self._setup_logging()

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Initialize all agents
        self._initialize_agents()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            # Use default configuration
            self.config = self._get_default_config()
            self.console.print(
                f"[yellow]Config file not found at {self.config_path}, using defaults[/yellow]"
            )
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            self.console.print(f"[red]Error parsing config file: {e}[/red]")
            self.config = self._get_default_config()
        except OSError as e:
            self.console.print(f"[red]Error reading config file: {e}[/red]")
            self.config = self._get_default_config()

        # Apply defaults for missing values
        defaults = self._get_default_config()
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

    def _get_default_config(self) -> dict[str, Any]:
        """Return default configuration values."""
        return {
            "api": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "temperature": 0.3,
                "timeout": 120,
                "max_retries": 3,
            },
            "paths": {
                "input_dir": "./exports",
                "output_dir": "./output",
                "cache_dir": "./.cache",
                "logs_dir": "./logs",
            },
            "agents": {
                "max_concurrent": 5,
                "timeout": 300,
                "verbose": True,
                "retry_failed": True,
                "max_retries": 2,
            },
            "processing": {
                "min_messages": 3,
                "max_messages_per_chunk": 50,
                "include_assistant_responses": True,
            },
            "obsidian": {
                "wiki_links": True,
                "create_mocs": True,
                "folder_structure": "by-topic",
            },
            "logging": {
                "level": "INFO",
                "file_logging": True,
            },
        }

    def _setup_logging(self) -> None:
        """Configure logging with Rich handler and file output."""
        log_level = getattr(
            logging, self.config.get("logging", {}).get("level", "INFO").upper(), logging.INFO
        )

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=self.console, rich_tracebacks=True, show_path=False)],
        )

        self.logger = logging.getLogger("orchestrator")
        self.logger.setLevel(log_level)

        # Add file handler if enabled
        if self.config.get("logging", {}).get("file_logging", True):
            logs_dir = Path(self.config.get("paths", {}).get("logs_dir", "./logs"))
            logs_dir.mkdir(parents=True, exist_ok=True)

            log_file = logs_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(log_level)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(file_handler)

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            self.console.print(f"\n[yellow]Received {sig_name}, initiating graceful shutdown...[/yellow]")
            self.shutdown_requested = True

        # Register handlers for SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _initialize_agents(self) -> None:
        """Initialize all pipeline agents."""
        self.logger.info("Initializing pipeline agents...")

        # Import agents dynamically to avoid circular imports
        # Each agent is initialized lazily when needed
        self.agents = {
            "parser": None,
            "cleaner": None,
            "tagger": None,
            "extractor": None,
            "graph": None,
            "linker": None,
            "moc": None,
            "formatter": None,
            "indexer": None,
        }

        self.logger.info("Agent initialization complete")

    def _get_agent(self, agent_name: str) -> Any:
        """
        Lazily load and return an agent instance.

        Args:
            agent_name: Name of the agent to load.

        Returns:
            Initialized agent instance.
        """
        if self.agents.get(agent_name) is None:
            try:
                if agent_name == "parser":
                    from agents.parser import ParserAgent

                    self.agents["parser"] = ParserAgent(self.config)
                elif agent_name == "cleaner":
                    from agents.cleaner import CleanerAgent

                    self.agents["cleaner"] = CleanerAgent(self.config)
                elif agent_name == "tagger":
                    from agents.tagger import TaggerAgent

                    self.agents["tagger"] = TaggerAgent(self.config)
                elif agent_name == "extractor":
                    from agents.extractor import ExtractorAgent

                    self.agents["extractor"] = ExtractorAgent(self.config)
                elif agent_name == "graph":
                    from agents.graph_builder import GraphBuilderAgent

                    self.agents["graph"] = GraphBuilderAgent(self.config)
                elif agent_name == "linker":
                    from agents.linker import LinkerAgent

                    self.agents["linker"] = LinkerAgent(self.config)
                elif agent_name == "moc":
                    from agents.moc_generator import MOCGeneratorAgent

                    self.agents["moc"] = MOCGeneratorAgent(self.config)
                elif agent_name == "formatter":
                    from agents.formatter import FormatterAgent

                    self.agents["formatter"] = FormatterAgent(self.config)
                elif agent_name == "indexer":
                    from agents.indexer import IndexerAgent

                    self.agents["indexer"] = IndexerAgent(self.config)
            except ImportError as e:
                self.logger.warning(f"Could not import {agent_name} agent: {e}")
                # Return a mock agent for development/testing
                self.agents[agent_name] = MockAgent(agent_name, self.config)

        return self.agents[agent_name]

    async def run(self, input_path: Path, output_path: Path) -> PipelineResult:
        """
        Execute the complete processing pipeline.

        Args:
            input_path: Path to input file or directory with exports.
            output_path: Path to output directory for Obsidian vault.

        Returns:
            PipelineResult with success status and statistics.
        """
        start_time = time.time()
        stages_completed: list[str] = []
        all_errors: list[str] = []
        stage_results: dict[str, StageResult] = {}

        # Pipeline state
        pipeline_data: dict[str, Any] = {
            "input_path": input_path,
            "output_path": output_path,
            "conversations": [],
            "cleaned": [],
            "tagged": [],
            "extracted": [],
            "graph": None,
            "linked": [],
            "mocs": [],
            "formatted": [],
            "index": None,
        }

        # Setup checkpoint path
        cache_dir = Path(self.config.get("paths", {}).get("cache_dir", "./.cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_path = cache_dir / "pipeline_checkpoint.json"

        # Check for existing checkpoint
        resume_from = self._load_checkpoint()

        # Display pipeline header
        self._display_header(input_path, output_path)

        # Create progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        ) as progress:
            # Add overall progress task
            overall_task = progress.add_task("Overall Progress", total=len(self.STAGES))

            # Track if we should skip to resume point
            should_skip = resume_from is not None

            for stage_name, stage_desc in self.STAGES:
                if self.shutdown_requested:
                    all_errors.append("Pipeline interrupted by shutdown request")
                    break

                # Skip completed stages when resuming
                if should_skip:
                    if stage_name == resume_from:
                        should_skip = False
                    else:
                        progress.update(overall_task, advance=1)
                        stages_completed.append(stage_name)
                        continue

                # Execute stage with retries
                stage_task = progress.add_task(f"Stage: {stage_desc}", total=100)
                result = await self._execute_stage_with_retry(
                    stage_name, stage_desc, pipeline_data, progress, stage_task
                )

                stage_results[stage_name] = result
                progress.update(stage_task, completed=100)

                if result.success:
                    stages_completed.append(stage_name)
                    self._save_checkpoint(stage_name, stage_results, pipeline_data)
                else:
                    all_errors.extend(result.errors)
                    # Check if this is a critical failure
                    if not self._can_continue_after_failure(stage_name):
                        self.logger.error(f"Critical stage {stage_name} failed, stopping pipeline")
                        break

                progress.update(overall_task, advance=1)

        # Calculate final statistics
        duration = time.time() - start_time
        total_conversations = len(pipeline_data.get("conversations", []))
        total_notes = len(pipeline_data.get("formatted", []))
        total_mocs = len(pipeline_data.get("mocs", []))

        # Create result
        result = PipelineResult(
            success=len(all_errors) == 0 and len(stages_completed) == len(self.STAGES),
            stages_completed=stages_completed,
            total_conversations=total_conversations,
            total_notes=total_notes,
            total_mocs=total_mocs,
            duration_seconds=duration,
            errors=all_errors,
            stage_results=stage_results,
        )

        # Display final summary
        self._display_summary(result)

        # Clean up checkpoint on success
        if result.success and self._checkpoint_path and self._checkpoint_path.exists():
            self._checkpoint_path.unlink()

        return result

    async def _execute_stage_with_retry(
        self,
        stage_name: str,
        stage_desc: str,
        pipeline_data: dict[str, Any],
        progress: Progress,
        task_id: TaskID,
    ) -> StageResult:
        """
        Execute a pipeline stage with retry logic.

        Args:
            stage_name: Name of the stage to execute.
            stage_desc: Human-readable stage description.
            pipeline_data: Shared pipeline state.
            progress: Rich progress instance.
            task_id: Progress task ID.

        Returns:
            StageResult with execution details.
        """
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self._max_retries):
            if self.shutdown_requested:
                return StageResult(
                    stage_name=stage_name,
                    success=False,
                    duration_seconds=time.time() - start_time,
                    errors=["Shutdown requested"],
                )

            try:
                self.logger.info(f"Executing stage: {stage_name} (attempt {attempt + 1}/{self._max_retries})")

                # Update progress
                progress.update(task_id, completed=10 + (attempt * 5))

                # Execute the stage
                result = await self._execute_stage(stage_name, pipeline_data, progress, task_id)

                if result.success:
                    return result

                last_error = "; ".join(result.errors) if result.errors else "Unknown error"
                self.logger.warning(f"Stage {stage_name} failed: {last_error}")

            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                self.logger.error(f"Exception in stage {stage_name}: {last_error}")
                self.logger.debug(traceback.format_exc())

            # Wait before retry
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay * (attempt + 1))

        return StageResult(
            stage_name=stage_name,
            success=False,
            duration_seconds=time.time() - start_time,
            errors=[last_error or "Max retries exceeded"],
        )

    async def _execute_stage(
        self,
        stage_name: str,
        pipeline_data: dict[str, Any],
        progress: Progress,
        task_id: TaskID,
    ) -> StageResult:
        """
        Execute a single pipeline stage.

        Args:
            stage_name: Name of the stage.
            pipeline_data: Shared pipeline state.
            progress: Rich progress instance.
            task_id: Progress task ID.

        Returns:
            StageResult with execution details.
        """
        start_time = time.time()

        try:
            if stage_name == "parse":
                return await self._stage_parse(pipeline_data, progress, task_id)
            elif stage_name == "clean":
                return await self._stage_clean(pipeline_data, progress, task_id)
            elif stage_name == "tag":
                return await self._stage_tag(pipeline_data, progress, task_id)
            elif stage_name == "extract":
                return await self._stage_extract(pipeline_data, progress, task_id)
            elif stage_name == "graph":
                return await self._stage_graph(pipeline_data, progress, task_id)
            elif stage_name == "link":
                return await self._stage_link(pipeline_data, progress, task_id)
            elif stage_name == "moc":
                return await self._stage_moc(pipeline_data, progress, task_id)
            elif stage_name == "format":
                return await self._stage_format(pipeline_data, progress, task_id)
            elif stage_name == "index":
                return await self._stage_index(pipeline_data, progress, task_id)
            else:
                return StageResult(
                    stage_name=stage_name,
                    success=False,
                    duration_seconds=time.time() - start_time,
                    errors=[f"Unknown stage: {stage_name}"],
                )
        except Exception as e:
            return StageResult(
                stage_name=stage_name,
                success=False,
                duration_seconds=time.time() - start_time,
                errors=[f"{type(e).__name__}: {str(e)}"],
            )

    async def _stage_parse(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Parse stage: Extract conversations from export files."""
        start_time = time.time()
        input_path = pipeline_data["input_path"]

        progress.update(task_id, completed=20)

        agent = self._get_agent("parser")
        conversations = await agent.process(input_path)

        progress.update(task_id, completed=80)

        pipeline_data["conversations"] = conversations

        return StageResult(
            stage_name="parse",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=1 if input_path.is_file() else len(list(input_path.glob("*.json"))),
            items_output=len(conversations),
            data={"conversation_count": len(conversations)},
        )

    async def _stage_clean(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Clean stage: Normalize conversation content."""
        start_time = time.time()
        conversations = pipeline_data.get("conversations", [])

        progress.update(task_id, completed=20)

        agent = self._get_agent("cleaner")
        cleaned = await agent.process(conversations)

        progress.update(task_id, completed=80)

        pipeline_data["cleaned"] = cleaned

        return StageResult(
            stage_name="clean",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(conversations),
            items_output=len(cleaned),
        )

    async def _stage_tag(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Tag stage: Apply taxonomy-based tagging."""
        start_time = time.time()
        cleaned = pipeline_data.get("cleaned", [])

        progress.update(task_id, completed=20)

        agent = self._get_agent("tagger")
        tagged = await agent.process(cleaned)

        progress.update(task_id, completed=80)

        pipeline_data["tagged"] = tagged

        return StageResult(
            stage_name="tag",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(cleaned),
            items_output=len(tagged),
        )

    async def _stage_extract(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Extract stage: Pull insights and decisions."""
        start_time = time.time()
        tagged = pipeline_data.get("tagged", [])

        progress.update(task_id, completed=20)

        agent = self._get_agent("extractor")
        extracted = await agent.process(tagged)

        progress.update(task_id, completed=80)

        pipeline_data["extracted"] = extracted

        return StageResult(
            stage_name="extract",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(tagged),
            items_output=len(extracted),
        )

    async def _stage_graph(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Graph stage: Build knowledge graph."""
        start_time = time.time()
        extracted = pipeline_data.get("extracted", [])

        progress.update(task_id, completed=20)

        agent = self._get_agent("graph")
        graph = await agent.process(extracted)

        progress.update(task_id, completed=80)

        pipeline_data["graph"] = graph

        # Count nodes and edges
        node_count = len(graph.nodes()) if hasattr(graph, "nodes") else 0
        edge_count = len(graph.edges()) if hasattr(graph, "edges") else 0

        return StageResult(
            stage_name="graph",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(extracted),
            items_output=node_count,
            data={"nodes": node_count, "edges": edge_count},
        )

    async def _stage_link(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Link stage: Create wikilinks between notes."""
        start_time = time.time()
        extracted = pipeline_data.get("extracted", [])
        graph = pipeline_data.get("graph")

        progress.update(task_id, completed=20)

        agent = self._get_agent("linker")
        linked = await agent.process(extracted, graph)

        progress.update(task_id, completed=80)

        pipeline_data["linked"] = linked

        return StageResult(
            stage_name="link",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(extracted),
            items_output=len(linked),
        )

    async def _stage_moc(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """MOC stage: Generate Maps of Content."""
        start_time = time.time()
        linked = pipeline_data.get("linked", [])
        graph = pipeline_data.get("graph")

        progress.update(task_id, completed=20)

        agent = self._get_agent("moc")
        mocs = await agent.process(linked, graph)

        progress.update(task_id, completed=80)

        pipeline_data["mocs"] = mocs

        return StageResult(
            stage_name="moc",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(linked),
            items_output=len(mocs),
        )

    async def _stage_format(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Format stage: Write Obsidian-formatted files."""
        start_time = time.time()
        linked = pipeline_data.get("linked", [])
        mocs = pipeline_data.get("mocs", [])
        output_path = pipeline_data["output_path"]

        progress.update(task_id, completed=20)

        agent = self._get_agent("formatter")
        formatted = await agent.process(linked, mocs, output_path)

        progress.update(task_id, completed=80)

        pipeline_data["formatted"] = formatted

        return StageResult(
            stage_name="format",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(linked) + len(mocs),
            items_output=len(formatted),
        )

    async def _stage_index(
        self, pipeline_data: dict[str, Any], progress: Progress, task_id: TaskID
    ) -> StageResult:
        """Index stage: Create master index."""
        start_time = time.time()
        formatted = pipeline_data.get("formatted", [])
        mocs = pipeline_data.get("mocs", [])
        output_path = pipeline_data["output_path"]

        progress.update(task_id, completed=20)

        agent = self._get_agent("indexer")
        index = await agent.process(formatted, mocs, output_path)

        progress.update(task_id, completed=80)

        pipeline_data["index"] = index

        return StageResult(
            stage_name="index",
            success=True,
            duration_seconds=time.time() - start_time,
            items_processed=len(formatted),
            items_output=1,
        )

    def _can_continue_after_failure(self, stage_name: str) -> bool:
        """
        Determine if pipeline can continue after a stage failure.

        Args:
            stage_name: Name of the failed stage.

        Returns:
            True if pipeline can continue, False otherwise.
        """
        # Critical stages that must succeed
        critical_stages = {"parse", "clean"}
        return stage_name not in critical_stages

    def _save_checkpoint(
        self,
        stage_name: str,
        stage_results: dict[str, StageResult],
        pipeline_data: dict[str, Any],
    ) -> None:
        """
        Save checkpoint for resume capability.

        Args:
            stage_name: Name of the completed stage.
            stage_results: Results from all completed stages.
            pipeline_data: Current pipeline state.
        """
        if not self._checkpoint_path:
            return

        try:
            # Serialize stage results
            serialized_results = {}
            for name, result in stage_results.items():
                serialized_results[name] = {
                    "stage_name": result.stage_name,
                    "success": result.success,
                    "duration_seconds": result.duration_seconds,
                    "items_processed": result.items_processed,
                    "items_output": result.items_output,
                    "errors": result.errors,
                }

            checkpoint = {
                "last_completed_stage": stage_name,
                "timestamp": datetime.now().isoformat(),
                "stage_results": serialized_results,
                "input_path": str(pipeline_data.get("input_path", "")),
                "output_path": str(pipeline_data.get("output_path", "")),
            }

            with open(self._checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2)

            self.logger.debug(f"Checkpoint saved after stage: {stage_name}")

        except Exception as e:
            self.logger.warning(f"Failed to save checkpoint: {e}")

    def _load_checkpoint(self) -> Optional[str]:
        """
        Load checkpoint for resume capability.

        Returns:
            Name of the stage to resume from, or None if no checkpoint.
        """
        if not self._checkpoint_path or not self._checkpoint_path.exists():
            return None

        try:
            with open(self._checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)

            last_stage = checkpoint.get("last_completed_stage")
            timestamp = checkpoint.get("timestamp", "unknown")

            self.console.print(
                Panel(
                    f"[yellow]Found checkpoint from {timestamp}\n"
                    f"Last completed stage: {last_stage}[/yellow]",
                    title="Resume Available",
                )
            )

            # Find next stage to resume from
            stage_names = [s[0] for s in self.STAGES]
            if last_stage in stage_names:
                idx = stage_names.index(last_stage)
                if idx + 1 < len(stage_names):
                    return stage_names[idx + 1]

            return None

        except Exception as e:
            self.logger.warning(f"Failed to load checkpoint: {e}")
            return None

    def _display_header(self, input_path: Path, output_path: Path) -> None:
        """Display pipeline header with configuration info."""
        header = Table.grid(padding=1)
        header.add_column(style="cyan", justify="right")
        header.add_column(style="white")

        header.add_row("Input:", str(input_path))
        header.add_row("Output:", str(output_path))
        header.add_row("Model:", self.config.get("api", {}).get("model", "N/A"))
        header.add_row("Stages:", str(len(self.STAGES)))

        self.console.print()
        self.console.print(
            Panel(
                header,
                title="[bold blue]Claude Obsidian Second Brain Pipeline[/bold blue]",
                border_style="blue",
            )
        )
        self.console.print()

    def _display_summary(self, result: PipelineResult) -> None:
        """Display final pipeline summary."""
        self.console.print()

        # Create summary table
        table = Table(title="Pipeline Summary", border_style="blue")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white", justify="right")

        status_text = Text()
        if result.success:
            status_text.append("SUCCESS", style="bold green")
        else:
            status_text.append("FAILED", style="bold red")

        table.add_row("Status", status_text)
        table.add_row("Stages Completed", f"{len(result.stages_completed)}/{len(self.STAGES)}")
        table.add_row("Conversations", str(result.total_conversations))
        table.add_row("Notes Generated", str(result.total_notes))
        table.add_row("MOCs Created", str(result.total_mocs))
        table.add_row("Duration", f"{result.duration_seconds:.2f}s")

        if result.errors:
            table.add_row("Errors", str(len(result.errors)))

        self.console.print(table)

        # Show errors if any
        if result.errors:
            self.console.print()
            error_panel = Panel(
                "\n".join(f"- {e}" for e in result.errors[:10]),
                title="[red]Errors[/red]",
                border_style="red",
            )
            self.console.print(error_panel)

            if len(result.errors) > 10:
                self.console.print(f"[dim]... and {len(result.errors) - 10} more errors[/dim]")

        self.console.print()


class MockAgent:
    """Mock agent for development/testing when real agents are not available."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config

    async def process(self, *args: Any, **kwargs: Any) -> Any:
        """Mock processing that returns empty results."""
        await asyncio.sleep(0.1)  # Simulate work

        if self.name == "parser":
            # Return mock conversations
            return [
                {
                    "id": f"conv_{i}",
                    "title": f"Conversation {i}",
                    "messages": [{"role": "human", "content": "Hello"}],
                }
                for i in range(3)
            ]
        elif self.name == "graph":
            # Return mock graph
            import networkx as nx

            g = nx.Graph()
            g.add_node("topic1")
            g.add_node("topic2")
            g.add_edge("topic1", "topic2")
            return g
        else:
            # Return input as output for other stages
            return args[0] if args else []


async def run_pipeline(
    input_path: Path,
    output_path: Path,
    config_path: Optional[Path] = None,
) -> PipelineResult:
    """
    Convenience function to run the pipeline.

    Args:
        input_path: Path to input file or directory.
        output_path: Path to output directory.
        config_path: Optional path to config file.

    Returns:
        PipelineResult with execution details.
    """
    config = config_path or Path("config/settings.yaml")
    orchestrator = OrchestratorAgent(config)
    return await orchestrator.run(input_path, output_path)


if __name__ == "__main__":
    # Simple test run
    import sys

    if len(sys.argv) < 2:
        print("Usage: python 10_orchestrator.py <input_path> [output_path]")
        sys.exit(1)

    input_p = Path(sys.argv[1])
    output_p = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("./output")

    result = asyncio.run(run_pipeline(input_p, output_p))
    sys.exit(0 if result.success else 1)
