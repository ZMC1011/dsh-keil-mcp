"""Official Keil debug channel: UV4 -d + .ini script (blueprint §7.4)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .uv4_runner import UV4Runner


class UV4DebugSession:
    """One-shot UV4 -d debug run driven by a .ini script.

    The .ini script (Keil Debugger Function syntax) can use Break.Set / Go /
    Step / Watch.Set / MEM.Dump / printf to drive the debugger headlessly.
    """

    def __init__(self, runner: Optional[UV4Runner] = None, ini_dir: str = ".keil-mcp-ini"):
        self.runner = runner or UV4Runner()
        self.ini_dir = Path(ini_dir)
        self._sessions: dict[str, dict] = {}
        self._seq = 0

    def start(self, project: str, target: Optional[str] = None,
              ini_script: Optional[str] = None, ini_path: Optional[str] = None,
              timeout: float = 120) -> dict:
        if ini_path is None:
            ini_path = str(self._make_ini(project, ini_script or self._default_ini()))
        proc = self.runner.debug(project, target, ini=ini_path, timeout=timeout)
        self._seq += 1
        sid = f"dbg{self._seq:04d}"
        output = ""
        if proc.stdout:
            output = proc.stdout
        log_file = Path(ini_path).with_suffix(".log")
        if log_file.exists():
            output = log_file.read_text(encoding="utf-8", errors="replace")
        self._sessions[sid] = {"project": project, "output": output,
                               "returncode": proc.returncode, "ts": time.time()}
        return {"success": proc.returncode == 0, "session_id": sid,
                "returncode": proc.returncode, "output": output[-4000:]}

    def get_output(self, session_id: str) -> dict:
        s = self._sessions.get(session_id)
        if not s:
            return {"success": False, "error": f"unknown session {session_id}"}
        return {"success": True, "session_id": session_id, "output": s["output"][-4000:]}

    # ---------- ini helpers ----------
    def _make_ini(self, project: str, script: str) -> Path:
        d = self.ini_dir
        if not d.is_absolute():
            d = Path(project).parent / d
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"debug_{int(time.time() * 1000)}.ini"
        p.write_text(script, encoding="utf-8")
        return p

    def _default_ini(self) -> str:
        return """FUNC void Setup(void) {
  Break.Set main
  Go
  WHILE (!PC_in_range(0x08000000, 0x08010000)) { Step }
  Break.Kill main
  printf("DEBUG-SESSION-COMPLETE PC=0x%08x\n", PC)
}
Setup()
""";


def build_custom_ini(reset: bool = True, breakpoint: str = "main", steps: int = 0,
                     dump_vars: Optional[list[str]] = None) -> str:
    """Build a custom .ini script per parameters."""
    lines: list[str] = ["FUNC void Setup(void) {"]
    if breakpoint:
        lines.append(f"  Break.Set {breakpoint}")
    if reset:
        lines.append("  RESET")
    lines.append("  Go")
    if steps > 0:
        lines.append(f"  WHILE (1) {{ Step }}  /* {steps} manual steps below */")
    if dump_vars:
        for v in dump_vars:
            lines.append(f'  printf("{v} = 0x%08x\\n", {v})')
    lines.append('  printf("DEBUG-SESSION-COMPLETE\\n")')
    lines.append("}")
    lines.append("Setup()")
    return "\n".join(lines)
