"""Per-probe exclusive lease + queueing (blueprint §7.5)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import filelock


class ProbeLease:
    """Serializes probe access per probe_id: asyncio lock + cross-process file lock."""

    def __init__(self, lock_dir: Path):
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_dir = Path(lock_dir)

    @asynccontextmanager
    async def acquire(self, probe_id: str = "default"):
        lock = self._locks.setdefault(probe_id, asyncio.Lock())
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        async with lock:
            with filelock.FileLock(str(self._lock_dir / f"{probe_id}.lock")):
                yield
