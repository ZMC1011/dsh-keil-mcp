"""Shared server state: config, editors, registry, leases, execution boundary."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Optional

from ..config import AppConfig
from ..core.probe_lease import ProbeLease
from ..core.source_editor import SourceEditor
from ..core.uv4_debug import UV4DebugSession
from ..core.uv4_runner import BuildRegistry, UV4Runner


class ServerContext:
    """One shared context per server process (singleton)."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = AppConfig.load(config_path)
        self.workdir = Path(self.config.keil.default_project_dir or ".")
        self.uv4 = UV4Runner(self.config.keil.uv4_path)
        self.editor = SourceEditor(
            backup_dir=self.config.source.backup_dir,
            allow_paths=self.config.source.allow_paths or None)
        self.builds = BuildRegistry()
        self.debug_sessions = UV4DebugSession(self.uv4, self.config.debug.uv4_debug_ini_dir)
        self.lease = ProbeLease(Path(self.config.probe_lease.lock_dir))
        # execution boundary: one worker slot per session
        self.execution_lock = asyncio.Lock()
        self._thread_pool = None

    # ---- execution boundary helpers (McuBuddy Execution Boundary style) ----
    def executor(self):
        if self._thread_pool is None:
            import concurrent.futures
            self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        return self._thread_pool


_ctx: Optional[ServerContext] = None


def get_context() -> ServerContext:
    global _ctx
    if _ctx is None:
        _ctx = ServerContext()
    return _ctx


def set_context(ctx: ServerContext) -> None:
    global _ctx
    _ctx = ctx
