"""Tests for UV4LogParser (blueprint §7.2) — official log format from §4.2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keil_mcp_server.core.error_parser import UV4LogParser, explain_error

SAMPLE_LOG = """Build target 'STM32F103C8'
compiling main.c...
main.c(25:1): error C2065: 'undeclared_var': undeclared identifier
linking...
Program Size: Code=5432 RO-data=432 RW-data=160 ZI-data=1024
"Objects\\app.axf" - 1 Error(s), 1 Warning(s).
Build Time Elapsed: 00:00:05
"""

SAMPLE_WARN = """compiling uart.c...
uart.c(7:5): warning C4013: 'foo' undefined; assuming extern returning int
"Objects\\app.axf" - 0 Error(s), 1 Warning(s).
Build Time Elapsed: 00:00:03
"""

LINK_LOG = """linking...
.\\Objects\\app.axf: Error: L6218E: Undefined symbol UART_Init (referred from main.o).
"Objects\\app.axf" - 1 Error(s), 0 Warning(s).
Build Time Elapsed: 00:00:01
"""


def test_parse_compile_error():
    parser = UV4LogParser()
    errors, summary = parser.parse(SAMPLE_LOG)
    assert summary.success is False
    assert summary.errors == 1
    assert summary.warnings == 1
    assert summary.code_size == 5432
    assert summary.ro_data == 432
    assert summary.rw_data == 160
    assert summary.zi_data == 1024
    assert summary.output_file.endswith("app.axf")
    assert summary.build_time == "00:00:05"
    errs = [e for e in errors if e.severity == "error"]
    assert len(errs) == 1
    e = errs[0]
    assert e.file == "main.c" and e.line == 25 and e.column == 1
    assert e.code == "C2065"
    assert "undeclared" in e.message


def test_parse_warning_only():
    parser = UV4LogParser()
    errors, summary = parser.parse(SAMPLE_WARN)
    assert summary.success is True
    assert summary.errors == 0
    assert summary.warnings == 1
    warns = [e for e in errors if e.severity == "warning"]
    assert len(warns) == 1 and warns[0].code == "C4013"


def test_parse_link_error():
    parser = UV4LogParser()
    errors, summary = parser.parse(LINK_LOG)
    assert summary.success is False
    link = [e for e in errors if e.severity == "error"]
    assert len(link) == 1
    assert link[0].code == "L6218E"
    assert "UART_Init" in link[0].message


def test_explain_error():
    info = explain_error("L6218E", "Undefined symbol UART_Init")
    assert "explanation" in info and info["common_causes"] and info["suggested_fixes"]
    assert any("未加入工程" in c for c in info["common_causes"])
    # unknown code falls back to default
    info2 = explain_error("X9999", "mystery")
    assert "未知错误码" in info2["explanation"]
