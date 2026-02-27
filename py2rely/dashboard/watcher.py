"""Sentinel file watcher for relion-ui.

Primary strategy: watchdog inotify/kqueue observer.
Fallback: asyncio polling loop (required for NFS/Lustre/GPFS which don't support inotify).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable

log = logging.getLogger("dashboard.watcher")

# Files whose creation or deletion signals a pipeline state change.
_WATCHED_NAMES = {"RELION_JOB_EXIT_SUCCESS", "PIPELINER_JOB_EXIT_SUCCESS", "default_pipeline.star"}


class PipelineWatcher:
    def __init__(
        self,
        project_dir: Path,
        poll_interval: int,
        on_change: Callable[[], Awaitable[None]],
    ) -> None:
        self.project_dir = project_dir
        self.poll_interval = poll_interval
        self.on_change = on_change
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        try:
            self._start_watchdog()
            log.info("watchdog observer started for %s", self.project_dir)
            # Keep this coroutine alive; watchdog runs in its own thread.
            while True:
                await asyncio.sleep(3600)
        except Exception as exc:
            log.warning("watchdog unavailable (%s), falling back to polling every %ss", exc, self.poll_interval)
            await self._poll_loop()

    def _start_watchdog(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        watcher = self

        class _Handler(FileSystemEventHandler):
            def _notify(self) -> None:
                if watcher._loop is not None:
                    asyncio.run_coroutine_threadsafe(watcher.on_change(), watcher._loop)

            def on_created(self, event) -> None:  # type: ignore[override]
                if not event.is_directory and Path(event.src_path).name in _WATCHED_NAMES:
                    self._notify()

            def on_deleted(self, event) -> None:  # type: ignore[override]
                if not event.is_directory and Path(event.src_path).name in _WATCHED_NAMES:
                    self._notify()

        observer = Observer()
        observer.schedule(_Handler(), str(self.project_dir), recursive=True)
        observer.start()

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self.poll_interval)
            await self.on_change()
