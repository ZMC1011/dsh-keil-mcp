"""Build control tools (blueprint §6.1-A/B)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from ..core.error_parser import UV4LogParser, explain_error
from ..core.project_utils import count_source_files
from ..core.build_progress import BuildProgressMonitor
from ..core.uv4_runner import BuildRegistry
from ..models import BuildResult
from .context import get_context


# ---------------------------------------------------------------------------
# build_project — compile with realtime progress (blueprint §7.1)
# ---------------------------------------------------------------------------
async def build_project(project: str, target: Optional[str] = None,
                        timeout_seconds: int = 120, stream_progress: bool = True,
                        clean: bool = False, rebuild: bool = False) -> dict:
    """Build a Keil project with UV4 -b (or -r rebuild / -c clean).

    Args:
        project: path to .uvprojx (absolute or relative to default_project_dir)
        target: target name (default: first target in project)
        timeout_seconds: build timeout (default 120)
        stream_progress: tail the log for realtime progress (percent/phase)
        clean: run UV4 -c instead of -b
        rebuild: run UV4 -r (full rebuild) instead of -b
    Returns:
        {status: ok|error|canceled|not_found, returncode, build_log, errors[], summary, progress?}
    """
    ctx = get_context()
    proj = _resolve_project(project)
    if not proj.exists():
        return {"status": "not_found", "returncode": None, "build_log": "",
                "errors": [], "summary": None,
                "error": f"project not found: {proj}"}

    log_path = proj.parent / "build.log"
    total = count_source_files(proj, target)
    bid = ctx.builds.create(str(proj), target or "", log_path)
    monitor = BuildProgressMonitor(bid, log_path, total,
                                   flush_wait=float(ctx.config.build.tail_flush_wait))
    ctx.builds.set(bid, state=monitor.state)

    def _run():
        proc = ctx.uv4.build(str(proj), target=target, clean=clean, rebuild=rebuild,
                             log_path=log_path, timeout=timeout_seconds, progress=monitor)
        return proc

    try:
        proc = await asyncio.to_thread(_run)
    except TimeoutError as e:
        ctx.builds.set(bid, state=monitor.state)
        return {"status": "error", "returncode": None, "build_log": str(e),
                "errors": [], "summary": None, "build_id": bid}
    except FileNotFoundError as e:
        return {"status": "error", "returncode": None, "build_log": str(e),
                "errors": [], "summary": None, "build_id": bid}

    log = log_path.read_text(encoding="utf-8", errors="replace")
    parser = UV4LogParser(max_errors=ctx.config.error.max_errors)
    errors, summary = parser.parse(log)
    ok = proc.returncode in (0, 1) and summary.errors == 0
    result = BuildResult(status="ok" if ok else "error", returncode=proc.returncode,
                         build_log=log, errors=errors, summary=summary)
    monitor.state.status = "done"
    ctx.builds.set(bid, state=monitor.state)
    out = result.to_dict()
    out["build_id"] = bid
    if stream_progress:
        out["progress"] = monitor.state.to_dict()
    return out


# ---------------------------------------------------------------------------
# build_progress_status / build_cancel
# ---------------------------------------------------------------------------
async def build_progress_status(build_id: str) -> dict:
    """Query the live progress of a running build."""
    ctx = get_context()
    entry = ctx.builds.get(build_id)
    if not entry or entry.get("state") is None:
        return {"success": False, "error": f"unknown build_id {build_id}"}
    return {"success": True, **entry["state"].to_dict()}


async def build_cancel(build_id: str) -> dict:
    """Request cancellation of a running build."""
    ctx = get_context()
    ok = ctx.builds.request_cancel(build_id)
    entry = ctx.builds.get(build_id)
    state = entry["state"] if entry else None
    if state is not None:
        state.status = "canceled"
    return {"success": ok, "build_id": build_id}


# ---------------------------------------------------------------------------
# parse_build_errors / explain_build_error (blueprint §6.1-B)
# ---------------------------------------------------------------------------
async def parse_build_errors(log_path: Optional[str] = None,
                             log_content: Optional[str] = None) -> dict:
    """Parse a UV4 build log into structured errors/warnings (blueprint §7.2).

    Args:
        log_path: path to build log file, OR
        log_content: raw log text
    Returns:
        {errors[], warnings[], summary{success, errors, warnings, code_size, ...}}
    """
    if log_content:
        log = log_content
    elif log_path:
        p = Path(log_path)
        if not p.exists():
            return {"success": False, "error": f"log not found: {p}"}
        log = p.read_text(encoding="utf-8", errors="replace")
    else:
        return {"success": False, "error": "provide log_path or log_content"}
    parser = UV4LogParser()
    errors, summary = parser.parse(log)
    return {
        "success": True,
        "errors": [e.to_dict() for e in errors if e.severity == "error"],
        "warnings": [e.to_dict() for e in errors if e.severity == "warning"],
        "summary": summary.to_dict(),
    }


async def explain_build_error(error_code: str, message: str = "",
                              file: str = "", line: Optional[int] = None) -> dict:
    """Map a Keil/armclang error code to explanation, causes and fixes."""
    return explain_error(error_code, message, file, line or 0)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _resolve_project(project: str) -> Path:
    p = Path(project)
    if not p.is_absolute():
        ctx = get_context()
        p = Path(ctx.config.keil.default_project_dir or ".") / project
    return p if p.suffix.lower() == ".uvprojx" else p.with_suffix(".uvprojx")
