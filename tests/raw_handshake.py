"""Bare-bones JSON-RPC handshake against keil_mcp_server over stdio."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PY = sys.executable
proc = subprocess.Popen(
    [PY, "-m", "keil_mcp_server"],
    cwd=str(HERE),
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, encoding="utf-8", errors="replace",
)

def send(obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()

def read_msg():
    line = proc.stdout.readline()
    return line

send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "rawtest", "version": "1.0"}}})
resp = read_msg()
print("RAW RESPONSE:", resp.strip()[:800])
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
resp2 = read_msg()
try:
    data = json.loads(resp2)
    tools = data.get("result", {}).get("tools", [])
    print("TOOLS:", len(tools))
    for t in sorted(tools, key=lambda x: x["name"]):
        print("  -", t["name"])
except Exception as e:
    print("PARSE FAIL:", resp2[:800], e)
proc.kill()
