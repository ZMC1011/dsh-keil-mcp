"""Official UV4 debug channel tools (blueprint §6.1-D)."""
from __future__ import annotations

from typing import List, Optional

from ..core.uv4_debug import build_custom_ini
from .context import get_context


async def uv4_debug_session(project: str, target: Optional[str] = None,
                            ini_path: Optional[str] = None,
                            reset: bool = True, breakpoint: str = "main",
                            steps: int = 0, dump_vars: Optional[List[str]] = None,
                            timeout_seconds: int = 120) -> dict:
    """Run an official Keil debug session via UV4 -d + a generated .ini script.

    The debugger runs headless: sets a breakpoint, resets, runs, optionally
    steps, and prints variable values. Output is captured from the session log.

    Args:
        project: path to .uvprojx
        target: target name (default first target)
        ini_path: custom .ini script path (overrides generated script)
        reset: reset target before running
        breakpoint: symbol/line to break at ("" = none)
        steps: extra single-step count after hitting the breakpoint
        dump_vars: variable names to print (e.g. ["i", "adc_value"])
        timeout_seconds: session timeout
    """
    ctx = get_context()
    proj = _resolve(project)
    if not proj.exists():
        return {"success": False, "error": f"project not found: {proj}"}
    if ini_path:
        from pathlib import Path
        ini = Path(ini_path)
        if not ini.exists():
            return {"success": False, "error": f"ini not found: {ini}"}
    else:
        ini_path = None
    try:
        script = None if ini_path else build_custom_ini(
            reset=reset, breakpoint=breakpoint, steps=steps, dump_vars=dump_vars)
        return await _run(proj, target, ini_path, script, timeout_seconds)
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _run(proj, target, ini_path, script, timeout):
    ctx = get_context()
    import asyncio
    return await asyncio.to_thread(
        ctx.debug_sessions.start, str(proj), target, script, ini_path, timeout)


async def uv4_debug_dde(session_id: str) -> dict:
    """Read the output of a UV4 -d debug session (session output channel)."""
    ctx = get_context()
    return ctx.debug_sessions.get_output(session_id)


def _resolve(project: str):
    from pathlib import Path
    p = Path(project)
    if not p.is_absolute():
        ctx = get_context()
        p = Path(ctx.config.keil.default_project_dir or ".") / project
    return p if p.suffix.lower() == ".uvprojx" else p.with_suffix(".uvprojx")
