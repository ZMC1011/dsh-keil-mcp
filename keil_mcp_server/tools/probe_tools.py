"""Probe debug tools via pyOCD: connect/halt/resume/step/breakpoints/registers.

These are read-only or execution-control operations on a debug probe; flash
persistent operations live in flash_tools.py. Every probe access is serialized
through the per-probe lease (blueprint §7.5).
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from .context import get_context

_probe_cache: dict = {}


def _session(probe_id: str = "default"):
    from pyocd.core.helpers import ConnectHelper
    s = _probe_cache.get(probe_id)
    if s is None:
        s = ConnectHelper.session_with_chosen_probe(
            unique_id=probe_id if probe_id != "default" else None,
            options={"target_override": None})
        s.open()
        _probe_cache[probe_id] = s
    return s


def _close(probe_id: str = "default") -> None:
    s = _probe_cache.pop(probe_id, None)
    if s is not None:
        try:
            s.close()
        except Exception:
            pass


async def probe_connect(probe_id: str = "default", chip: str = "") -> dict:
    """Connect to a debug probe via pyOCD (auto-detect or by unique id)."""
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            s = _session(probe_id)
            tgt = s.target
            return {"success": True, "probe_id": probe_id,
                    "target": getattr(tgt, "part_number", "") or chip,
                    "state": "connected"}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def probe_disconnect(probe_id: str = "default") -> dict:
    """Disconnect the probe (releases it for UV4 -f flash path)."""
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            _close(probe_id)
            return {"success": True, "probe_id": probe_id}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _ctrl(probe_id: str, op: str, **kw) -> dict:
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            s = _session(probe_id)
            t = s.target
            fn = getattr(t, op)
            fn(**kw)
            return {"success": True, "probe_id": probe_id, "op": op}
        except Exception as e:
            return {"success": False, "error": str(e), "op": op}


async def probe_halt(probe_id: str = "default") -> dict:
    """Halt the target."""
    return await _ctrl(probe_id, "halt")


async def probe_resume(probe_id: str = "default") -> dict:
    """Resume the target."""
    return await _ctrl(probe_id, "resume")


async def probe_step(probe_id: str = "default") -> dict:
    """Single-step the target."""
    return await _ctrl(probe_id, "step")


async def set_breakpoint(address: int = 0, symbol: str = "", probe_id: str = "default") -> dict:
    """Set a hardware breakpoint by symbol name or address."""
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            s = _session(probe_id)
            t = s.target
            if symbol and not address:
                # resolve symbol via ELF if loaded
                from pyocd.debug.elf.debug_elf import DebugElf
                elf = getattr(s, "_elf", None)
                if elf is not None:
                    syms = elf.symbols
                    if symbol in syms:
                        address = syms[symbol].address
            if not address:
                return {"success": False, "error": f"cannot resolve symbol {symbol!r} (no ELF loaded)"}
            bp = t.set_breakpoint(address)
            return {"success": True, "address": address, "bp_handle": bp}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def continue_target(probe_id: str = "default") -> dict:
    """Continue the target until the next breakpoint."""
    return await _ctrl(probe_id, "resume")


async def probe_read_registers(probe_id: str = "default") -> dict:
    """Read core registers (r0-r15, xpsr, sp, lr, pc)."""
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            s = _session(probe_id)
            t = s.target
            regs = t.read_core_registers_raw(range(16))
            xpsr = t.read_core_register("xpsr") if hasattr(t, "read_core_register") else None
            names = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
                     "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc"]
            out = {n: ("0x%08x" % (v & 0xFFFFFFFF)) for n, v in zip(names, regs)}
            if xpsr is not None:
                out["xpsr"] = "0x%08x" % (xpsr & 0xFFFFFFFF)
            return {"success": True, "registers": out}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def probe_read_memory(address: int, length: int = 64, probe_id: str = "default") -> dict:
    """Read memory at address (bytes)."""
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            s = _session(probe_id)
            t = s.target
            data = t.read_memory_block8(address, length)
            hexs = " ".join("%02x" % b for b in data)
            return {"success": True, "address": "0x%08x" % address,
                    "length": length, "data_hex": hexs}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def read_rtt_log(probe_id: str = "default", timeout_seconds: int = 3) -> dict:
    """Read recent SEGGER RTT log output from the target (if RTT is running)."""
    ctx = get_context()
    async with ctx.lease.acquire(probe_id):
        try:
            from pyocd.rtt import RTT
            s = _session(probe_id)
            rtt = RTT(s)
            rtt.start()
            text = rtt.read(0)
            rtt.stop()
            return {"success": True, "rtt_log": text.decode("utf-8", errors="replace")[-4000:]}
        except Exception as e:
            return {"success": False, "error": str(e)}
