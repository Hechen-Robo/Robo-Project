"""PyInstaller entry point for the Smap2LIF desktop application."""

from smap2lif.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
