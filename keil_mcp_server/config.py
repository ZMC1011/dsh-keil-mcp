"""Configuration loading (blueprint §8)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class KeilConfig:
    uv4_path: str = "C:/Keil_v5/UV4/UV4.exe"
    default_project_dir: str = ""


@dataclass
class DebugConfig:
    default_backend: str = "pyocd"
    default_interface: str = "swd"
    uv4_debug_ini_dir: str = ".keil-mcp-ini"


@dataclass
class BuildConfig:
    build_timeout: int = 300
    stream_progress: bool = True
    progress_mode: str = "tail"
    tail_flush_wait: int = 3


@dataclass
class ErrorConfig:
    parser: str = "uv4"
    max_errors: int = 200


@dataclass
class SourceConfig:
    backup_dir: str = ".keil-mcp-backups"
    allow_paths: List[str] = field(default_factory=list)


@dataclass
class ProbeLeaseConfig:
    lock_dir: str = ".keil-mcp-locks"


@dataclass
class ServerConfig:
    transport: str = "stdio"
    log_level: str = "INFO"


@dataclass
class AppConfig:
    keil: KeilConfig = field(default_factory=KeilConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    error: ErrorConfig = field(default_factory=ErrorConfig)
    source: SourceConfig = field(default_factory=SourceConfig)
    probe_lease: ProbeLeaseConfig = field(default_factory=ProbeLeaseConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    config_path: str = ""

    @staticmethod
    def load(config_path: Optional[str] = None) -> "AppConfig":
        """Load YAML config; env vars override. Missing file -> defaults."""
        cfg = AppConfig()
        candidates = []
        if config_path:
            candidates.append(Path(config_path))
        candidates.append(Path(__file__).parent / "config.yaml")
        for cand in candidates:
            if cand.exists():
                cfg.config_path = str(cand)
                data = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
                cfg._apply(data)
                break
        cfg._apply_env()
        return cfg

    def _apply(self, data: dict) -> None:
        k = data.get("keil") or {}
        self.keil = KeilConfig(uv4_path=str(k.get("uv4_path", self.keil.uv4_path)),
                               default_project_dir=str(k.get("default_project_dir", "")))
        d = data.get("debug") or {}
        self.debug = DebugConfig(
            default_backend=str(d.get("default_backend", self.debug.default_backend)),
            default_interface=str(d.get("default_interface", self.debug.default_interface)),
            uv4_debug_ini_dir=str(d.get("uv4_debug_ini_dir", self.debug.uv4_debug_ini_dir)))
        b = data.get("build") or {}
        self.build = BuildConfig(
            build_timeout=int(b.get("build_timeout", self.build.build_timeout)),
            stream_progress=bool(b.get("stream_progress", self.build.stream_progress)),
            progress_mode=str(b.get("progress_mode", self.build.progress_mode)),
            tail_flush_wait=int(b.get("tail_flush_wait", self.build.tail_flush_wait)))
        e = data.get("error") or {}
        self.error = ErrorConfig(parser=str(e.get("parser", self.error.parser)),
                                 max_errors=int(e.get("max_errors", self.error.max_errors)))
        s = data.get("source") or {}
        self.source = SourceConfig(
            backup_dir=str(s.get("backup_dir", self.source.backup_dir)),
            allow_paths=[str(x) for x in (s.get("allow_paths") or [])])
        p = data.get("probe_lease") or {}
        self.probe_lease = ProbeLeaseConfig(lock_dir=str(p.get("lock_dir", self.probe_lease.lock_dir)))
        sv = data.get("server") or {}
        self.server = ServerConfig(transport=str(sv.get("transport", self.server.transport)),
                                   log_level=str(sv.get("log_level", self.server.log_level)))

    def _apply_env(self) -> None:
        if os.environ.get("KEIL_PATH"):
            self.keil.uv4_path = str(Path(os.environ["KEIL_PATH"]) / "UV4" / "UV4.exe")
        if os.environ.get("KEIL_UV4_PATH"):
            self.keil.uv4_path = os.environ["KEIL_UV4_PATH"]
        if os.environ.get("KEIL_PROJECT_DIR"):
            self.keil.default_project_dir = os.environ["KEIL_PROJECT_DIR"]


def uv4_exists(cfg: AppConfig) -> bool:
    return Path(cfg.keil.uv4_path).exists()


def find_uv4(cfg: AppConfig) -> str:
    """Locate UV4.exe: config path -> env -> common install dirs."""
    candidates = [cfg.keil.uv4_path]
    for root in ("C:/Keil_v5", "D:/Keil_v5", "C:/Keil", "D:/Keil", "C:/Program Files/Keil_v5"):
        for sub in ("UV4/UV4.exe", "UV4.exe"):
            candidates.append(f"{root}/{sub}")
    for cand in candidates:
        p = Path(cand)
        if p.exists():
            return str(p)
    return cfg.keil.uv4_path  # fall back to configured path; caller reports missing
