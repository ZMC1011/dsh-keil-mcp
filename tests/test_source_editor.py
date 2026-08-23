"""Tests for SourceEditor (blueprint §7.3)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keil_mcp_server.core.source_editor import SourceEditor


def test_read_lines():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "main.c"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        ed = SourceEditor(backup_dir=".bk")
        r = ed.read(str(f))
        assert r["total_lines"] == 3
        assert r["content"] == "line1\nline2\nline3"
        r2 = ed.read(str(f), 2, 2)
        assert r2["content"] == "line2"


def test_edit_backs_up_and_rollback():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "main.c"
        original = "int main(void) {\n    return 0;\n}\n"
        f.write_text(original, encoding="utf-8")
        ed = SourceEditor(backup_dir=".keil-mcp-backups")
        res = ed.edit(str(f), 2, 2, "    return 1;")
        assert res.success is True
        assert res.lines_changed == 1
        assert Path(res.backup_path).exists()
        assert "return 1" in f.read_text(encoding="utf-8")
        # rollback via backup
        f.write_text(Path(res.backup_path).read_text(encoding="utf-8"), encoding="utf-8")
        assert f.read_text(encoding="utf-8") == original


def test_edit_invalid_range():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.c"
        f.write_text("x\n", encoding="utf-8")
        ed = SourceEditor()
        try:
            ed.edit(str(f), 1, 99, "y")
            assert False, "should raise"
        except ValueError:
            pass


def test_search():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "main.c"
        f.write_text("void setup(void) {}\nint counter = 0;\n", encoding="utf-8")
        ed = SourceEditor()
        m = ed.search("counter", path=td)
        assert len(m) == 1 and m[0]["line"] == 2
        m2 = ed.search("counter", path=td, regex=True)
        assert len(m2) == 1
