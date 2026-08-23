"""Entry point: python -m keil_mcp_server"""
import sys


def main(argv=None) -> int:
    from keil_mcp_server.server import run_server
    return run_server(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
