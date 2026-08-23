"""Data models (blueprint §12)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CompileError:
    """A single structured compile error/warning (blueprint §7.2)."""
    file: str
    line: int
    column: int
    severity: str          # error | warning | note
    code: str              # e.g. C2065 / L6218E
    message: str
    source: str = ""       # raw source line when available

    def to_dict(self) -> dict:
        return {
            "file": self.file, "line": self.line, "column": self.column,
            "severity": self.severity, "code": self.code,
            "message": self.message, "source": self.source,
        }


@dataclass
class BuildSummary:
    success: bool
    errors: int = 0
    warnings: int = 0
    code_size: int = 0
    ro_data: int = 0
    rw_data: int = 0
    zi_data: int = 0
    build_time: str = ""
    output_file: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success, "errors": self.errors, "warnings": self.warnings,
            "code_size": self.code_size, "ro_data": self.ro_data,
            "rw_data": self.rw_data, "zi_data": self.zi_data,
            "build_time": self.build_time, "output_file": self.output_file,
        }


@dataclass
class BuildResult:
    """Full build outcome (blueprint §12)."""
    status: str                       # ok | error | canceled | not_found
    returncode: Optional[int]
    build_log: str
    errors: List[CompileError] = field(default_factory=list)
    summary: Optional[BuildSummary] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status, "returncode": self.returncode,
            "build_log": self.build_log[-20000:],
            "errors": [e.to_dict() for e in self.errors[:200]],
            "summary": self.summary.to_dict() if self.summary else None,
        }


@dataclass
class BuildProgressState:
    """Live progress state for one build (blueprint §7.1)."""
    build_id: str
    status: str = "starting"          # starting | running | done | canceled | failed
    percent: int = 0
    compiled_files: int = 0
    current_file: str = ""
    phase: str = "starting"
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "build_id": self.build_id, "status": self.status,
            "percent": self.percent, "current_file": self.current_file,
            "phase": self.phase, "error": self.error,
        }


@dataclass
class DebugState:
    state: str                        # connected | running | halted
    pc: str = ""
    sp: str = ""
    current_file: str = ""
    current_line: int = 0

    def to_dict(self) -> dict:
        return {
            "state": self.state, "pc": self.pc, "sp": self.sp,
            "current_file": self.current_file, "current_line": self.current_line,
        }


@dataclass
class EditResult:
    success: bool
    file: str = ""
    lines_changed: int = 0
    backup_path: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success, "file": self.file,
            "lines_changed": self.lines_changed, "backup_path": self.backup_path,
        }


@dataclass
class KeilProject:
    """Parsed .uvprojx project info."""
    path: str
    name: str = ""
    targets: List[str] = field(default_factory=list)
    device: str = ""
    vendor: str = ""
    pack_id: str = ""
    cpu: str = ""
    source_files: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path, "name": self.name, "targets": self.targets,
            "device": self.device, "vendor": self.vendor, "pack_id": self.pack_id,
            "cpu": self.cpu,
            "source_files": self.source_files[:500],
            "source_file_count": len(self.source_files),
            "groups": self.groups,
        }
