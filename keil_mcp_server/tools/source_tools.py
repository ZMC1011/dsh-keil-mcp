"""Source editing tools (blueprint §6.1-C)."""
from __future__ import annotations

from typing import List, Optional

from .context import get_context


async def source_read(file: str, start_line: int = 1,
                      end_line: Optional[int] = None) -> dict:
    """Read a source file with line numbers (auto backup not needed; read-only)."""
    ctx = get_context()
    try:
        return {"success": True, **ctx.editor.read(file, start_line, end_line)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def source_edit(file: str, start_line: int, end_line: int,
                      new_content: str) -> dict:
    """Edit a source file; original is automatically backed up to .keil-mcp-backups/.

    Args:
        file: path to source file
        start_line / end_line: 1-based inclusive line range to replace
        new_content: replacement text (can be multi-line)
    """
    ctx = get_context()
    try:
        r = ctx.editor.edit(file, start_line, end_line, new_content)
        return {"success": True, **r.to_dict()}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def source_search(pattern: str, path: str = "",
                        files: Optional[List[str]] = None,
                        regex: bool = False, ignore_case: bool = True,
                        max_matches: int = 200) -> dict:
    """Search source files in the project directory.

    Args:
        pattern: text or regex pattern
        path: directory to search (default: default_project_dir or cwd)
        files: optional explicit file list (relative to path)
        regex: treat pattern as a regular expression
    """
    ctx = get_context()
    try:
        root = path or ctx.config.keil.default_project_dir or "."
        matches = ctx.editor.search(pattern, path=root, files=files,
                                    regex=regex, ignore_case=ignore_case,
                                    max_matches=max_matches)
        return {"success": True, "pattern": pattern, "match_count": len(matches),
                "matches": matches}
    except Exception as e:
        return {"success": False, "error": str(e)}
