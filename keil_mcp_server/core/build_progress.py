"""Real-time build progress monitor (blueprint §7.1, RT-Thread tail paradigm)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ..models import BuildProgressState


class BuildProgressMonitor:
    """Tails the UV4 log file and updates a BuildProgressState."""

    def __init__(self, build_id: str, log_path: Path, total_files: int,
                 flush_wait: float = 3.0):
        self.build_id = build_id
        self.state = BuildProgressState(build_id=build_id)
        self.log_path = log_path
        self.total_files = total_files
        self.flush_wait = flush_wait
        self._stop = threading.Event()
        self._tail_thread: threading.Thread | None = None
        self._finished_ok = False
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            log_path.touch()  # pre-create: UV4 may write the tail late

    # ---------- lifecycle ----------
    def start(self, process) -> None:
        self._tail_thread = threading.Thread(
            target=self._tail, args=(process,), daemon=True, name=f"keil-tail-{self.build_id}")
        self._tail_thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float = 30.0) -> None:
        if self._tail_thread and self._tail_thread.is_alive():
            self._tail_thread.join(timeout)

    # ---------- tail loop ----------
    def _tail(self, process) -> None:
        self.state.status = "running"
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                empty = 0
                while not self._stop.is_set():
                    line = f.readline()
                    if line:
                        self._parse(line.strip())
                        empty = 0
                        if "Build Time Elapsed" in line:
                            self._finished_ok = True
                            self.state.status = "done"
                            self.state.percent = 100
                            break
                    else:
                        empty += 1
                        if empty > 5 and process is not None and process.poll() is not None:
                            # UV4 exited: the tail may not be flushed yet
                            time.sleep(self.flush_wait)
                            f.seek(0, 2)
                            continue
                        time.sleep(0.4)
        except Exception as e:  # pragma: no cover
            self.state.status = "failed"
            self.state.error = str(e)
        finally:
            if self.state.status == "running":
                self.state.status = "done"
                self.state.percent = min(100, self.state.percent)

    # ---------- parsing ----------
    def _parse(self, line: str) -> None:
        if line.startswith("compiling "):
            self.state.compiled_files += 1
            self.state.phase = "compiling"
            self.state.current_file = line[len("compiling "):].strip()
        elif "linking..." in line:
            self.state.phase = "linking"
        elif "Program Size:" in line:
            self.state.phase = "sizing"
        elif "FromELF:" in line or line.startswith("fromelf"):
            self.state.phase = "generating"
        elif "Build Target" in line:
            self.state.phase = "preparing"
        self.state.percent = self.percent()

    def percent(self) -> int:
        if self._finished_ok:
            return 100
        if self.total_files <= 0:
            return 0
        # cap at 95: last 5% reserved for link/generate
        return min(95, int(self.state.compiled_files * 100 / self.total_files))
