"""Project & environment tools: doctor / discover / configure (blueprint §6.2)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from ..config import find_uv4, uv4_exists
from ..core.project_utils import discover_projects, parse_project
from .context import get_context


async def keil_doctor() -> dict:
    """Check the Keil environment: UV4.exe, pyocd, packs, config."""
    ctx = get_context()
    uv4 = find_uv4(ctx.config)
    checks = {
        "uv4_exists": uv4_exists(ctx.config),
        "uv4_path": uv4,
        "pyocd_installed": _import_ok("pyocd"),
        "mcp_installed": _import_ok("mcp"),
        "config_path": ctx.config.config_path or "(defaults)",
        "default_project_dir": ctx.config.keil.default_project_dir or "(not set)",
    }
    if checks["pyocd_installed"]:
        try:
            from pyocd.core.helpers import ConnectHelper
            probes = ConnectHelper.get_all_connected_probes(blocking=False)
            checks["probes"] = [
                {"name": getattr(p, "product_name", "") or str(p),
                 "unique_id": getattr(p, "unique_id", "") or ""}
                for p in (probes or [])]
            checks["probe_count"] = len(checks["probes"])
        except Exception as e:
            checks["probes"] = []
            checks["probe_error"] = str(e)
    ok = checks["uv4_exists"] and checks["pyocd_installed"]
    checks["status"] = "OK" if ok else "WARN"
    return checks


async def discover_keil_projects(directory: Optional[str] = None,
                                 recursive: bool = True) -> dict:
    """Discover *.uvprojx Keil projects under a directory."""
    ctx = get_context()
    root = directory or ctx.config.keil.default_project_dir or "."
    root_p = Path(root)
    if not root_p.exists():
        return {"success": False, "error": f"directory not found: {root_p}"}
    projects = discover_projects(root_p, recursive=recursive)
    return {"success": True, "directory": str(root_p),
            "project_count": len(projects), "projects": projects}


async def configure_keil_project(project: str, target: Optional[str] = None) -> dict:
    """Parse a Keil project: targets, device, pack, groups, source files.

    Use before building to pick the right target / confirm the device.
    """
    ctx = get_context()
    p = Path(project)
    if not p.is_absolute():
        p = Path(ctx.config.keil.default_project_dir or ".") / project
    if p.suffix.lower() != ".uvprojx":
        p = p.with_suffix(".uvprojx")
    if not p.exists():
        return {"success": False, "error": f"project not found: {p}"}
    try:
        info = parse_project(p, target)
        d = info.to_dict()
        d["success"] = True
        return d
    except Exception as e:
        return {"success": False, "error": str(e)}


def _import_ok(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False
