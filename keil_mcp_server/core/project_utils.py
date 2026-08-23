"""Keil .uvprojx project parsing (targets / device / source files / groups).

Real .uvprojx files carry NO XML namespace (only xsi), so all element lookup
is done by local tag name (namespace-agnostic).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from ..models import KeilProject

# C/C++/asm source files that count toward build progress
_SOURCE_SUFFIXES = {".c", ".cpp", ".cxx", ".s", ".asm", ".S", ".sx"}


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _find_local(root, name: str):
    """First descendant (including root) whose local tag name == name."""
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _find_all_local(root, name: str) -> list:
    return [el for el in root.iter() if _local(el.tag) == name]


_MALFORMED_LINE = re.compile(r"^\s*<([A-Za-z0-9_]+)>(.*?)</([A-Za-z0-9_]+)>\s*$")


def _fix_malformed_xml(text: str) -> str:
    """Repair Keil's known broken tag pairs (e.g. <b498tele498>1</bUseTDR>).

    Older Keil versions write mismatched open/close tag names; standard XML
    parsers reject such projects. We rewrite the closing tag to match.
    """
    out = []
    for line in text.splitlines():
        m = _MALFORMED_LINE.match(line)
        if m and m.group(1) != m.group(3):
            line = f"<{m.group(1)}>{m.group(2)}</{m.group(1)}>"
        out.append(line)
    return "\n".join(out)


def parse_project(path: str | Path, target: Optional[str] = None) -> KeilProject:
    """Parse a .uvprojx file. target selects a Target; None -> first target."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    import xml.etree.ElementTree as ET
    root = ET.fromstring(_fix_malformed_xml(p.read_text(encoding="utf-8", errors="replace")))
    proj = KeilProject(path=str(p), name=p.stem)

    # targets
    targets = []
    for t in _find_all_local(root, "TargetName"):
        if t.text:
            targets.append(t.text)
    proj.targets = targets

    sel = target or (targets[0] if targets else "")
    # locate selected target element
    tgt_el = None
    for t in _find_all_local(root, "Target"):
        name_el = _find_local(t, "TargetName")
        if name_el is not None and (name_el.text or "") == sel:
            tgt_el = t
            break
    if tgt_el is None:
        tgt_els = _find_all_local(root, "Target")
        tgt_el = tgt_els[0] if tgt_els else None

    if tgt_el is not None:
        dev = _find_local(tgt_el, "Device")
        vendor = _find_local(tgt_el, "Vendor")
        pack = _find_local(tgt_el, "PackID")
        cpu = _find_local(tgt_el, "Cpu")
        if dev is not None and dev.text:
            proj.device = dev.text
        if vendor is not None and vendor.text:
            proj.vendor = vendor.text
        if pack is not None and pack.text:
            proj.pack_id = pack.text
        if cpu is not None and cpu.text:
            proj.cpu = cpu.text

        # groups + source files of selected target
        for grp in _find_all_local(tgt_el, "GroupName"):
            if grp.text:
                proj.groups.append(grp.text)
        for fn in _find_all_local(tgt_el, "FileName"):
            if fn.text and fn.text.strip():
                name = fn.text.strip()
                if Path(name).suffix.lower() in _SOURCE_SUFFIXES:
                    proj.source_files.append(name)
    return proj


def count_source_files(path: str | Path, target: Optional[str] = None) -> int:
    """Number of compilable source files in the selected target (for progress %)."""
    try:
        return len(parse_project(path, target).source_files)
    except Exception:
        return 0


def discover_projects(directory: str | Path, recursive: bool = True) -> List[str]:
    """Find *.uvprojx projects under directory."""
    d = Path(directory)
    if not d.exists():
        return []
    pattern = "**/*.uvprojx" if recursive else "*.uvprojx"
    return [str(p) for p in sorted(d.glob(pattern))]
