"""Source editing with automatic backup (blueprint §7.3)."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Optional

from ..models import EditResult


class SourceEditor:
    """read / edit / search source files; every edit is backed up first."""

    def __init__(self, backup_dir: str = ".keil-mcp-backups", allow_paths: Optional[List[str]] = None):
        self.backup_dir_name = backup_dir
        self.allow_paths = [Path(p).resolve() for p in (allow_paths or [])]

    # ---------- path checks ----------
    def _resolve(self, file: str) -> Path:
        p = Path(file).resolve()
        if self.allow_paths:
            if not any(p == root or root in p.parents for root in self.allow_paths):
                raise PermissionError(
                    f"file {p} outside allowed paths: {[str(x) for x in self.allow_paths]}")
        if not p.exists():
            raise FileNotFoundError(str(p))
        return p

    # ---------- read ----------
    def read(self, file: str, start_line: int = 1, end_line: Optional[int] = None) -> dict:
        path = self._resolve(file)
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        total = len(lines)
        start = max(1, start_line)
        end = min(total, end_line if end_line else total)
        return {
            "file": str(path), "total_lines": total,
            "start_line": start, "end_line": end,
            "content": "\n".join(lines[start - 1:end]),
        }

    # ---------- edit ----------
    def edit(self, file: str, start_line: int, end_line: int, new_content: str) -> EditResult:
        path = self._resolve(file)
        original = path.read_text(encoding="utf-8", errors="replace")
        lines = original.splitlines()
        total = len(lines)
        if start_line < 1 or end_line < start_line or end_line > total:
            raise ValueError(
                f"invalid range {start_line}..{end_line} (file has {total} lines)")
        backup_dir = path.parent / self.backup_dir_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{path.stem}.{int(time.time() * 1000)}.bak"
        backup.write_text(original, encoding="utf-8")
        new_lines = new_content.splitlines()
        lines[start_line - 1:end_line] = new_lines
        path.write_text("\n".join(lines), encoding="utf-8")
        return EditResult(success=True, file=str(path),
                          lines_changed=len(new_lines), backup_path=str(backup))

    # ---------- search ----------
    def search(self, pattern: str, path: str = "", files: Optional[List[str]] = None,
               regex: bool = False, ignore_case: bool = True, max_matches: int = 200) -> List[dict]:
        root = Path(path or ".").resolve()
        if files:
            targets = [root / f for f in files if (root / f).exists()]
        else:
            targets = [p for p in root.rglob("*")
                       if p.suffix.lower() in (".c", ".h", ".cpp", ".hpp", ".s", ".asm", ".sct", ".ld")
                       and not any(part.startswith(".") for part in p.parts)
                       and "Objects" not in p.parts and "Listings" not in p.parts]
        flags = 0 if regex else re.escape
        try:
            rx = re.compile(pattern if regex else re.escape(pattern),
                            re.IGNORECASE if ignore_case else 0)
        except re.error as e:
            raise ValueError(f"invalid pattern: {e}")
        matches: List[dict] = []
        for p in targets[:2000]:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    matches.append({"file": str(p), "line": i, "text": line.strip()[:300]})
                    if len(matches) >= max_matches:
                        return matches
        return matches
