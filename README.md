# Keil5 MCP Server

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-server-7C3AED.svg)](https://modelcontextprotocol.io)
[![PyPI](https://img.shields.io/badge/PyPI-keil--mcp--server-orange.svg)](https://pypi.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**English** | [中文](README.zh-CN.md)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that gives deepseek harness a **edit code → flash → debug → read feedback → fix code** closed loop for STM32 development with Keil MDK.

Instead of manually switching between the IDE, the programmer and the terminal, an agent can:

1. Build a Keil project and watch **real-time compile progress**
2. Get **structured errors** from UV4 logs (file / line / column / code / message)
3. **Explain error codes** with causes and suggested fixes
4. Edit source files safely (every edit is **auto-backed up**)
5. **Flash** firmware via the official UV4 channel or pyOCD
6. **Debug on hardware** through pyOCD: breakpoints, stepping, registers, memory, RTT logs
7. Run the **official Keil debug channel** (UV4 `-d` + `.ini` scripts)

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [From source (GitHub)](#from-source-github)
  - [Verify the install](#verify-the-install)
- [Quick Start](#quick-start)
- [MCP Client Configuration](#mcp-client-configuration)
  - [DeepSeek Harness (DSH)](#deepseek-harness-dsh)
  - [Claude Desktop / other stdio MCP clients](#claude-desktop--other-stdio-mcp-clients)
- [Tools](#tools)
  - [Build & Errors](#build--errors)
  - [Source Editing](#source-editing)
  - [Official Debug Channel](#official-debug-channel)
  - [Project & Environment](#project--environment)
  - [Flash](#flash)
  - [Probe Debugging](#probe-debugging)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [End-to-End Workflow Example](#end-to-end-workflow-example)
- [Safety Rules](#safety-rules)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **27 MCP tools** registered as `mcp__<serverName>__<tool>` (e.g. `mcp__keil__build_project`)
- **Real-time build progress**: tail-based monitor with percent / current file / phase, capped at 95% until link finishes
- **Structured UV4 log parsing**: compile errors (`main.c(25:1): error C2065: ...`), link errors (`L6218E`), Program Size, build time
- **Error-code knowledge base**: built-in explanations and fixes for common armcc/armclang codes (C2065, L6218E, L6406E, ...)
- **Safe source editing**: automatic `.keil-mcp-backups/` before every edit, line-range replace, regex search
- **Official flash path**: `UV4 -f` uses the project's configured Flash algorithm; pyOCD fallback accepts `.axf` directly
- **Hardware debug**: pyOCD probe control (connect / halt / resume / step / breakpoint / registers / memory / RTT)
- **Probe lease**: per-probe exclusive access (asyncio lock + file lock) so UV4 and pyOCD never fight over the debug port
- **Execution boundary**: read-only tools run concurrently; mutating tools serialize on a session lock; cancellation-safe via `asyncio.shield`
- **Works without Keil installed**: `keil_doctor` reports missing components clearly; the server still starts

## Requirements

| Component | Version / Notes |
|---|---|
| Python | **3.10+** (tested on 3.12) |
| Keil MDK | `UV4.exe` (build `-b`, flash `-f`, debug `-d`) — optional but required for build/flash tools |
| pyOCD | installed automatically via pip; needs a probe driver (ST-Link / J-Link / CMSIS-DAP) |
| Probe | ST-Link V2/V3, J-Link, CMSIS-DAP, Keil ULINKplus |
| Target pack | e.g. `pyocd pack install stm32f103c8` or reuse the Keil DFP |

## Installation

### From PyPI

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux / macOS
pip install keil-mcp-server
```

> Package is PyPI-ready (`pyproject.toml` + `LICENSE` + `server.json` included). If the package is not yet published, use the source install below.

### From source (GitHub)

```bash
git clone https://github.com/ZMC1011/dsh-keil-mcp.git
cd ds-keil-mcp
python -m venv .venv
.venv/Scripts/activate                       # Windows
# source .venv/bin/activate                  # Linux / macOS
pip install -e ".[dev]"
```

### Verify the install

```bash
# Environment self-check (UV4.exe, pyocd, connected probes)
python -m keil_mcp_server --check

# List all registered tools
python -m keil_mcp_server --tools

# Run the unit tests
pytest tests -q
```

## Quick Start

```bash
# 1. Start the MCP server (stdio transport — the MCP client will spawn this)
python -m keil_mcp_server

# 2. In your MCP client, call e.g.:
#    keil_doctor
#    discover_keil_projects { directory: "D:/STM32Projects" }
#    configure_keil_project { project: "D:/STM32Projects/app/app.uvprojx" }
#    build_project { project: "...", target: "Target 1", stream_progress: true }
#    flash_firmware { project: "...", confirm: true }
```

## MCP Client Configuration

### DeepSeek Harness (DSH)

Per the [official DSH MCP docs](https://deepseekdocs.com/docs/features/mcp): **one plugin instance = one MCP server**, wired through the official bridge plugin `@deepseek-ai/dsh-mcp-client`. Add this to your profile's `cordis.patch.yml` (or `cordis.yml`):

```yaml
- insert:
    - id: mcp-keil
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: keil                 # tools appear as mcp__keil__build_project etc.
        transport: stdio
        command: D:/000_Environment/mcp-servers/ds-keil-mcp/.venv/Scripts/python.exe
        args: ['-m', 'keil_mcp_server']
        env:
          KEIL_UV4_PATH: D:/002_software/Keil5/UV4/UV4.exe
          KEIL_PROJECT_DIR: D:/STM32Projects
        # optional: toolCallTimeoutMs: 60000, failOnStartupError: false
```

Verify with:

```bash
dsh web --dump-config | grep -A3 mcp
# or check session logs for mcp__keil__* calls
```

> Note: serverName must match `[A-Za-z0-9_-]{1,32}` and be unique among live instances.

### Claude Desktop / other stdio MCP clients

Most MCP clients use the `mcpServers` JSON convention:

```json
{
  "mcpServers": {
    "keil": {
      "command": "D:/000_Environment/mcp-servers/ds-keil-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "keil_mcp_server"],
      "env": {
        "KEIL_UV4_PATH": "D:/002_software/Keil5/UV4/UV4.exe",
        "KEIL_PROJECT_DIR": "D:/STM32Projects"
      }
    }
  }
}
```

For a source checkout without a venv, `uv` also works:

```json
{
  "mcpServers": {
    "keil": {
      "command": "uv",
      "args": ["--directory", "D:/path/to/ds-keil-mcp", "run", "keil_mcp_server"]
    }
  }
}
```

## Tools

All 27 tools return structured JSON. Destructive operations (**flash / erase**) require `confirm=True`.

### Build & Errors

| Tool | Description | Key params → Result |
|---|---|---|
| `build_project` | Compile with UV4 `-b` (or `-r` rebuild / `-c` clean), realtime progress | `project`, `target?`, `timeout_seconds?`, `stream_progress?`, `clean?`, `rebuild?` → `{status, returncode, build_log, errors[], summary, progress?}` |
| `build_progress_status` | Query in-flight build progress | `build_id` → `{status, percent, current_file, phase}` |
| `build_cancel` | Request build cancellation | `build_id` → `{success}` |
| `parse_build_errors` | Parse UV4 log into structured errors | `log_path?` or `log_content?` → `{errors[], warnings[], summary}` |
| `explain_build_error` | Error code → explanation + causes + fixes | `error_code`, `message?`, `file?`, `line?` → `{explanation, common_causes[], suggested_fixes[]}` |

### Source Editing

| Tool | Description | Key params → Result |
|---|---|---|
| `source_read` | Read source with line numbers | `file`, `start_line?`, `end_line?` → `{content, total_lines, ...}` |
| `source_edit` | Replace a line range; **auto-backup** first | `file`, `start_line`, `end_line`, `new_content` → `{success, lines_changed, backup_path}` |
| `source_search` | Search source files (text or regex) | `pattern`, `path?`, `files?`, `regex?` → `{matches[]}` |

### Official Debug Channel

| Tool | Description | Key params → Result |
|---|---|---|
| `uv4_debug_session` | Run UV4 `-d` + generated `.ini` debug script (headless breakpoint/go/step) | `project`, `target?`, `ini_path?`, `breakpoint?`, `dump_vars?`, `timeout_seconds?` → `{success, returncode, output}` |
| `uv4_debug_dde` | Read session output by id | `session_id` → `{output}` |

### Project & Environment

| Tool | Description | Key params → Result |
|---|---|---|
| `keil_doctor` | Environment check: UV4.exe, pyocd, packs, connected probes | — → `{uv4_exists, pyocd_installed, probes[], status}` |
| `discover_keil_projects` | Find `*.uvprojx` under a directory | `directory?`, `recursive?` → `{projects[]}` |
| `configure_keil_project` | Parse project: targets, device, pack, groups, source files | `project`, `target?` → `{targets[], device, pack_id, source_files[]}` |

### Flash

| Tool | Description | Key params → Result |
|---|---|---|
| `flash_firmware` | Flash via UV4 `-f` (preferred) or pyOCD | `project?`, `image?`, `backend?`, `probe_id?`, **`confirm`** → `{success, log}` |
| `erase_flash` | Erase chip flash (pyOCD `erase -c`) | **`confirm`**, `probe_id?`, `chip?` → `{success, output}` |
| `verify_flash` | Verify chip against image (pyOCD `verify`) | `image`, `probe_id?` → `{success, output}` |

### Probe Debugging

| Tool | Description |
|---|---|
| `probe_connect` / `probe_disconnect` | Connect / release a pyOCD probe (disconnect frees the port for UV4 `-f`) |
| `probe_halt` / `probe_resume` / `probe_step` | Core control |
| `set_breakpoint` / `continue_target` | Breakpoint by symbol or address, continue |
| `probe_read_registers` | Read r0-r15, sp, lr, pc, xpsr |
| `probe_read_memory` | Read memory at address (hex bytes) |
| `read_rtt_log` | Read SEGGER RTT output (if running) |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  MCP Client (DeepSeek Harness / Claude Desktop / ...)        │
│  → tools registered as mcp__keil__*                          │
└──────────────────────────────┬───────────────────────────────┘
                               │ stdio (JSON-RPC 2.0)
┌──────────────────────────────▼───────────────────────────────┐
│  keil-mcp-server (Python, FastMCP)                           │
│                                                              │
│  server.py   — tool registration + Execution Boundary        │
│                (read-only whitelist → concurrent;            │
│                 mutating tools → session lock +              │
│                 asyncio.to_thread + asyncio.shield)          │
│                                                              │
│  tools/      — MCP tool layer (27 tools)                     │
│                                                              │
│  core/       — deliverable layer                             │
│    uv4_runner.py      UV4 -b/-r/-c/-f/-d process runner      │
│    build_progress.py  realtime log tail monitor              │
│    error_parser.py    UV4 log → structured errors + KB       │
│    source_editor.py   read/edit/search + auto-backup         │
│    uv4_debug.py       UV4 -d + .ini script engine            │
│    probe_lease.py     per-probe exclusive lease              │
│    project_utils.py   .uvprojx parser (namespace-tolerant)   │
│                                                              │
│  models.py / config.py / config.yaml                         │
└───────────────┬──────────────────────────────┬───────────────┘
                │                              │
      ┌─────────▼─────────┐          ┌─────────▼─────────┐
      │ Keil MDK (UV4.exe)│          │ pyOCD + probe     │
      │ build/flash/debug │          │ ST-Link/J-Link/   │
      │                   │          │ CMSIS-DAP → chip  │
      └───────────────────┘          └───────────────────┘
```

**Dependency direction**: MCP layer → tools → core → Keil MDK / pyOCD → target chip.

Key design points:

- **Execution boundary** (inspired by McuBuddy): read-only tools run concurrently; everything else serializes on a per-session `asyncio.Lock`, runs in a worker thread (`asyncio.to_thread`) and is cancellation-protected (`asyncio.shield`).
- **Probe lease**: UV4 `-f` and pyOCD cannot share the debug port. `ProbeLease` (asyncio lock + `filelock`) serializes access; the flash flow disconnects pyOCD before UV4 takes over.
- **Realtime progress**: a daemon thread tails the UV4 log, counting `compiling` lines against the source-file count parsed from `.uvprojx` (percent capped at 95% until the `Build Time Elapsed` marker).
- **Malformed-XML tolerance**: older Keil projects contain mismatched tags (e.g. `<b498tele498>...</bUseTDR>`); the project parser repairs them before parsing.

## Configuration

`config.yaml` (bundled) + environment variable overrides:

```yaml
keil:
  uv4_path: "C:/Keil_v5/UV4/UV4.exe"        # or env KEIL_UV4_PATH
  default_project_dir: ""                   # or env KEIL_PROJECT_DIR
build:
  build_timeout: 300
  stream_progress: true
  tail_flush_wait: 3        # seconds to wait for UV4 log tail flush after exit
error:
  max_errors: 200
source:
  backup_dir: ".keil-mcp-backups"
probe_lease:
  lock_dir: ".keil-mcp-locks"
server:
  transport: "stdio"
  log_level: "INFO"
```

## End-to-End Workflow Example

A typical agent session (tool names shown with DSH prefix `mcp__keil__`):

```text
1. mcp__keil__keil_doctor                       # environment + probe OK?
2. mcp__keil__discover_keil_projects            # find .uvprojx files
3. mcp__keil__configure_keil_project            # parse targets/device/sources
4. mcp__keil__build_project (stream_progress)   # compile; on failure:
5. mcp__keil__parse_build_errors                # structured errors[]
6. mcp__keil__explain_build_error               # causes + fixes
7. mcp__keil__source_edit                       # fix code (auto-backup)
   → back to 4 until 0 errors
8. mcp__keil__flash_firmware (confirm=true)     # UV4 -f → "Verify OK"
9. mcp__keil__probe_connect + set_breakpoint    # attach debugger
10. mcp__keil__probe_read_registers / _memory   # observe chip state
11. mcp__keil__read_rtt_log                     # firmware logs
    → if logic bug found: source_edit → rebuild → reflash
```

## Safety Rules

| Level | Operations | Default |
|---|---|---|
| Read-only | chip match, register/memory/symbol reads, logs | no confirmation |
| Execute | halt / resume / step / reset | prompt |
| State write | memory/register writes, breakpoints, watchpoints | confirm |
| **Persistent destructive** | **flash erase / programming** | **explicit confirm + recovery plan** |
| Host process | Keil build, GDB server | prompt |

Principles: gather evidence before acting; identify the target chip first; confirm target / range / image / recovery before flashing.

## Testing

```bash
pytest tests -q        # 11 unit tests: log parsing, source editing, progress, project parsing
```

Manual smoke tests (in `tests/`):

```bash
python tests/raw_handshake.py    # bare JSON-RPC initialize + tools/list over stdio
python tests/func_test.py        # end-to-end tool calls through the MCP client SDK
```

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `Target DLL has been cancelled` on flash | pyOCD still owns the probe. Call `probe_disconnect` (or let the probe lease handle it) before `flash_firmware` with the UV4 backend. |
| `UV4.exe not found` | Set `KEIL_UV4_PATH` or `keil.uv4_path` in config; run `keil_doctor` to confirm. |
| `No module named keil_mcp_server` | The venv's editable install points at an old path — reinstall from the current checkout: `pip install -e .` |
| `No target connected` | Check probe wiring / driver; `keil_doctor` lists detected probes. |
| `pyocd pack install` needed | e.g. `pyocd pack install stm32f103c8` or point pyOCD at the Keil DFP folder. |

## Roadmap

- [ ] Publish to PyPI and register in the MCP registry
- [ ] MCUBUDDY_TOOLSETS-style domain toggles
- [ ] ELF symbol resolution for `set_breakpoint` by name
- [ ] RTOS task awareness (FreeRTOS)
- [ ] GitHub Actions CI for unit tests
- [ ] Linux/macOS support notes (Keil is Windows-only; pyOCD parts are cross-platform)

## Contributing

Contributions are welcome! Please open an issue first to discuss changes, then submit a PR. 

## License

[MIT](LICENSE) — free to use, modify and distribute with attribution.
