"""Structured UV4 log parsing (blueprint §7.2)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..models import BuildSummary, CompileError

# Official format:  main.c(25:1): error C2065: 'x': undeclared identifier
ERROR_PATTERN = re.compile(
    r'^(?P<file>.+?)\((?P<line>\d+):(?P<col>\d+)\):\s+'
    r'(?P<sev>error|warning|note)\s+(?P<code>[A-Za-z]?\d+):\s+(?P<msg>.+)$',
    re.MULTILINE)
# Link errors:  .\app.axf: Error: L6218E: Undefined symbol ...
LINK_PATTERN = re.compile(
    r'^(?P<file>.+?):\s+(?P<sev>Error|Warning):\s+(?P<code>[A-Z]\d+\w*):\s+(?P<msg>.+)$',
    re.MULTILINE)
SIZE_PATTERN = re.compile(
    r'Program Size: Code=(?P<code>\d+) RO-data=(?P<ro>\d+) '
    r'RW-data=(?P<rw>\d+) ZI-data=(?P<zi>\d+)', re.MULTILINE)
RESULT_PATTERN = re.compile(
    r'(?P<errs>\d+) Error\(s\), (?P<warns>\d+) Warning\(s\)', re.MULTILINE)
TIME_PATTERN = re.compile(r'Build Time Elapsed:\s*(?P<t>.+)')
OUTPUT_PATTERN = re.compile(r'"([^"]+\.(?:axf|hex|bin))"')

# C-syntax style errors (gcc/armclang may emit):  main.c:25:5: error: ...
GCC_PATTERN = re.compile(
    r'^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s+'
    r'(?P<sev>error|warning|note):\s+(?P<msg>.+)$', re.MULTILINE)

_ERROR_CODES = re.compile(r'\bC\d{4}\b|\bL\d{4}\w?\b')


class UV4LogParser:
    """Parse UV4 build logs into structured errors + summary."""

    def __init__(self, max_errors: int = 200):
        self.max_errors = max_errors

    def parse(self, log: str) -> Tuple[List[CompileError], BuildSummary]:
        errors: List[CompileError] = []
        seen = set()

        def add(err: CompileError) -> None:
            key = (err.file, err.line, err.code, err.message)
            if key in seen:
                return
            seen.add(key)
            if err.severity == "error" and len([e for e in errors if e.severity == "error"]) < self.max_errors:
                errors.append(err)
            elif err.severity in ("warning", "note"):
                errors.append(err)

        for m in ERROR_PATTERN.finditer(log):
            add(CompileError(
                file=m.group("file"), line=int(m.group("line")),
                column=int(m.group("col")), severity=m.group("sev").lower(),
                code=m.group("code"), message=m.group("msg")))
        for m in LINK_PATTERN.finditer(log):
            add(CompileError(
                file=m.group("file"), line=0, column=0,
                severity=m.group("sev").lower(), code=m.group("code"),
                message=m.group("msg")))
        for m in GCC_PATTERN.finditer(log):
            add(CompileError(
                file=m.group("file"), line=int(m.group("line")),
                column=int(m.group("col")), severity=m.group("sev").lower(),
                code="", message=m.group("msg")))

        # summary
        size = SIZE_PATTERN.search(log)
        res = RESULT_PATTERN.search(log)
        errs = int(res.group("errs")) if res else len([e for e in errors if e.severity == "error"])
        warns = int(res.group("warns")) if res else len([e for e in errors if e.severity == "warning"])
        tm = TIME_PATTERN.search(log)
        out = OUTPUT_PATTERN.search(log)
        summary = BuildSummary(
            success=errs == 0,
            errors=errs,
            warnings=warns,
            code_size=int(size.group("code")) if size else 0,
            ro_data=int(size.group("ro")) if size else 0,
            rw_data=int(size.group("rw")) if size else 0,
            zi_data=int(size.group("zi")) if size else 0,
            build_time=tm.group("t").strip() if tm else "",
            output_file=out.group(1) if out else "",
        )
        return errors, summary


ERROR_KNOWLEDGE: dict[str, dict] = {
    "C2065": {
        "explanation": "undeclared identifier — 使用了未声明/未包含头文件的标识符。",
        "common_causes": [
            "变量或函数未声明即使用",
            "缺少 #include 头文件",
            "宏或类型拼写错误",
            "头文件中的声明被 #ifdef 条件编译排除",
        ],
        "suggested_fixes": [
            "检查该标识符拼写与声明位置",
            "确认所需头文件已 #include 且路径正确",
            "确认条件编译宏（如 USE_HAL_DRIVER）已定义",
        ],
    },
    "C2061": {
        "explanation": "syntax error: identifier — 语法错误，通常是缺分号、括号不匹配或前向声明缺失。",
        "common_causes": ["缺分号", "括号不匹配", "结构体/枚举未定义即引用"],
        "suggested_fixes": ["检查上一行是否缺 ';'", "确认结构体类型已定义", "检查括号配对"],
    },
    "C2064": {
        "explanation": "term does not evaluate to a function — 把变量当函数调用。",
        "common_causes": ["函数指针用法错误", "漏了调用括号", "宏展开异常"],
        "suggested_fixes": ["检查调用对象是否为函数/函数指针", "检查宏定义"],
    },
    "C2099": {
        "explanation": "initializer is not a constant — 初始化器不是编译期常量。",
        "common_causes": ["用运行时值初始化静态/全局变量", "数组大小使用非常量"],
        "suggested_fixes": ["改用编译期常量表达式", "或改为运行时赋值"],
    },
    "C2450": {
        "explanation": "undefined symbol — 链接期符号未定义。",
        "common_causes": ["对应 .c 文件未加入工程", "函数名拼写不一致", "库未链接", "弱符号/条件编译导致缺失"],
        "suggested_fixes": ["确认定义该符号的源文件在工程中", "检查 extern 声明与定义签名一致", "检查链接库配置"],
    },
    "L6218E": {
        "explanation": "Undefined symbol — 链接错误：引用的符号在整个工程+库中找不到定义。",
        "common_causes": [
            "定义该符号的 .c 文件未加入工程",
            "符号拼写不一致（大小写/下划线）",
            "未链接对应 .lib 库",
            "条件编译导致定义被排除",
        ],
        "suggested_fixes": [
            "在 .uvprojx 中把定义文件加入对应 Group",
            "核对声明与定义签名（extern/static/返回值）",
            "检查分散加载文件与库路径",
        ],
    },
    "L6220E": {
        "explanation": "Insufficient memory region attributes — 内存区域属性不足，常见于变量放入只读区域。",
        "common_causes": ["变量定义在 const/ROM 区", "分散加载文件区域属性错误"],
        "suggested_fixes": ["检查变量存储类型", "检查 .sct 分散加载文件"],
    },
    "L6406E": {
        "explanation": "No space in execution regions with attributes — 内存溢出（RAM/Flash 空间不足）。",
        "common_causes": ["代码/数据超过芯片容量", "ZI 段过大", "分散加载文件区域配置错误"],
        "suggested_fixes": [
            "查看 Program Size 各段数值对比芯片规格",
            "优化代码（-O2/-Os）、减小缓冲区",
            "检查 .sct 文件区域大小",
        ],
    },
    "L6407E": {
        "explanation": "Sections of aggregate size exceed region limit — 段总大小超出区域上限，内存溢出。",
        "common_causes": ["RAM 或 Flash 溢出"],
        "suggested_fixes": ["对照 Program Size 与芯片内存规格", "精简代码/数据", "调整链接区域"],
    },
    "L6328W": {
        "explanation": "Conflicting section attributes — 冲突的段属性警告，通常无碍但应检查。",
        "common_causes": ["同一符号在不同文件中属性不同"],
        "suggested_fixes": ["统一 extern/static 与 const 声明"],
    },
}

DEFAULT_EXPLANATION = {
    "explanation": "未知错误码 — 请结合完整日志与上下文判断。",
    "common_causes": ["错误码不在内置知识库", "可能是 armclang/编译环境特有错误"],
    "suggested_fixes": ["提供完整 build_log 以获取上下文", "检查出错行附近代码", "查阅 Keil 编译器手册中的错误码说明"],
}


def explain_error(error_code: str, message: str = "", file: str = "", line: int = 0) -> dict:
    """Map an error code to explanation + causes + fixes (blueprint §6.1-B)."""
    code = (error_code or "").strip()
    if not code and message:
        m = _ERROR_CODES.search(message)
        code = m.group(0) if m else ""
    entry = ERROR_KNOWLEDGE.get(code.upper(), DEFAULT_EXPLANATION)
    return {
        "error_code": code,
        "message": message,
        "file": file,
        "line": line,
        **entry,
    }
