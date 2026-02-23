"""
Environment load commands for py2rely (python_load, relion_load).

Stored under the installed package path: py2rely/envs/env_config.json.
- If envs/ is missing when a command needs these values, the user is prompted once.
- Users can also set or update values via: py2rely config
Pressing Enter means "no module load" (empty) for that slot.
"""

import json
from pathlib import Path
from typing import Any, Optional

CONFIG_FILENAME = "env_config.json"
CONFIG_KEYS = ("python_load", "relion_load")


def get_config_dir() -> Path:
    """Path to the envs directory inside the installed py2rely package."""
    import py2rely
    return Path(py2rely.__path__[0]) / "envs"


def get_config_path() -> Path:
    """Path to the env config file."""
    return get_config_dir() / CONFIG_FILENAME


def envs_folder_exists() -> bool:
    """True if py2rely/envs exists."""
    return get_config_dir().exists()


def load_config() -> dict[str, Any]:
    """Load config from disk. Returns empty dict if missing or invalid."""
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(config: dict[str, Any]) -> None:
    """Write config to disk (creates envs dir if needed)."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    with open(get_config_path(), "w") as f:
        json.dump(config, f, indent=2)


def _prompt_multiline(instruction: str, empty_means_keep_current: Optional[str] = None) -> str:
    """
    Read multiple lines from stdin until the user enters an empty line.
    - First line empty (Enter only) = return "" (none), or return empty_means_keep_current if given.
    - Otherwise collect lines; one empty line ends input.
    Returns the joined text with real newlines. No need to type \\n.
    """
    if instruction:
        try:
            from rich.console import Console
        except ImportError:
            Console = None
        if Console:
            Console().print(instruction)
        else:
            print(instruction)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            if not lines:
                return empty_means_keep_current if empty_means_keep_current is not None else ""
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _prompt_for_load_commands() -> dict[str, str]:
    """Ask user for python_load and relion_load; supports multi-line (empty line to finish)."""
    try:
        from rich.console import Console
    except ImportError:
        Console = None

    if Console:
        Console().print("[bold cyan]py2rely env setup[/bold cyan]")
        Console().print("Values saved to: [dim]{}[/dim]\n".format(get_config_path()))

    # python_load: allow single or multi-line
    if Console:
        Console().print("[bold]python_load[/bold] (e.g. ml anaconda, or multi-line; [dim]empty line to finish, first empty = none[/dim])")
    else:
        print("python_load (e.g. ml anaconda, or multi-line; empty line to finish, first empty = none)")
    python_load = _prompt_multiline("")

    # relion_load: multi-line so users can paste a full script
    if Console:
        Console().print("[bold]relion_load[/bold] (e.g. ml relion/5.0 or paste a script; [dim]empty line to finish, first empty = none[/dim])")
    else:
        print("relion_load (e.g. ml relion/5.0 or paste a script; empty line to finish, first empty = none)")
    relion_load = _prompt_multiline("")

    return {
        "python_load": python_load,
        "relion_load": relion_load,
    }


def ensure_env_config(prompt_if_missing: bool = True) -> dict[str, Any]:
    """
    Load config. If the envs folder does not exist and prompt_if_missing is True,
    prompt for python_load and relion_load (Enter = no module load), create envs,
    save, and return. Otherwise load from file and return.
    """
    if not envs_folder_exists():
        if prompt_if_missing:
            config = _prompt_for_load_commands()
            save_config(config)
            C = _Console()
            if C is not None:
                C().print("[green]Config saved.[/green]\n")
            return config
        return {}
    return load_config()


def _Console():
    try:
        from rich.console import Console
        return Console
    except ImportError:
        return None


def get_load_commands(prompt_if_missing: bool = True) -> tuple[str, str]:
    """
    Return (python_load, relion_load). If envs folder is missing and
    prompt_if_missing is True, prompts once and saves. Empty string means
    no module load for that slot.
    """
    config = ensure_env_config(prompt_if_missing=prompt_if_missing)
    return (
        (config.get("python_load") or "").strip(),
        (config.get("relion_load") or "").strip(),
    )


def config_cli():
    """CLI: py2rely config — show and/or update python_load and relion_load."""
    import rich_click as click
    from rich.console import Console
    from rich.table import Table

    @click.command(name="config")
    @click.option(
        "--show-only",
        is_flag=True,
        help="Only show current config; do not prompt to update.",
    )
    def _config(show_only: bool):
        """Show or update env load commands (python_load, relion_load). Enter = no module load."""
        console = Console()
        path = get_config_path()

        if show_only:
            if not path.exists():
                console.print("[yellow]No config yet.[/yellow] Run [bold]py2rely config[/bold] to set.")
                return
            cfg = load_config()
            table = Table(show_header=True, header_style="bold")
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")
            for k in CONFIG_KEYS:
                table.add_row(k, (cfg.get(k) or "(none)")[:80])
            console.print(f"Config: [dim]{path}[/dim]\n")
            console.print(table)
            return

        # Ensure envs exists; prompt for each (multi-line; empty line to finish)
        get_config_dir().mkdir(parents=True, exist_ok=True)
        current = load_config()

        console.print("[bold cyan]Update env load commands[/bold cyan]")
        console.print("Multi-line OK; [dim]empty line to finish. First line empty = keep current.[/dim]\n")

        cur_py = (current.get("python_load") or "").strip()
        cur_rel = (current.get("relion_load") or "").strip()

        console.print("[bold]python_load[/bold] (current: first 60 chars shown)")
        console.print("[dim]%s[/dim]" % (cur_py[:60] + "..." if len(cur_py) > 60 else cur_py or "(none)"))
        python_load = _prompt_multiline("", empty_means_keep_current=cur_py)

        console.print("[bold]relion_load[/bold] (current: first 60 chars shown)")
        console.print("[dim]%s[/dim]" % (cur_rel[:60] + "..." if len(cur_rel) > 60 else cur_rel or "(none)"))
        relion_load = _prompt_multiline("", empty_means_keep_current=cur_rel)

        config = {
            "python_load": python_load,
            "relion_load": relion_load,
        }
        save_config(config)
        console.print("[green]Config saved.[/green]\n")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for k in CONFIG_KEYS:
            table.add_row(k, (config.get(k) or "(none)")[:80])
        console.print(table)

    return _config
