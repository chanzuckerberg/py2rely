from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Any, Optional


def run_threaded(
    items: Iterable[Any],
    worker: Callable[[Any], Any],
    *,
    max_workers: Optional[int] = None,
    description: str = "Working",
    total: Optional[int] = None,  # set to len(items) if you have it
    get_status: Callable[[Any], str] = lambda r: r if isinstance(r, str) else r[0],
    on_status: Optional[Callable[[Any, str, Any], None]] = None,
    on_error: Optional[Callable[[Any, Exception], None]] = None,
    progress: bool = True,
) -> dict[str, int]:
    """
    Threaded runner with robust progress reporting.

    - If tqdm is installed, it will show a progress bar.
    - Otherwise it falls back to py2rely.utils.progress._progress if available.
    - Otherwise no progress indicator.
    """
    items = list(items)  # to support len() and multiple iteration
    if total is None:
        total = len(items)

    # Choose progress wrapper
    wrap = None
    if progress:
        try:
            from tqdm.auto import tqdm  # works in notebooks + terminals
            wrap = lambda it: tqdm(it, total=total, desc=description)
        except Exception:
            try:
                from py2rely.utils.progress import _progress
                wrap = lambda it: _progress(it, description=description)
            except Exception:
                wrap = None

    counts: dict[str, int] = {"error": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(worker, item): item for item in items}
        iterator = as_completed(futures)
        if wrap is not None:
            iterator = wrap(iterator)

        for fut in iterator:
            item = futures[fut]
            try:
                result = fut.result()
                status = get_status(result)
                counts[status] = counts.get(status, 0) + 1
                if on_status is not None:
                    on_status(item, status, result)
            except Exception as e:
                counts["error"] = counts.get("error", 0) + 1
                if on_error is not None:
                    on_error(item, e)
                else:
                    print(f"[Error]: Failed on {item}: {e}")

    return counts

def warn_missing_run(ur: str, status: str, result: Any):
    """
    Warn about a missing run in the Copick root for a given session.
    """
    if status == "missing_run":
        mysession = ur.split('_')[0]
        myrun = '_'.join(ur.split('_')[1:])
        print(f'[Warning]: Run {myrun + suffix} not found in Copick root for session {mysession}. Skipping.')