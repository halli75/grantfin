"""Entry point: `python -m grant_scout` starts the MCP server over stdio."""

from .server import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
