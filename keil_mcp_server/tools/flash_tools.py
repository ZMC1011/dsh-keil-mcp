"""Flash tools: UV4 -f (official) with pyOCD fallback (blueprint §6.2 / §7.5).

Safety (blueprint §13): flash/erase are persistent destructive operations and
REQUIRE confirm=True. Always identify target + image + recovery method first.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config import uv4_exists
from .context import get_context


async def flash_firmware(project: str, target: Optional[str] = None,
                         image: Optional[str] = None, backend: str = "auto",
                         probe_id: Optional[str] = None,
                         confirm: bool = False, timeout_seconds: int = 120) -> dict:
    """Flash firmware to the target chip.

    Preferred path: UV4 -f <project> (Keil official flash download, uses the
    project's configured Flash algorithm). Fallback: pyocd load <image>.
    Requires confirm=True (persistent destructive operation).

    Args:
        project: .uvprojx path (for UV4 -f) — required unless image is given
        target: target name for UV4 -f
        image: firmware image (axf/hex/bin) for the pyocd path
        backend: "uv4" | "pyocd" | "auto"
        probe_id: pyOCD probe unique id (optional)
        confirm: MUST be True to actually flash
    """
    if not confirm:
        return {"success": False,
                "error": "refusing to flash without confirm=True (persistent destructive operation). "
                         "Verify target chip, image and recovery method first."}
    ctx = get_context()

    # pick backend
    if backend == "auto":
        use_uv4 = bool(project) and uv4_exists(ctx.config) and image is None
        backend = "uv4" if use_uv4 else "pyocd"

    if backend == "uv4":
        if not project:
            return {"success": False, "error": "project required for UV4 -f backend"}
        p = Path(project)
        if not p.is_absolute():
            p = Path(ctx.config.keil.default_project_dir or ".") / project
        if p.suffix.lower() != ".uvprojx":
            p = p.with_suffix(".uvprojx")
        if not p.exists():
            return {"success": False, "error": f"project not found: {p}"}
        log_path = p.parent / "flash.log"

        async with ctx.lease.acquire(probe_id or "default"):
            def _run():
                return ctx.uv4.flash(str(p), target=target, log_path=log_path,
                                     timeout=timeout_seconds)
            try:
                proc = await asyncio.to_thread(_run)
            except FileNotFoundError as e:
                return {"success": False, "error": str(e)}
        log = log_path.read_text(encoding="utf-8", errors="replace")
        ok = proc.returncode == 0 and "Verify OK" in log
        return {"success": ok, "backend": "uv4", "returncode": proc.returncode,
                "log": log[-6000:],
                "detail": "Verify OK in log" if "Verify OK" in log else "no 'Verify OK' marker found"}

    # pyocd backend
    pyocd = shutil.which("pyocd")
    if not pyocd:
        return {"success": False, "error": "pyocd CLI not found on PATH"}
    if not image:
        # try to derive .axf from project build output
        derived = _find_axf(project)
        if derived:
            image = str(derived)
        else:
            return {"success": False, "error": "image (axf/hex/bin) required for pyocd backend"}
    img = Path(image)
    if not img.exists():
        return {"success": False, "error": f"image not found: {img}"}
    cmd = [pyocd, "load", str(img)]
    if probe_id:
        cmd += ["-u", probe_id]
    async with ctx.lease.acquire(probe_id or "default"):
        try:
            r = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"pyocd load timed out after {timeout_seconds}s"}
    out = (r.stdout or "") + (r.stderr or "")
    return {"success": r.returncode == 0, "backend": "pyocd", "returncode": r.returncode,
            "output": out[-6000:]}


async def erase_flash(probe_id: Optional[str] = None, chip: str = "",
                      confirm: bool = False, timeout_seconds: int = 120) -> dict:
    """Erase the target chip flash (pyocd erase -c). Requires confirm=True."""
    if not confirm:
        return {"success": False,
                "error": "refusing to erase without confirm=True (persistent destructive operation)."}
    ctx = get_context()
    pyocd = shutil.which("pyocd")
    if not pyocd:
        return {"success": False, "error": "pyocd CLI not found on PATH"}
    cmd = [pyocd, "erase", "-c"]
    if probe_id:
        cmd += ["-u", probe_id]
    if chip:
        cmd += ["-t", chip]
    async with ctx.lease.acquire(probe_id or "default"):
        try:
            r = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"pyocd erase timed out after {timeout_seconds}s"}
    out = (r.stdout or "") + (r.stderr or "")
    return {"success": r.returncode == 0, "returncode": r.returncode, "output": out[-6000:]}


async def verify_flash(image: str, probe_id: Optional[str] = None,
                       timeout_seconds: int = 120) -> dict:
    """Verify firmware on chip against an image (pyocd verify)."""
    ctx = get_context()
    pyocd = shutil.which("pyocd")
    if not pyocd:
        return {"success": False, "error": "pyocd CLI not found on PATH"}
    img = Path(image)
    if not img.exists():
        return {"success": False, "error": f"image not found: {img}"}
    cmd = [pyocd, "verify", str(img)]
    if probe_id:
        cmd += ["-u", probe_id]
    async with ctx.lease.acquire(probe_id or "default"):
        try:
            r = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"pyocd verify timed out after {timeout_seconds}s"}
    out = (r.stdout or "") + (r.stderr or "")
    return {"success": r.returncode == 0, "returncode": r.returncode, "output": out[-6000:]}


def _find_axf(project: str) -> Optional[Path]:
    p = Path(project)
    if p.suffix.lower() != ".uvprojx":
        return None
    for cand in (p.parent / "Objects", p.parent / "build", p.parent):
        for f in cand.glob("*.axf"):
            return f
    return None
