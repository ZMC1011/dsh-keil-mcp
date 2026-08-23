"""Keil5 MCP Server — compile / flash / debug closed-loop for DeepSeek Harness.

Implements the executable blueprint (keil-mcp-server-blueprint.md v1.0):
  * 8 core deliverable tools (build control / error parsing / source editing / UV4 debug)
  * McuBuddy-style project / probe / flash tools (self-contained implementation)
  * Execution boundary: session lock + worker thread + cancel protection
"""
__version__ = "0.1.0"
