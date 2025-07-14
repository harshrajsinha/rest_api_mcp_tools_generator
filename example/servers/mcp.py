from ..config.config import SciKiqConfig

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.resources import FunctionResource
from mcp.cli.claude import get_claude_config_path
from pydantic.networks import AnyUrl
import os
import sys
import logging
import asyncio
from typing import List, Union, Annotated, Optional, Tuple, Dict, Any
from functools import reduce
from operator import ior
from pathlib import Path
from typer import Typer, Option, Argument, BadParameter
from rich import console, table, print as pp
from click import Choice
from enum import StrEnum, auto
from json import load, dump as jdump

from ..tools import tools

# ----------------- Logging Setup -----------------
log = logging.getLogger("datahubhouse")
log.setLevel(logging.INFO)
if not log.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)

# ----------------- Utility Functions -----------------
def _mode() -> List[str]:
    return [tt.name for tt in tools.ToolType]

def load_config(config_file: Optional[Path]) -> SciKiqConfig:
    log.info(config_file)
    config = SciKiqConfig.from_env()
    if config_file:
        import yaml
        with open(config_file, "r") as f:
            cfg_data = yaml.safe_load(f)
        config = SciKiqConfig(
            base_url=cfg_data.get("base_url", config.base_url),
            client_key=cfg_data.get("client_key", config.client_key),
            entity_key=cfg_data.get("entity_key", config.entity_key),
            user_key=cfg_data.get("user_key", config.user_key),
        )
    return config

# ----------------- MCP Server Initialization -----------------
def init(
    config: SciKiqConfig = None,
    mode: Union[tools.ToolType, List[tools.ToolType]] = None,
) -> FastMCP:
    mcp = FastMCP("SCIKIQ", level="DEBUG")
    mode = reduce(ior, mode) if mode is not None else None
    config = config or SciKiqConfig.from_env()
    for tool in tools.get_tools(For=mode):
        tool_instance = tool(config=config)
        mcp.add_tool(
            tool_instance.invoke,
            name=tool.__name__,
            description=tool_instance.invoke.__doc__,
        )
    for resource in tools.get_resources(For=mode):
        resource_instance = resource(config=config)
        mcp.add_resource(
            FunctionResource(
                uri=AnyUrl(resource_instance.resource_path),
                name=resource.__name__,
                description=resource.__doc__,
                mime_type="application/json",
                fn=resource_instance.invoke,
            )
        )
    mcp.add_prompt(
        Prompt.from_function(tools.system_prompt, "System Prompt", "System Prompt")
    )
    return mcp

# ----------------- Typer CLI Setup -----------------
ty = Typer(context_settings=dict(help_option_names=["-h", "--help"]))

@ty.command(name="run", help="Run the SCIKIQ MCP server")
def main(
    config_file: Annotated[
        Optional[Path],
        Option("-c", "--cfg", help="The config yaml for various options"),
    ] = None,
    mode: Annotated[
        Optional[List[str]],
        Option("-m", "--mode", help="MCP server mode", click_type=Choice(_mode())),
    ] = None,
    list_tools: Annotated[
        bool, Option(help="List available tools for this mode and exit")
    ] = False,
    log_to_file: Annotated[Optional[bool], Option(help="Log to file")] = False,
):
    # Logging configuration
    log.handlers.clear()
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO if not list_tools else logging.DEBUG)

    log.info("Starting SCIKIQ MCP server...")

    # Mode handling
    if mode is not None:
        mode = [tools.ToolType[m.upper()] for m in mode]

    # Load config from file or environment
    config = load_config(config_file)

    if list_tools:
        mode_val = reduce(ior, mode) if mode is not None else None
        for tool in tools.get_tools(For=mode_val):
            print(tool.__name__)
        return

    try:
        app = init(
            config=config,
            mode=mode,
        )
        log.info("Initialized FastMCP app, starting server...")
        app.run()
    except Exception as e:
        log.exception("Failed to start the MCP server: %s", e)

# ----------------- Config CLI -----------------
tc = Typer(
    context_settings=dict(help_option_names=["-h", "--help"]),
    name="config",
    help="Configuration management",
)

class ConfigTypes(StrEnum):
    dremioai = auto()
    claude = auto()

def get_claude_config_path() -> Path:
    dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"), "Claude")
    match sys.platform:
        case "win32":
            dir = Path(Path.home(), "AppData", "Roaming", "Claude")
        case "darwin":
            dir = Path(Path.home(), "Library", "Application Support", "Claude")
    return dir / "claude_desktop_config.json"

@tc.command("list", help="Show default configuration, if it exists")
def show_default_config(
    show_filename: Annotated[bool, Option(help="Show the filename for default config file")] = False,
    type: Annotated[Optional[ConfigTypes], Option(help="The type of configuration to show", show_default=True)] = ConfigTypes.dremioai,
):
    match type:
        case ConfigTypes.dremioai:
            config = SciKiqConfig.from_env()
            if show_filename:
                pp("SCIKIQ config is loaded from environment variables or .env file.")
            else:
                pp(
                    {
                        "base_url": config.base_url,
                        "client_key": config.client_key,
                        "entity_key": config.entity_key,
                        "user_key": config.user_key,
                    }
                )
        case ConfigTypes.claude:
            cc = get_claude_config_path()
            pp(f"Default config file: '{cc!s}' (exists = {cc.exists()!s})")
            if not show_filename:
                jdump(load(cc.open()), sys.stdout, indent=2)

cc = Typer(
    context_settings=dict(help_option_names=["-h", "--help"]),
    name="create",
    help="Create SCIKIQ or LLM configuration files",
)
tc.add_typer(cc)

def create_default_datahubhouse_config() -> Dict[str, Any]:
    return {
        "base_url": "http://localhost:8000/api",
        "client_key": "your_client_key",
        "entity_key": "your_entity_key",
        "user_key": "your_user_key",
    }

def create_default_config_helper(dry_run: bool):
    config_path = Path(os.getcwd()) / "datahubhouse_config.yaml"
    config_data = create_default_datahubhouse_config()
    if dry_run:
        pp(config_data)
        return
    if not config_path.parent.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w") as f:
        import yaml
        yaml.safe_dump(config_data, f)
        pp(f"Created default config file: {config_path!s}")

@cc.command("datahubhouse", help="Create a default configuration file for SCIKIQ")
def create_default_config(
    dry_run: Annotated[
        bool, Option(help="Dry run, do not overwrite the config file. Just print it")
    ] = False,
):
    create_default_config_helper(dry_run)

# ----------------- Tools CLI -----------------
tl = Typer(
    context_settings=dict(help_option_names=["-h", "--help"]),
    name="tools",
    help="Support for testing tools directly",
)

@tl.command(
    name="list",
    help="List the available tools",
    context_settings=dict(help_option_names=["-h", "--help"]),
)
def tools_list(
    mode: Annotated[
        Optional[List[str]],
        Option("-m", "--mode", help="MCP server mode", click_type=Choice(_mode())),
    ] = [tools.ToolType.FOR_SCIKIQ.name],  # <-- FIXED: Use FOR_SCIKIQ, not FOR_SELF
):
    mode = reduce(ior, [tools.ToolType[m.upper()] for m in mode])
    tab = table.Table(
        table.Column("Tool", justify="left", style="cyan"),
        "Description",
        "For",
        title="Tools list",
        show_lines=True,
    )
    for tool in tools.get_tools(For=mode):
        For = tools.get_for(tool)
        desc = tool.invoke.__doc__.strip() if getattr(tool.invoke, "__doc__", None) else "No Description"
        for_name = For.name if For is not None else "Unknown"
        tab.add_row(tool.__name__, desc, for_name)
    console.Console().print(tab)

@tl.command(
    name="invoke",
    help="Execute an available tools",
    context_settings=dict(help_option_names=["-h", "--help"]),
)
def tools_exec(
    tool: Annotated[str, Option("-t", "--tool", help="The tool to execute")],
    config_file: Annotated[
        Optional[Path],
        Option("-c", "--cfg", help="The config yaml for various options"),
    ] = None,
    args: Annotated[
        Optional[List[str]],
        Argument(help="The arguments to pass to the tool (arg=value ...)"),
    ] = None,
):
    def _to_kw(arg: str) -> Tuple[str, str]:
        if "=" not in arg:
            raise BadParameter(f"Argument {arg} is not in the form arg=value")
        return tuple(arg.split("=", 1))

    config = load_config(config_file)
    if args is None:
        args = {}
    elif isinstance(args, str):
        args = [args]
    args = dict(map(_to_kw, args))
    for_all = reduce(ior, tools.ToolType.__members__.values())
    all_tools = {t.__name__: t for t in tools.get_tools(for_all)}

    if selected := all_tools.get(tool):
        try:
            tool_instance = selected(config=config)
            # Add logging to show which tool is being invoked and with what args
            log.info(f"Invoking tool: {tool} with args: {args}")
            result = asyncio.run(tool_instance.invoke(**args))
            pp(result)
        except Exception as e:
            log.exception(f"Error invoking tool {tool}: {e}")
    else:
        log.error(f"Tool {tool} not found in available tools: {list(all_tools.keys())}")
        raise BadParameter(f"Tool {tool} not found")

# Add sub-commands to main Typer app
ty.add_typer(tl)
ty.add_typer(tc)

def cli():
    ty()

if __name__ == "__main__":
    cli()
