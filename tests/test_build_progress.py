"""Tests for BuildProgressMonitor (blueprint §7.1)."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keil_mcp_server.core.build_progress import BuildProgressMonitor


class FakeProcess:
    def __init__(self):
        self._poll = None

    def poll(self):
        return self._poll


def test_percent_progression():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "build.log"
        mon = BuildProgressMonitor("t1", log, total_files=10)
        fake = FakeProcess()
        mon.start(fake)
        # simulate UV4 writing lines
        with open(log, "a", encoding="utf-8") as f:
            f.write("compiling main.c...\n")
            f.flush()
        time.sleep(0.8)
        assert mon.state.phase == "compiling"
        assert mon.state.percent == 10
        with open(log, "a", encoding="utf-8") as f:
            f.write("compiling uart.c...\n")
            f.write("linking...\n")
            f.write("Program Size: Code=100 RO-data=10 RW-data=5 ZI-data=50\n")
            f.write('"Objects\\app.axf" - 0 Error(s), 0 Warning(s).\n')
            f.write("Build Time Elapsed: 00:00:01\n")
            f.flush()
        mon.join(timeout=5)
        assert mon.state.percent == 100
        assert mon.state.status == "done"
        assert mon.state.phase == "sizing"
        mon.stop()


def test_percent_cap_95():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "build.log"
        mon = BuildProgressMonitor("t2", log, total_files=4)
        for i in range(3):
            mon._parse("compiling f%d.c..." % i)
        assert mon.state.percent == 75
        mon._parse("compiling f3.c...")
        # 4/4 = 100 but capped at 95 until finished marker
        assert mon.state.percent == 95
        mon._finished_ok = True
        assert mon.percent() == 100
