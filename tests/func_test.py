"""End-to-end functional test: call tools through the MCP client."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SAMPLE_LOG = """Build target 'STM32F103C8'
compiling main.c...
main.c(25:1): error C2065: 'undeclared_var': undeclared identifier
linking...
Program Size: Code=5432 RO-data=432 RW-data=160 ZI-data=1024
"Objects\\app.axf" - 1 Error(s), 1 Warning(s).
Build Time Elapsed: 00:00:05
"""

HERE = Path(__file__).resolve().parent.parent
PROJ = str(HERE.parent / "deepseek-harness-master" / "example-project.uvprojx")


async def call(session, name, args):
    res = await session.call_tool(name, args)
    text = "".join(c.text for c in res.content) if res.content else str(res)
    return text


import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


OUT = open(str(HERE / "func_out_clean.txt"), "w", encoding="utf-8")


def log(*args):
    OUT.write(" ".join(str(a) for a in args) + "\n")
    OUT.flush()


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "keil_mcp_server"], cwd=str(HERE))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            log("=== keil_doctor ===")
            log(await call(session, "keil_doctor", {}))

            log("\n=== configure_keil_project (example-project.uvprojx) ===")
            log(await call(session, "configure_keil_project", {"project": PROJ}))

            log("\n=== parse_build_errors (sample log) ===")
            log(await call(session, "parse_build_errors", {"log_content": SAMPLE_LOG}))

            log("\n=== explain_build_error ===")
            log(await call(session, "explain_build_error", {"error_code": "L6218E", "message": "Undefined symbol UART_Init"}))

            log("\n=== source_read + source_edit on a scratch file ===")
            scratch = str(HERE / "scratch_test.c")
            open(scratch, "w", encoding="utf-8").write("int a = 1;\nint b = 2;\nint main(void) { return a + b; }\n")
            log(await call(session, "source_read", {"file": scratch}))
            log(await call(session, "source_edit", {"file": scratch, "start_line": 3, "end_line": 3, "new_content": "int main(void) { return a - b; }"}))
            log(await call(session, "source_read", {"file": scratch}))

            log("\n=== discover_keil_projects ===")
            log(await call(session, "discover_keil_projects", {"directory": str(HERE.parent)}))
            OUT.close()


asyncio.run(main())
