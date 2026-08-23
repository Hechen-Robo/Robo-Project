"""Tkinter desktop interface for Smap2LIF."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from smap2lif.converter import (
    ConversionOptions,
    ConversionResult,
    WarningLevel,
    convert_source_map,
    write_lif_file,
)
from smap2lif.source_map import SourceMap, load_source_map


APP_NAME = "Smap2LIF"
APP_VERSION = "0.1.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION}"


@dataclass(frozen=True, slots=True)
class InspectionCompleted:
    """Successful source-map inspection returned by a worker thread."""

    path: Path
    source_map: SourceMap


@dataclass(frozen=True, slots=True)
class ConversionPrepared:
    """Validated conversion waiting for export or user review."""

    output_path: Path
    result: ConversionResult


@dataclass(frozen=True, slots=True)
class WorkerFailed:
    """Failure returned by a worker thread."""

    operation: str
    message: str


WorkerMessage = InspectionCompleted | ConversionPrepared | WorkerFailed


def suggested_output_path(input_path: str | Path) -> Path:
    """Return the default LIF output path for a source-map file."""

    source = Path(input_path)
    return source.with_name(f"{source.stem}_LIF_1.0.0.json")


def format_source_summary(source_map: SourceMap) -> str:
    """Build the source-map summary displayed in the GUI."""

    return "\n".join(
        [
            f"Map name: {source_map.map_name}",
            f"Source version: {source_map.source_version}",
            f"Resolution: {source_map.resolution:g} m",
            (
                "Bounds: "
                f"({source_map.minimum_position.x:g}, "
                f"{source_map.minimum_position.y:g}) to "
                f"({source_map.maximum_position.x:g}, "
                f"{source_map.maximum_position.y:g})"
            ),
            f"Topological points: {source_map.counts.points}",
            f"Topological curves: {source_map.counts.curves}",
            f"Occupancy positions: {source_map.counts.normal_positions}",
            f"Non-topological lines: {source_map.counts.lines}",
            f"Non-topological areas: {source_map.counts.areas}",
            f"External devices: {source_map.counts.external_devices}",
            f"Bin locations: {source_map.counts.bin_locations}",
            f"Source station tasks: {source_map.counts.bin_tasks}",
            _format_classes("Line types", source_map.line_classes),
            _format_classes("Area types", source_map.area_classes),
        ]
    )


def build_conversion_options(
    *,
    vehicle_type_id: str,
    creator: str,
    project_identification: str,
    layout_name: str,
    layout_version: str,
    map_id: str,
    include_stations: bool,
    rotation_allowed: bool,
) -> ConversionOptions:
    """Build normalized conversion options from GUI field values."""

    return ConversionOptions(
        vehicle_type_id=vehicle_type_id.strip(),
        creator=creator.strip(),
        project_identification=_blank_as_none(project_identification),
        layout_name=_blank_as_none(layout_name),
        layout_version=_blank_as_none(layout_version),
        map_id=_blank_as_none(map_id),
        include_stations=include_stations,
        rotation_allowed=rotation_allowed,
    )


def format_conversion_report(
    result: ConversionResult,
    output_path: str | Path,
) -> str:
    """Build the success report displayed in the GUI log."""

    lines = [
        "Conversion completed successfully.",
        f"Output: {Path(output_path)}",
        f"Nodes: {result.node_count}",
        f"Edges: {result.edge_count}",
        f"Stations: {result.station_count}",
        f"Trajectories: {result.trajectory_count}",
        f"Node actions: {result.action_count}",
        "Official LIF schema validation: PASSED",
    ]
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning.format()}" for warning in result.warnings)
    else:
        lines.append("Warnings: none")
    return "\n".join(lines)


def _blank_as_none(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


def _format_classes(label: str, values: tuple[str, ...]) -> str:
    if not values:
        return f"{label}: none"
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    details = ", ".join(
        f"{name}={count}" for name, count in sorted(counts.items())
    )
    return f"{label}: {details}"


class Smap2LifApplication:
    """Main desktop application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._worker_messages: Queue[WorkerMessage] = Queue()
        self._cached_source_path: Path | None = None
        self._cached_source_map: SourceMap | None = None
        self._last_output_path: Path | None = None
        self._busy = False
        self._closing = False

        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.vehicle_type_id_var = tk.StringVar()
        self.creator_var = tk.StringVar(value=APP_NAME)
        self.project_identification_var = tk.StringVar()
        self.layout_name_var = tk.StringVar()
        self.layout_version_var = tk.StringVar()
        self.map_id_var = tk.StringVar()
        self.include_stations_var = tk.BooleanVar(value=True)
        self.rotation_allowed_var = tk.BooleanVar(value=False)
        self.summary_var = tk.StringVar(
            value="Select a source-map JSON file to inspect it."
        )
        self.status_var = tk.StringVar(value="Ready")

        self._configure_window()
        self._configure_style()
        self._build_interface()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._process_worker_messages)

    def _configure_window(self) -> None:
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1020x840")
        self.root.minsize(900, 740)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        available_themes = style.theme_names()
        if "vista" in available_themes:
            style.theme_use("vista")
        elif "clam" in available_themes:
            style.theme_use("clam")

        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure(
            "Subtitle.TLabel",
            font=("Segoe UI", 10),
            foreground="#4b5563",
        )
        style.configure(
            "Section.TLabelframe.Label",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(18, 8),
        )

    def _build_interface(self) -> None:
        container = ttk.Frame(self.root, padding=(24, 20))
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(4, weight=1)

        self._build_header(container)
        self._build_file_section(container)
        self._build_settings_section(container)
        self._build_summary_section(container)
        self._build_log_section(container)
        self._build_action_section(container)

        self._busy_sensitive_widgets: tuple[ttk.Widget, ...] = (
            self.input_entry,
            self.input_button,
            self.output_entry,
            self.output_button,
            self.vehicle_type_entry,
            self.creator_entry,
            self.project_entry,
            self.layout_name_entry,
            self.layout_version_entry,
            self.map_id_entry,
            self.stations_checkbutton,
            self.rotation_checkbutton,
            self.convert_button,
        )

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Native 2D source map to LIF 1.0.0 converter",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(
            header,
            text=f"Version {APP_VERSION}",
            style="Subtitle.TLabel",
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_file_section(self, parent: ttk.Frame) -> None:
        section = self._section(parent, " Files ", row=1)
        section.columnconfigure(1, weight=1)

        self.input_entry, self.input_button = self._path_row(
            section,
            row=0,
            label="Source map",
            variable=self.input_path_var,
            command=self._browse_input,
        )
        self.output_entry, self.output_button = self._path_row(
            section,
            row=1,
            label="LIF output",
            variable=self.output_path_var,
            command=self._browse_output,
        )

    def _build_settings_section(self, parent: ttk.Frame) -> None:
        section = self._section(parent, " LIF settings ", row=2)
        section.columnconfigure(1, weight=1)
        section.columnconfigure(3, weight=1)

        self.vehicle_type_entry = self._field(
            section, 0, 0, "Vehicle type ID *", self.vehicle_type_id_var
        )
        self.creator_entry = self._field(
            section, 0, 2, "Creator *", self.creator_var
        )
        self.project_entry = self._field(
            section, 1, 0, "Project ID", self.project_identification_var
        )
        self.layout_name_entry = self._field(
            section, 1, 2, "Layout name", self.layout_name_var
        )
        self.layout_version_entry = self._field(
            section, 2, 0, "Layout version", self.layout_version_var
        )
        self.map_id_entry = self._field(
            section, 2, 2, "VDA 5050 map ID", self.map_id_var
        )

        option_frame = ttk.Frame(section)
        option_frame.grid(row=3, column=0, columnspan=4, sticky="w", pady=5)
        self.stations_checkbutton = ttk.Checkbutton(
            option_frame,
            text="Export stations",
            variable=self.include_stations_var,
        )
        self.stations_checkbutton.grid(row=0, column=0, padx=(0, 18))
        self.rotation_checkbutton = ttk.Checkbutton(
            option_frame,
            text="Allow rotation on edges",
            variable=self.rotation_allowed_var,
        )
        self.rotation_checkbutton.grid(row=0, column=1)

    def _build_summary_section(self, parent: ttk.Frame) -> None:
        section = self._section(parent, " Source-map summary ", row=3)
        ttk.Label(section, textvariable=self.summary_var, justify="left").grid(
            row=0, column=0, sticky="w"
        )

    def _build_log_section(self, parent: ttk.Frame) -> None:
        section = self._section(parent, " Conversion log ", row=4, expand=True)
        section.columnconfigure(0, weight=1)
        section.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            section,
            height=10,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def _build_action_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent)
        section.grid(row=5, column=0, sticky="ew")
        section.columnconfigure(1, weight=1)

        ttk.Label(section, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        self.progress = ttk.Progressbar(section, mode="indeterminate")
        self.progress.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        self.open_folder_button = ttk.Button(
            section,
            text="Open output folder",
            command=self._open_output_folder,
            state=tk.DISABLED,
        )
        self.open_folder_button.grid(row=0, column=2, padx=(0, 10))
        self.convert_button = ttk.Button(
            section,
            text="Convert to LIF",
            command=self._start_conversion,
            style="Primary.TButton",
        )
        self.convert_button.grid(row=0, column=3)

    def _section(
        self,
        parent: ttk.Frame,
        title: str,
        *,
        row: int,
        expand: bool = False,
    ) -> ttk.LabelFrame:
        section = ttk.LabelFrame(
            parent,
            text=title,
            style="Section.TLabelframe",
            padding=(14, 12),
        )
        section.grid(
            row=row,
            column=0,
            sticky="nsew" if expand else "ew",
            pady=(0, 12),
        )
        return section

    def _path_row(
        self,
        parent: ttk.Frame,
        *,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> tuple[ttk.Entry, ttk.Button]:
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=5
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        button = ttk.Button(parent, text="Browse...", command=command)
        button.grid(row=row, column=2, padx=(10, 0), pady=5)
        return entry, button

    def _field(
        self,
        parent: ttk.Frame,
        row: int,
        label_column: int,
        label: str,
        variable: tk.StringVar,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=label_column,
            sticky="w",
            padx=(0, 10),
            pady=5,
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(
            row=row,
            column=label_column + 1,
            sticky="ew",
            padx=(0, 18) if label_column == 0 else 0,
            pady=5,
        )
        return entry

    def _browse_input(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Select source-map JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return

        source_path = Path(selected)
        self.input_path_var.set(str(source_path))
        self.output_path_var.set(str(suggested_output_path(source_path)))
        self._cached_source_path = None
        self._cached_source_map = None
        self._start_inspection(source_path)

    def _browse_output(self) -> None:
        current_output = self.output_path_var.get().strip()
        if current_output:
            current_path = Path(current_output)
            initial_directory = current_path.parent
            initial_file = current_path.name
        else:
            input_text = self.input_path_var.get().strip()
            suggested = (
                suggested_output_path(input_text)
                if input_text
                else Path.cwd() / "converted_LIF_1.0.0.json"
            )
            initial_directory = suggested.parent
            initial_file = suggested.name

        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save LIF file",
            initialdir=str(initial_directory),
            initialfile=initial_file,
            defaultextension=".json",
            filetypes=[("LIF JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected:
            self.output_path_var.set(selected)

    def _start_inspection(self, source_path: Path) -> None:
        if self._busy:
            return

        self._set_busy(True, "Reading source map...")
        self._append_log(f"Reading source map: {source_path}")
        Thread(
            target=self._inspection_worker,
            args=(source_path,),
            daemon=True,
        ).start()

    def _inspection_worker(self, source_path: Path) -> None:
        try:
            source_map = load_source_map(source_path)
        except Exception as exc:
            self._worker_messages.put(
                WorkerFailed("Source-map inspection", str(exc))
            )
            return

        self._worker_messages.put(InspectionCompleted(source_path, source_map))

    def _start_conversion(self) -> None:
        if self._busy:
            return

        input_text = self.input_path_var.get().strip()
        output_text = self.output_path_var.get().strip()
        if not input_text:
            self._show_error("Select a source-map file.")
            return
        if not output_text:
            self._show_error("Select an output file.")
            return

        input_path = Path(input_text)
        output_path = Path(output_text)
        if not input_path.is_file():
            self._show_error(f"Source-map file does not exist:\n{input_path}")
            return
        if self._same_path(input_path, output_path):
            self._show_error("The output file must be different from the source file.")
            return
        if not self.vehicle_type_id_var.get().strip():
            self._show_error("Vehicle type ID is required.")
            self.vehicle_type_entry.focus_set()
            return
        if not self.creator_var.get().strip():
            self._show_error("Creator is required.")
            self.creator_entry.focus_set()
            return
        if not self.map_id_var.get().strip():
            self._show_error(
                "VDA 5050 map ID is required. It must match the map ID "
                "used by the robot."
            )
            self.map_id_entry.focus_set()
            return
        if output_path.exists() and not messagebox.askyesno(
            APP_NAME,
            f"The output file already exists.\n\n{output_path}\n\nReplace it?",
            parent=self.root,
        ):
            return

        options = build_conversion_options(
            vehicle_type_id=self.vehicle_type_id_var.get(),
            creator=self.creator_var.get(),
            project_identification=self.project_identification_var.get(),
            layout_name=self.layout_name_var.get(),
            layout_version=self.layout_version_var.get(),
            map_id=self.map_id_var.get(),
            include_stations=self.include_stations_var.get(),
            rotation_allowed=self.rotation_allowed_var.get(),
        )
        cached_source_map = self._matching_cached_map(input_path)

        self._set_busy(True, "Converting to LIF 1.0.0...")
        self._append_log(f"Starting conversion: {input_path}")
        Thread(
            target=self._conversion_worker,
            args=(input_path, output_path, options, cached_source_map),
            daemon=True,
        ).start()

    def _conversion_worker(
        self,
        input_path: Path,
        output_path: Path,
        options: ConversionOptions,
        cached_source_map: SourceMap | None,
    ) -> None:
        try:
            source_map = cached_source_map or load_source_map(input_path)
            result = convert_source_map(source_map, options)
        except Exception as exc:
            self._worker_messages.put(WorkerFailed("LIF conversion", str(exc)))
            return

        self._worker_messages.put(ConversionPrepared(output_path, result))

    def _process_worker_messages(self) -> None:
        if self._closing:
            return

        try:
            while True:
                self._handle_worker_message(self._worker_messages.get_nowait())
        except Empty:
            pass

        self.root.after(100, self._process_worker_messages)

    def _handle_worker_message(self, message: WorkerMessage) -> None:
        if isinstance(message, InspectionCompleted):
            self._handle_inspection_completed(message)
        elif isinstance(message, ConversionPrepared):
            self._handle_conversion_prepared(message)
        else:
            self._handle_worker_failed(message)

    def _handle_inspection_completed(self, message: InspectionCompleted) -> None:
        current_input = self.input_path_var.get().strip()
        if not current_input or not self._same_path(Path(current_input), message.path):
            self._set_busy(False, "Ready")
            return

        self._cached_source_path = message.path
        self._cached_source_map = message.source_map
        self.project_identification_var.set(message.source_map.map_name)
        self.layout_name_var.set(message.source_map.map_name)
        self.layout_version_var.set(message.source_map.source_version)
        self.map_id_var.set(message.source_map.map_name)

        summary = format_source_summary(message.source_map)
        self.summary_var.set(summary)
        self._append_log(f"Source map loaded successfully.\n{summary}")
        self._set_busy(False, "Source map ready")

    def _handle_conversion_prepared(self, message: ConversionPrepared) -> None:
        if message.result.has_critical_warnings:
            critical_warnings = "\n".join(
                f"- {warning.format()}"
                for warning in message.result.warnings
                if warning.level is WarningLevel.CRITICAL
            )
            should_export = messagebox.askyesno(
                f"{APP_NAME} - Critical review required",
                (
                    "The generated document passed the official LIF schema, "
                    "but safety-related source data could not be represented.\n\n"
                    f"{critical_warnings}\n\n"
                    "Export this reviewed draft anyway?"
                ),
                parent=self.root,
            )
            if not should_export:
                self._append_log(
                    "Export cancelled. No output file was written because "
                    "critical warnings were not accepted."
                )
                self._set_busy(False, "Export cancelled")
                return

        try:
            write_lif_file(
                message.result.document,
                message.output_path,
            )
        except Exception as exc:
            self._handle_worker_failed(
                WorkerFailed("LIF export", str(exc))
            )
            return

        self._last_output_path = message.output_path
        report = format_conversion_report(message.result, message.output_path)
        self._append_log(report)
        self._set_busy(False, "Conversion completed")
        messagebox.showinfo(APP_NAME, report, parent=self.root)

    def _handle_worker_failed(self, message: WorkerFailed) -> None:
        error_text = f"{message.operation} failed:\n{message.message}"
        self._append_log(error_text)
        self._set_busy(False, "Operation failed")
        self._show_error(error_text)

    def _matching_cached_map(self, input_path: Path) -> SourceMap | None:
        if self._cached_source_path is None or self._cached_source_map is None:
            return None
        if self._same_path(self._cached_source_path, input_path):
            return self._cached_source_map
        return None

    @staticmethod
    def _same_path(first: Path, second: Path) -> bool:
        try:
            return first.resolve() == second.resolve()
        except OSError:
            return False

    def _set_busy(self, busy: bool, status: str) -> None:
        self._busy = busy
        self.status_var.set(status)
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in self._busy_sensitive_widgets:
            widget.configure(state=state)

        if busy:
            self.progress.start(12)
            self.open_folder_button.configure(state=tk.DISABLED)
        else:
            self.progress.stop()
            folder_state = tk.NORMAL if self._last_output_path else tk.DISABLED
            self.open_folder_button.configure(state=folder_state)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        if self.log_text.index("end-1c") != "1.0":
            self.log_text.insert(tk.END, "\n\n")
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _show_error(self, message: str) -> None:
        messagebox.showerror(APP_NAME, message, parent=self.root)

    def _open_output_folder(self) -> None:
        if self._last_output_path is None:
            return

        directory = self._last_output_path.parent
        try:
            if sys.platform == "win32":
                startfile = getattr(os, "startfile")
                startfile(str(directory))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(directory)])
            else:
                subprocess.Popen(["xdg-open", str(directory)])
        except OSError as exc:
            self._show_error(f"Could not open output folder:\n{exc}")

    def _on_close(self) -> None:
        if self._busy and not messagebox.askyesno(
            APP_NAME,
            "An operation is still running.\nClose the application anyway?",
            parent=self.root,
        ):
            return

        self._closing = True
        self.root.destroy()


def main() -> int:
    """Start the desktop application."""

    root = tk.Tk()
    Smap2LifApplication(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "Smap2LifApplication",
    "build_conversion_options",
    "format_conversion_report",
    "format_source_summary",
    "main",
    "suggested_output_path",
]
