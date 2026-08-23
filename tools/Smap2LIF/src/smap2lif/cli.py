"""Command-line interface for Smap2LIF."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from smap2lif import __version__
from smap2lif.converter import (
    ConversionOptions,
    ConversionResult,
    WarningLevel,
    convert_source_map,
    write_lif_file,
)
from smap2lif.source_map import load_source_map


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        prog="smap2lif",
        description=(
            "Convert a native 2D source-map JSON file into a validated "
            "LIF 1.0.0 document."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Smap2LIF {__version__}",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open the desktop interface.",
    )
    parser.add_argument(
        "--tk-smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Source-map JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination LIF JSON file.",
    )
    parser.add_argument(
        "--vehicle-type-id",
        help="Vehicle type ID used in node and edge properties.",
    )
    parser.add_argument(
        "--map-id",
        help="Map ID that must match the ID used by the robot.",
    )
    parser.add_argument(
        "--creator",
        default="Smap2LIF",
        help="Creator written to LIF metadata.",
    )
    parser.add_argument("--project-id")
    parser.add_argument("--layout-name")
    parser.add_argument("--layout-version")
    parser.add_argument(
        "--no-stations",
        action="store_true",
        help="Do not export station objects.",
    )
    parser.add_argument(
        "--allow-rotation-on-edges",
        action="store_true",
        help="Set rotationAllowed to true on every edge.",
    )
    parser.add_argument(
        "--accept-critical",
        action="store_true",
        help=(
            "Write the file even when safety-related source objects cannot "
            "be represented in LIF."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GUI or command-line conversion."""

    arguments = list(argv) if argv is not None else sys.argv[1:]
    if not arguments:
        from smap2lif.gui import main as gui_main

        return gui_main()

    parser = build_parser()
    options = parser.parse_args(arguments)
    if options.tk_smoke_test:
        return _run_tk_smoke_test()

    if options.gui:
        from smap2lif.gui import main as gui_main

        return gui_main()

    missing = [
        flag
        for flag, value in (
            ("--input", options.input),
            ("--output", options.output),
            ("--vehicle-type-id", options.vehicle_type_id),
            ("--map-id", options.map_id),
        )
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        parser.error(
            "command-line conversion requires " + ", ".join(missing)
        )

    try:
        source_map = load_source_map(options.input)
        result = convert_source_map(
            source_map,
            ConversionOptions(
                vehicle_type_id=options.vehicle_type_id,
                creator=options.creator,
                project_identification=options.project_id,
                layout_name=options.layout_name,
                layout_version=options.layout_version,
                map_id=options.map_id,
                include_stations=not options.no_stations,
                rotation_allowed=options.allow_rotation_on_edges,
            ),
        )
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    _print_report(result)
    if result.has_critical_warnings and not options.accept_critical:
        print(
            "Output was not written. Review the CRITICAL warnings and run "
            "again with --accept-critical only after confirming the risks.",
            file=sys.stderr,
        )
        return 2

    try:
        write_lif_file(result.document, options.output)
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1

    print(f"Output: {options.output}")
    return 0


def _run_tk_smoke_test() -> int:
    """Verify that the complete Tk runtime can create a hidden window."""

    root = None
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
    except Exception as exc:
        print(f"Tk runtime check failed: {exc}", file=sys.stderr)
        return 3
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    print("Tk runtime check: PASSED")
    return 0


def _print_report(result: ConversionResult) -> None:
    print("Official LIF schema validation: PASSED")
    print(f"Nodes: {result.node_count}")
    print(f"Edges: {result.edge_count}")
    print(f"Stations: {result.station_count}")
    print(f"Trajectories: {result.trajectory_count}")
    print(f"Node actions: {result.action_count}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            stream = (
                sys.stderr
                if warning.level is WarningLevel.CRITICAL
                else sys.stdout
            )
            print(f"- {warning.format()}", file=stream)
    else:
        print("Warnings: none")


__all__ = ["build_parser", "main"]
