"""FastMCP server main (blueprint §3 / §5.4 / §9.1).

Run:  python -m keil_mcp_server            (stdio transport)
      python -m keil_mcp_server --check     (environment self-test)
      python -m keil_mcp_server --tools     (list registered tools)
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import AppConfig
from .tools.context import ServerContext, get_context, set_context

log = logging.getLogger("keil-mcp")

# read-only tools may run concurrently; everything else serializes on the
# session execution lock (McuBuddy Execution Boundary, blueprint §3).
_READONLY_TOOLS = {
    "build_progress_status", "parse_build_errors", "explain_build_error",
    "source_read", "source_search", "keil_doctor", "discover_keil_projects",
    "configure_keil_project", "probe_read_registers", "probe_read_memory",
    "read_rtt_log", "uv4_debug_dde", "verify_flash", "probe_connect",
}


def _execution_boundary(fn):
    """Wrap a tool: readonly -> concurrent; else session execution lock.

    All heavy work runs via asyncio.to_thread; asyncio.shield protects against
    client-side cancellation races.
    """
    name = getattr(fn, "__name__", "?")

    async def wrapper(*args, **kwargs):
        ctx = get_context()
        if name in _READONLY_TOOLS:
            return await asyncio.shield(fn(*args, **kwargs))
        async with ctx.execution_lock:
            return await asyncio.shield(fn(*args, **kwargs))

    wrapper.__name__ = name
    wrapper.__doc__ = fn.__doc__
    return wrapper


def register_tools(mcp: FastMCP) -> None:
    """Register every MCP tool (blueprint §6)."""
    from .tools.build_tools import (
        build_cancel, build_project, build_progress_status,
        explain_build_error, parse_build_errors,
    )
    from .tools.source_tools import source_edit, source_read, source_search
    from .tools.debug_tools import uv4_debug_dde, uv4_debug_session
    from .tools.project_tools import (
        configure_keil_project, discover_keil_projects, keil_doctor,
    )
    from .tools.flash_tools import erase_flash, flash_firmware, verify_flash
    from .tools.probe_tools import (
        continue_target, probe_connect, probe_disconnect, probe_halt,
        probe_read_memory, probe_read_registers, probe_resume, probe_step,
        read_rtt_log, set_breakpoint,
    )

    tools = {
        # build control (blueprint §6.1-A)
        "build_project": build_project,
        "build_progress_status": build_progress_status,
        "build_cancel": build_cancel,
        # error parsing (§6.1-B)
        "parse_build_errors": parse_build_errors,
        "explain_build_error": explain_build_error,
        # source editing (§6.1-C)
        "source_read": source_read,
        "source_edit": source_edit,
        "source_search": source_search,
        # official debug channel (§6.1-D)
        "uv4_debug_session": uv4_debug_session,
        "uv4_debug_dde": uv4_debug_dde,
        # project & environment
        "keil_doctor": keil_doctor,
        "discover_keil_projects": discover_keil_projects,
        "configure_keil_project": configure_keil_project,
        # flash (persistent ops require confirm=True)
        "flash_firmware": flash_firmware,
        "erase_flash": erase_flash,
        "verify_flash": verify_flash,
        # probe debug
        "probe_connect": probe_connect,
        "probe_disconnect": probe_disconnect,
        "probe_halt": probe_halt,
        "probe_resume": probe_resume,
        "probe_step": probe_step,
        "set_breakpoint": set_breakpoint,
        "continue_target": continue_target,
        "probe_read_registers": probe_read_registers,
        "probe_read_memory": probe_read_memory,
        "read_rtt_log": read_rtt_log,
    }
    for name, fn in tools.items():
        mcp.tool()(fn)
    log.info("registered %d tools", len(tools))


def build_app(config_path: Optional[str] = None) -> FastMCP:
    cfg = AppConfig.load(config_path)
    set_context(ServerContext(config_path))
    mcp = FastMCP(
        "keil5-mcp",
        log_level=cfg.server.log_level.upper(),
    )
    register_tools(mcp)

    @mcp.tool()
    async def keil_version() -> dict:
        """Return the keil5-mcp server version and available tool count."""
        ctx = get_context()
        return {"name": "keil5-mcp", "version": __version__,
                "tool_count": 27, "config": ctx.config.config_path or "(defaults)"}

    return mcp


async def _self_check() -> int:
    """--check: environment self test without starting the MCP server."""
    from .tools.project_tools import keil_doctor
    doc = await keil_doctor()
    print("=== keil5-mcp environment check ===")
    for k, v in doc.items():
        print(f"  {k}: {v}")
    ok = doc.get("uv4_exists") and doc.get("pyocd_installed")
    print("RESULT:", "OK" if ok else "WARN (UV4.exe or pyocd missing — server still starts, build/flash tools will report clear errors)")
    return 0 if ok else 1


def run_server(argv: Optional[list] = None) -> int:
    argv = argv or sys.argv[1:]
    # MCP stdio transport must emit valid UTF-8 regardless of Windows console
    # codepage (otherwise Chinese tool output corrupts JSON-RPC frames).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "--check" in argv:
        return asyncio.run(_self_check())
    if "--tools" in argv:
        import json
        cfg = AppConfig.load()
        from .tools.context import ServerContext
        set_context(ServerContext())
        mcp = build_app()
        # FastMCP keeps tool registry internally; introspect via _tool_manager
        try:
            names = sorted(mcp._tool_manager._tools.keys())
            print(json.dumps(names, indent=2))
        except Exception:
            print("tool introspection not available; register_tools lists 27 tools")
        return 0
    mcp = build_app()
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_server())
