"""UV4.exe process runner: build (-b/-r), flash (-f), debug (-d) (blueprint §4.1)."""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from ..config import find_uv4


class UV4Runner:
    """Runs UV4.exe commands with log capture, progress tail and cancel support."""

    def __init__(self, uv4_path: Optional[str] = None):
        self.uv4_path = uv4_path or find_uv4(__import__("keil_mcp_server.config", fromlist=["AppConfig"]).AppConfig.load())

    def uv4(self) -> str:
        p = Path(self.uv4_path)
        if not p.exists():
            raise FileNotFoundError(
                f"UV4.exe not found at {self.uv4_path}. Install Keil MDK or set KEIL_UV4_PATH.")
        return str(p)

    # ---------- low-level run ----------
    def run(self, args: list[str], project: str, log_path: Optional[Path] = None,
            timeout: float = 300, progress=None) -> subprocess.CompletedProcess:
        """Run UV4.exe with args; stream progress via BuildProgressMonitor."""
        cmd = [self.uv4(), *args, project]
        log_path = log_path or (Path(project).parent / "build.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch()  # pre-create to avoid tail latency
        with open(log_path, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"\n===== UV4 {' '.join(args)} {project} @ {time.strftime('%H:%M:%S')} =====\n")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=0x08000000)  # CREATE_NO_WINDOW
        if progress is not None:
            progress.start(proc)
        try:
            # also mirror stdout into the log file
            with open(log_path, "a", encoding="utf-8", errors="replace") as f:
                for line in proc.stdout:
                    f.write(line)
                    f.flush()
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise TimeoutError(f"UV4 {' '.join(args)} timed out after {timeout}s")
        finally:
            if progress is not None:
                progress.stop()
                progress.join(timeout=10)
                # flush tail: UV4 may not flush the last lines before exit
                with open(log_path, "a", encoding="utf-8", errors="replace"):
                    pass
        return proc

    # ---------- typed commands ----------
    def build(self, project: str, target: Optional[str] = None, clean: bool = False,
              rebuild: bool = False, log_path: Optional[Path] = None,
              timeout: float = 300, progress=None) -> subprocess.CompletedProcess:
        args = ["-c" if clean else ("-r" if rebuild else "-b")]
        if target:
            args += ["-t", target]
        args += ["-j0", "-o", str(log_path or (Path(project).parent / "build.log"))]
        return self.run(args, project, log_path=log_path, timeout=timeout, progress=progress)

    def flash(self, project: str, target: Optional[str] = None, log_path: Optional[Path] = None,
              timeout: float = 120) -> subprocess.CompletedProcess:
        args = ["-f"]
        if target:
            args += ["-t", target]
        args += ["-j0", "-o", str(log_path or (Path(project).parent / "flash.log"))]
        return self.run(args, project, log_path=log_path, timeout=timeout)

    def debug(self, project: str, target: Optional[str] = None, ini: Optional[str] = None,
              timeout: float = 120) -> subprocess.CompletedProcess:
        """UV4 -d with a .ini debug script (official debug channel, blueprint §7.4)."""
        args = ["-d"]
        if target:
            args += ["-t", target]
        args += ["-j0"]
        if ini:
            args += ["-o", ini]
        return self.run(args, project, log_path=None, timeout=timeout)


class BuildRegistry:
    """Registry of in-flight builds (for build_progress_status / build_cancel)."""

    def __init__(self):
        self._builds: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._seq = 0

    def create(self, project: str, target: str = "", log_path: Optional[Path] = None) -> str:
        with self._lock:
            self._seq += 1
            bid = f"b{self._seq:04d}"
            self._builds[bid] = {
                "project": project, "target": target,
                "log_path": str(log_path) if log_path else "",
                "state": None, "process": None, "cancel": threading.Event(),
            }
            return bid

    def get(self, build_id: str) -> Optional[dict]:
        with self._lock:
            return self._builds.get(build_id)

    def set(self, build_id: str, **kw) -> None:
        with self._lock:
            if build_id in self._builds:
                self._builds[build_id].update(kw)

    def request_cancel(self, build_id: str) -> bool:
        with self._lock:
            b = self._builds.get(build_id)
            if not b:
                return False
            b["cancel"].set()
            return True

    def remove(self, build_id: str) -> None:
        with self._lock:
            self._builds.pop(build_id, None)
