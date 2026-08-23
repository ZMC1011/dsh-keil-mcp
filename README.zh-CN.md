# Keil5 MCP Server

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-server-7C3AED.svg)](https://modelcontextprotocol.io)
[![PyPI](https://img.shields.io/badge/PyPI-keil--mcp--server-orange.svg)](https://pypi.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[English](README.md) | **中文**

一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 的服务器，让 AI 编程智能体在 STM32 开发中（配合 Keil MDK）完成 **编译 → 烧录 → 调试 → 读反馈 → 改码** 的自动化闭环。

无需在 IDE、烧录器和终端之间手动切换，智能体可以：

1. 编译 Keil 工程并观察**实时编译进度**
2. 从 UV4 日志中获取**结构化错误**（文件 / 行 / 列 / 错误码 / 信息）
3. **解释错误码**，给出原因与修复建议
4. 安全地修改源码（每次编辑**自动备份**）
5. 通过官方 UV4 通道或 pyOCD **烧录**固件
6. 通过 pyOCD **硬件调试**：断点、单步、寄存器、内存、RTT 日志
7. 运行**官方 Keil 调试通道**（UV4 `-d` + `.ini` 脚本）

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [安装](#安装)
  - [从 PyPI 安装](#从-pypi-安装)
  - [从源码安装（GitHub）](#从源码安装github)
  - [验证安装](#验证安装)
- [快速开始](#快速开始)
- [MCP 客户端配置](#mcp-客户端配置)
  - [DeepSeek Harness (DSH)](#deepseek-harness-dsh)
  - [Claude Desktop / 其他 stdio MCP 客户端](#claude-desktop--其他-stdio-mcp-客户端)
- [工具清单](#工具清单)
  - [编译与错误解析](#编译与错误解析)
  - [源码编辑](#源码编辑)
  - [官方调试通道](#官方调试通道)
  - [工程与环境](#工程与环境)
  - [烧录](#烧录)
  - [探针调试](#探针调试)
- [工程架构](#工程架构)
- [配置](#配置)
- [端到端工作流示例](#端到端工作流示例)
- [安全规则](#安全规则)
- [测试](#测试)
- [故障排查](#故障排查)
- [路线图](#路线图)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 功能特性

- **27 个 MCP 工具**，注册为 `mcp__<serverName>__<tool>`（如 `mcp__keil__build_project`）
- **实时编译进度**：基于日志 tail 的监控器，显示百分比 / 当前文件 / 阶段，链接完成前封顶 95%
- **UV4 日志结构化解析**：编译错误（`main.c(25:1): error C2065: ...`）、链接错误（`L6218E`）、Program Size、编译耗时
- **错误码知识库**：内置常见 armcc/armclang 错误码（C2065、L6218E、L6406E 等）的解释与修复建议
- **安全源码编辑**：每次编辑前自动备份到 `.keil-mcp-backups/`，支持行区间替换、正则搜索
- **官方烧录通道**：`UV4 -f` 使用工程配置的 Flash 算法；pyOCD 备选可直接烧录 `.axf`
- **硬件调试**：pyOCD 探针控制（连接 / 暂停 / 恢复 / 单步 / 断点 / 寄存器 / 内存 / RTT）
- **探针租约**：每探针独占访问（asyncio 锁 + 文件锁），避免 UV4 与 pyOCD 争抢调试口
- **执行边界**：只读工具并发执行；写工具在会话锁上串行；`asyncio.shield` 防取消
- **无 Keil 也能启动**：`keil_doctor` 清晰报告缺失组件，服务器仍可正常运行

## 环境要求

| 组件 | 版本 / 说明 |
|---|---|
| Python | **3.10+**（已在 3.12 上测试） |
| Keil MDK | `UV4.exe`（编译 `-b`、烧录 `-f`、调试 `-d`）——可选，但编译/烧录工具需要 |
| pyOCD | 随 pip 自动安装；需要探针驱动（ST-Link / J-Link / CMSIS-DAP） |
| 探针 | ST-Link V2/V3、J-Link、CMSIS-DAP、Keil ULINKplus |
| 目标芯片包 | 如 `pyocd pack install stm32f103c8`，或复用 Keil DFP |

## 安装

### 从 PyPI 安装

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux / macOS
pip install keil-mcp-server
```

> 包已具备 PyPI 发布条件（包含 `pyproject.toml` + `LICENSE` + `server.json`）。若尚未发布到 PyPI，请使用下面的源码安装方式。

### 从源码安装（GitHub）

```bash
git clone https://github.com/ZMC1011/dsh-keil-mcp.git
cd ds-keil-mcp
python -m venv .venv
.venv/Scripts/activate                       # Windows
# source .venv/bin/activate                  # Linux / macOS
pip install -e ".[dev]"
```

### 验证安装

```bash
# 环境自检（UV4.exe、pyocd、已连接探针）
python -m keil_mcp_server --check

# 列出全部已注册工具
python -m keil_mcp_server --tools

# 运行单元测试
pytest tests -q
```

## 快速开始

```bash
# 1. 启动 MCP 服务器（stdio 传输——由 MCP 客户端拉起）
python -m keil_mcp_server

# 2. 在 MCP 客户端中调用，例如：
#    keil_doctor
#    discover_keil_projects { directory: "D:/STM32Projects" }
#    configure_keil_project { project: "D:/STM32Projects/app/app.uvprojx" }
#    build_project { project: "...", target: "Target 1", stream_progress: true }
#    flash_firmware { project: "...", confirm: true }
```

## MCP 客户端配置

### DeepSeek Harness (DSH)

按照 [DSH 官方 MCP 文档](https://deepseekdocs.com/docs/features/mcp)：**一个插件实例 = 一个 MCP 服务器**，通过官方桥接插件 `@deepseek-ai/dsh-mcp-client` 接入。在 profile 的 `cordis.patch.yml`（或 `cordis.yml`）中添加：

```yaml
- insert:
    - id: mcp-keil
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: keil                 # 工具显示为 mcp__keil__build_project 等
        transport: stdio
        command: D:/000_Environment/mcp-servers/ds-keil-mcp/.venv/Scripts/python.exe
        args: ['-m', 'keil_mcp_server']
        env:
          KEIL_UV4_PATH: D:/002_software/Keil5/UV4/UV4.exe
          KEIL_PROJECT_DIR: D:/STM32Projects
        # 可选：toolCallTimeoutMs: 60000, failOnStartupError: false
```

验证方法：

```bash
dsh web --dump-config | grep -A3 mcp
# 或在会话日志中查找 mcp__keil__* 调用
```

> 注意：serverName 必须匹配 `[A-Za-z0-9_-]{1,32}`，且在存活实例中唯一。

### Claude Desktop / 其他 stdio MCP 客户端

多数 MCP 客户端使用 `mcpServers` JSON 约定：

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

源码检出（无 venv）也可以用 `uv`：

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

## 工具清单

全部 27 个工具返回结构化 JSON。破坏性操作（**烧录 / 擦除**）必须传 `confirm=True`。

### 编译与错误解析

| 工具 | 说明 | 关键参数 → 返回 |
|---|---|---|
| `build_project` | UV4 `-b` 编译（`-r` 重建 / `-c` 清理），实时进度 | `project`、`target?`、`timeout_seconds?`、`stream_progress?`、`clean?`、`rebuild?` → `{status, returncode, build_log, errors[], summary, progress?}` |
| `build_progress_status` | 查询进行中构建的进度 | `build_id` → `{status, percent, current_file, phase}` |
| `build_cancel` | 请求取消构建 | `build_id` → `{success}` |
| `parse_build_errors` | 解析 UV4 日志为结构化错误 | `log_path?` 或 `log_content?` → `{errors[], warnings[], summary}` |
| `explain_build_error` | 错误码 → 解释 + 原因 + 修复建议 | `error_code`、`message?`、`file?`、`line?` → `{explanation, common_causes[], suggested_fixes[]}` |

### 源码编辑

| 工具 | 说明 | 关键参数 → 返回 |
|---|---|---|
| `source_read` | 带行号读取源码 | `file`、`start_line?`、`end_line?` → `{content, total_lines, ...}` |
| `source_edit` | 替换行区间；**自动备份** | `file`、`start_line`、`end_line`、`new_content` → `{success, lines_changed, backup_path}` |
| `source_search` | 源码搜索（文本或正则） | `pattern`、`path?`、`files?`、`regex?` → `{matches[]}` |

### 官方调试通道

| 工具 | 说明 | 关键参数 → 返回 |
|---|---|---|
| `uv4_debug_session` | UV4 `-d` + 生成的 `.ini` 调试脚本（无头断点/运行/单步） | `project`、`target?`、`ini_path?`、`breakpoint?`、`dump_vars?`、`timeout_seconds?` → `{success, returncode, output}` |
| `uv4_debug_dde` | 按 id 读取会话输出 | `session_id` → `{output}` |

### 工程与环境

| 工具 | 说明 | 关键参数 → 返回 |
|---|---|---|
| `keil_doctor` | 环境检查：UV4.exe、pyocd、pack、已连接探针 | — → `{uv4_exists, pyocd_installed, probes[], status}` |
| `discover_keil_projects` | 在目录下查找 `*.uvprojx` | `directory?`、`recursive?` → `{projects[]}` |
| `configure_keil_project` | 解析工程：targets、device、pack、groups、源文件 | `project`、`target?` → `{targets[], device, pack_id, source_files[]}` |

### 烧录

| 工具 | 说明 | 关键参数 → 返回 |
|---|---|---|
| `flash_firmware` | UV4 `-f`（首选）或 pyOCD 烧录 | `project?`、`image?`、`backend?`、`probe_id?`、**`confirm`** → `{success, log}` |
| `erase_flash` | 擦除芯片 Flash（pyOCD `erase -c`） | **`confirm`**、`probe_id?`、`chip?` → `{success, output}` |
| `verify_flash` | 校验芯片与镜像（pyOCD `verify`） | `image`、`probe_id?` → `{success, output}` |

### 探针调试

| 工具 | 说明 |
|---|---|
| `probe_connect` / `probe_disconnect` | 连接 / 释放 pyOCD 探针（释放后可让 UV4 `-f` 使用调试口） |
| `probe_halt` / `probe_resume` / `probe_step` | 内核控制 |
| `set_breakpoint` / `continue_target` | 按符号或地址设断点，继续运行 |
| `probe_read_registers` | 读取 r0-r15、sp、lr、pc、xpsr |
| `probe_read_memory` | 按地址读内存（十六进制字节） |
| `read_rtt_log` | 读取 SEGGER RTT 输出（若运行中） |

## 工程架构

```
┌──────────────────────────────────────────────────────────────┐
│  MCP 客户端（DeepSeek Harness / Claude Desktop / ...）       │
│  → 工具注册为 mcp__keil__*                                   │
└──────────────────────────────┬───────────────────────────────┘
                               │ stdio（JSON-RPC 2.0）
┌──────────────────────────────▼───────────────────────────────┐
│  keil-mcp-server（Python，FastMCP）                          │
│                                                              │
│  server.py   — 工具注册 + 执行边界                            │
│                （只读白名单 → 并发；                           │
│                 写工具 → 会话锁 +                             │
│                 asyncio.to_thread + asyncio.shield）          │
│                                                              │
│  tools/      — MCP 工具层（27 个工具）                        │
│                                                              │
│  core/       — 核心交付层                                     │
│    uv4_runner.py      UV4 -b/-r/-c/-f/-d 进程封装             │
│    build_progress.py  实时日志 tail 监控                      │
│    error_parser.py    UV4 日志 → 结构化错误 + 知识库           │
│    source_editor.py   读/改/搜 + 自动备份                     │
│    uv4_debug.py       UV4 -d + .ini 脚本引擎                  │
│    probe_lease.py     每探针独占租约                          │
│    project_utils.py   .uvprojx 解析（容错畸形 XML）           │
│                                                              │
│  models.py / config.py / config.yaml                         │
└───────────────┬──────────────────────────────┬───────────────┘
                │                              │
      ┌─────────▼─────────┐          ┌─────────▼─────────┐
      │ Keil MDK (UV4.exe)│          │ pyOCD + 探针      │
      │ 编译/烧录/调试    │          │ ST-Link/J-Link/   │
      │                   │          │ CMSIS-DAP → 芯片  │
      └───────────────────┘          └───────────────────┘
```

**依赖方向**：MCP 层 → tools → core → Keil MDK / pyOCD → 目标芯片。

关键设计点：

- **执行边界**（借鉴 McuBuddy）：只读工具并发执行；其余工具在会话 `asyncio.Lock` 上串行，在工作线程（`asyncio.to_thread`）中运行，并用 `asyncio.shield` 防取消。
- **探针租约**：UV4 `-f` 与 pyOCD 不能共享调试口。`ProbeLease`（asyncio 锁 + `filelock`）串行化访问；烧录流程会先断开 pyOCD 再交给 UV4。
- **实时进度**：守护线程 tail UV4 日志，按 `.uvprojx` 解析出的源文件数统计 `compiling` 行（百分比在 `Build Time Elapsed` 标记出现前封顶 95%）。
- **畸形 XML 容错**：旧版 Keil 工程含不匹配标签（如 `<b498tele498>...</bUseTDR>`），工程解析器会先修复再解析。

## 配置

`config.yaml`（随包内置）+ 环境变量覆盖：

```yaml
keil:
  uv4_path: "C:/Keil_v5/UV4/UV4.exe"        # 或环境变量 KEIL_UV4_PATH
  default_project_dir: ""                   # 或环境变量 KEIL_PROJECT_DIR
build:
  build_timeout: 300
  stream_progress: true
  tail_flush_wait: 3        # UV4 退出后等待日志尾部冲刷的秒数
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

## 端到端工作流示例

典型智能体会话（工具名以 DSH 前缀 `mcp__keil__` 显示）：

```text
1. mcp__keil__keil_doctor                       # 环境 + 探针就绪？
2. mcp__keil__discover_keil_projects            # 查找 .uvprojx 工程
3. mcp__keil__configure_keil_project            # 解析 targets/device/源文件
4. mcp__keil__build_project (stream_progress)   # 编译；若失败：
5. mcp__keil__parse_build_errors                # 结构化 errors[]
6. mcp__keil__explain_build_error               # 原因 + 修复建议
7. mcp__keil__source_edit                       # 修复代码（自动备份）
   → 回到 4 直到 0 错误
8. mcp__keil__flash_firmware (confirm=true)     # UV4 -f → "Verify OK"
9. mcp__keil__probe_connect + set_breakpoint    # 挂接调试器
10. mcp__keil__probe_read_registers / _memory   # 观察芯片状态
11. mcp__keil__read_rtt_log                     # 固件日志
    → 发现逻辑错误：source_edit → 重新编译 → 重新烧录
```

## 安全规则

| 级别 | 操作 | 默认要求 |
|---|---|---|
| 只读 | 芯片匹配、寄存器/内存/符号读取、日志 | 无需确认 |
| 执行 | halt / resume / step / reset | 提示 |
| 状态写 | 内存/寄存器写入、断点、watchpoint | 确认 |
| **持久破坏** | **Flash 擦除 / 烧录** | **显式确认 + 恢复方案** |
| 主机进程 | Keil 构建、GDB server | 提示 |

原则：先取证后动手；未知目标先识别芯片；烧录前确认目标 / 范围 / 镜像 / 恢复方法。

## 测试

```bash
pytest tests -q        # 11 个单元测试：日志解析、源码编辑、进度监控、工程解析
```

手动冒烟测试（位于 `tests/`）：

```bash
python tests/raw_handshake.py    # 裸 JSON-RPC initialize + tools/list（stdio）
python tests/func_test.py        # 通过 MCP 客户端 SDK 的端到端工具调用
```

## 故障排查

| 现象 | 原因 / 解决 |
|---|---|
| 烧录时报 `Target DLL has been cancelled` | pyOCD 仍占用探针。先调用 `probe_disconnect`（或交给探针租约处理），再使用 UV4 后端 `flash_firmware`。 |
| `UV4.exe not found` | 设置 `KEIL_UV4_PATH` 或配置 `keil.uv4_path`；用 `keil_doctor` 确认。 |
| `No module named keil_mcp_server` | venv 的 editable 安装指向旧路径——从当前检出目录重新安装：`pip install -e .` |
| `No target connected` | 检查探针接线 / 驱动；`keil_doctor` 会列出检测到的探针。 |
| 需要 `pyocd pack install` | 例如 `pyocd pack install stm32f103c8`，或将 pyOCD 指向 Keil DFP 目录。 |

## 路线图

- [ ] 发布到 PyPI 并注册进 MCP registry
- [ ] MCUBUDDY_TOOLSETS 风格的领域开关
- [ ] `set_breakpoint` 按名称的 ELF 符号解析
- [ ] RTOS 任务感知（FreeRTOS）
- [ ] GitHub Actions CI 跑单元测试
- [ ] Linux/macOS 支持说明（Keil 仅 Windows；pyOCD 部分跨平台）

## 贡献指南

欢迎贡献！请先开 issue 讨论改动，再提交 PR。参见 [CONTRIBUTING.md](CONTRIBUTING.md)（尚未创建——欢迎 PR 补充）。

## 许可证

[MIT](LICENSE) — 可自由使用、修改与分发（需保留署名）。
