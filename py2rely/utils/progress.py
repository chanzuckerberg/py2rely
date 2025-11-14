"""
Progress bar utility using Rich.

Example:
    from saber.utils.progress import _progress

    for key in _progress(train_keys, description="My Process Description.."):
        ...
"""

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.console import Console

# Minimal helper to get a shared Console without top-level Rich dependency.
def get_console():
    return Console()

def _progress(iterable, description="Processing"):
    """
    Wrap an iterable with a Rich progress bar.

    Args:
        iterable: Any iterable object (e.g., list, generator).
        description: Text label to display above the progress bar.

    Yields:
        Each item from the iterable, while updating the progress bar.

    Example:
        for x in _progress(range(10), "Doing work"):
            time.sleep(0.5)
    """

    console = Console()

    # The generator itself yields items while advancing the progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]{description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        transient=False,
        console=console,
    ) as progress:
        task = progress.add_task(description, total=len(iterable))
        for item in iterable:
            yield item
            progress.advance(task)