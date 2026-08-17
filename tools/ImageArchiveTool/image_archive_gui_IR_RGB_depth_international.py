import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
import locale
from datetime import datetime
from pathlib import Path, PurePosixPath
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp"
}

SUPPORTED_ARCHIVES = {".zip", ".7z", ".rar"}
OUTPUT_CATEGORIES = ("IR", "RGB", "depth")
NUMBER_WIDTH = 8
APP_NAME = "Image Archive Tool"
ICON_FILENAME = "ImageArchiveTool.ico"


def resource_path(filename):
    """Resolve bundled resources both in source mode and PyInstaller one-file mode."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / filename


TRANSLATIONS = {
    "zh": {
        "window_title": APP_NAME,
        "headline": "图像批量提取 → IR / RGB / depth 分类 → 统一编号 → ZIP 压缩",
        "language": "语言",
        "step1": "1. 选择原始压缩文件",
        "select_archive": "选择压缩包",
        "info": (
            "支持输入：ZIP / 7Z / RAR。程序会递归扫描每个数据子文件夹。\n"
            "每个完整数据组应包含 1 张 IR、1 张 RGB/Color、1 张 depth 图片；同组使用完全相同的 8 位编号。\n"
            "输出 ZIP 根目录示例：IR/00000001.png、RGB/00000001.jpg、depth/00000001.png。\n"
            "不完整的数据组会跳过并在日志中提示，避免 IR / RGB / depth 错位。\n"
            "导出时只需填写基础文件名，程序会自动追加 YYYYMMDD_HHMMSS 时间戳。"
        ),
        "step2": "2. 开始处理",
        "log_frame": "处理日志",
        "status_initial": "请选择 ZIP / 7Z / RAR 压缩文件。",
        "status_selected": "已选择压缩包，点击“开始处理”。",
        "status_processing": "正在处理...",
        "status_extracting": "正在解压 {archive_type} 压缩包...",
        "status_pairing": "正在扫描并配对 IR / RGB / depth...",
        "status_ready_export": "已整理 {groups} 组 / {images} 张图片。请选择 ZIP 基础文件名和保存位置。",
        "status_cancelled": "已取消导出。",
        "status_creating_zip": "正在创建 ZIP 压缩文件...",
        "status_complete": "完成：{groups} 组，共 {images} 张图片。",
        "status_failed": "处理失败。",
        "dialog_select_title": "选择包含图像数据的压缩文件",
        "filetype_supported": "支持的压缩文件",
        "filetype_zip": "ZIP 压缩文件",
        "filetype_7z": "7Z 压缩文件",
        "filetype_rar": "RAR 压缩文件",
        "filetype_all": "所有文件",
        "dialog_save_title": "设置 ZIP 基础文件名和导出位置（时间戳自动追加）",
        "error": "错误",
        "unsupported": "格式不支持",
        "invalid_archive": "请选择有效的压缩文件。",
        "unsupported_archive": "请选择 ZIP、7Z 或 RAR 格式的压缩文件。",
        "invalid_zip": "所选文件不是有效的 ZIP 压缩文件。",
        "unsafe_path": "压缩包中发现不安全路径：{member}",
        "sevenzip_read_failed": "7-Zip 无法读取该压缩包。\n\n{details}",
        "sevenzip_extract_failed": "7-Zip 解压失败。\n\n{details}",
        "py7zr_failed": "py7zr 解压失败，尝试使用 7-Zip：{error}",
        "using_7zip": "使用 7-Zip 解压：{path}",
        "using_7zip_rar": "使用 7-Zip 解压 RAR：{path}",
        "no_7z_backend": (
            "无法解压 7Z 文件。\n\n"
            "请任选一种方式：\n"
            "1. 安装 Python 包：pip install py7zr\n"
            "2. 安装 7-Zip，并确保 7z.exe 可被程序找到。"
        ),
        "unrar_read_failed": "UnRAR 无法读取该 RAR 压缩包。\n\n{details}",
        "unrar_extract_failed": "UnRAR 解压失败。\n\n{details}",
        "using_unrar": "使用 UnRAR 解压 RAR：{path}",
        "rar_extract_failed": (
            "RAR 解压失败。RAR 通常需要系统中安装 7-Zip、UnRAR 或其他 rarfile 后端。\n\n"
            "详细错误：{error}"
        ),
        "no_rar_backend": (
            "无法解压 RAR 文件。\n\n"
            "推荐安装 7-Zip 或 WinRAR。程序会自动查找 7z.exe / UnRAR.exe 并直接支持 RAR。\n"
            "也可以安装 rarfile：pip install rarfile，但 rarfile 通常仍需要系统解压后端。"
        ),
        "extracting_log": "正在解压 {name} ...",
        "unsupported_format_runtime": "不支持的压缩格式：{suffix}",
        "no_images": "压缩包中没有找到支持的图片文件。",
        "scanned_images": "共扫描到 {count} 张图片。",
        "unclassified_header": "有 {count} 张图片无法识别类型，已忽略：",
        "unclassified_more": "  ... 其余 {count} 张省略显示",
        "skip_group": "跳过不完整/重复的数据组：{group} ({counts})",
        "no_complete_groups": (
            "没有找到完整的 IR + RGB + depth 数据组。\n\n"
            "请确认每个原始数据子文件夹中各有 1 张 IR、RGB/Color 和 depth 图片，"
            "并且文件名中包含相应关键词。"
        ),
        "build_groups": "正在按原始子文件夹建立数据组...",
        "complete_groups": "完整数据组：{count} 组。",
        "skipped_groups": "跳过异常数据组：{count} 组。",
        "group_mapping": "[{current}/{total}] {group}  →  IR/{number} | RGB/{number} | depth/{number}",
        "cancelled_export": "用户取消了导出。",
        "final_export": "最终导出文件：{path}",
        "done": "完成",
        "log_done": "处理完成。",
        "log_complete_groups": "完整数据组：{count}",
        "log_image_count": "图片数量：{count}",
        "log_skipped": "跳过异常组：{count}",
        "log_zip": "ZIP 文件：{path}",
        "complete_extra": "\n跳过异常/不完整数据组：{count} 组",
        "complete_message": (
            "处理完成！\n\n"
            "完整数据组：{groups} 组\n"
            "共导出图片：{images} 张{extra}\n\n"
            "ZIP 文件已保存到：\n{path}"
        ),
        "failed_title": "处理失败",
        "failed_log": "处理失败：{error}",
        "selected_log": "已选择：{path}",
        "start_log": "开始处理：{name}",
    },
    "en": {
        "window_title": APP_NAME,
        "headline": "Batch Extract → IR / RGB / depth → Unified Numbering → ZIP",
        "language": "Language",
        "step1": "1. Select source archive",
        "select_archive": "Select archive",
        "info": (
            "Supported input: ZIP / 7Z / RAR. The program recursively scans each data subfolder.\n"
            "Each complete data group must contain exactly 1 IR, 1 RGB/Color, and 1 depth image; all three use the same 8-digit ID.\n"
            "Example ZIP root: IR/00000001.png, RGB/00000001.jpg, depth/00000001.png.\n"
            "Incomplete or duplicated groups are skipped and reported in the log to prevent IR / RGB / depth misalignment.\n"
            "When exporting, enter only the base filename; YYYYMMDD_HHMMSS is appended automatically."
        ),
        "step2": "2. Start processing",
        "log_frame": "Processing log",
        "status_initial": "Select a ZIP / 7Z / RAR archive.",
        "status_selected": "Archive selected. Click “Start processing”.",
        "status_processing": "Processing...",
        "status_extracting": "Extracting {archive_type} archive...",
        "status_pairing": "Scanning and matching IR / RGB / depth...",
        "status_ready_export": "Organized {groups} groups / {images} images. Choose a ZIP base filename and save location.",
        "status_cancelled": "Export cancelled.",
        "status_creating_zip": "Creating ZIP archive...",
        "status_complete": "Done: {groups} groups, {images} images.",
        "status_failed": "Processing failed.",
        "dialog_select_title": "Select an archive containing image data",
        "filetype_supported": "Supported archives",
        "filetype_zip": "ZIP archive",
        "filetype_7z": "7Z archive",
        "filetype_rar": "RAR archive",
        "filetype_all": "All files",
        "dialog_save_title": "Set ZIP base filename and export location (timestamp added automatically)",
        "error": "Error",
        "unsupported": "Unsupported format",
        "invalid_archive": "Please select a valid archive file.",
        "unsupported_archive": "Please select a ZIP, 7Z, or RAR archive.",
        "invalid_zip": "The selected file is not a valid ZIP archive.",
        "unsafe_path": "Unsafe path detected in archive: {member}",
        "sevenzip_read_failed": "7-Zip could not read this archive.\n\n{details}",
        "sevenzip_extract_failed": "7-Zip extraction failed.\n\n{details}",
        "py7zr_failed": "py7zr extraction failed; trying 7-Zip: {error}",
        "using_7zip": "Extracting with 7-Zip: {path}",
        "using_7zip_rar": "Extracting RAR with 7-Zip: {path}",
        "no_7z_backend": (
            "Unable to extract the 7Z file.\n\n"
            "Use either option below:\n"
            "1. Install the Python package: pip install py7zr\n"
            "2. Install 7-Zip and make sure the program can find 7z.exe."
        ),
        "unrar_read_failed": "UnRAR could not read this RAR archive.\n\n{details}",
        "unrar_extract_failed": "UnRAR extraction failed.\n\n{details}",
        "using_unrar": "Extracting RAR with UnRAR: {path}",
        "rar_extract_failed": (
            "RAR extraction failed. RAR normally requires 7-Zip, UnRAR, or another rarfile backend installed on the system.\n\n"
            "Details: {error}"
        ),
        "no_rar_backend": (
            "Unable to extract the RAR file.\n\n"
            "Installing 7-Zip or WinRAR is recommended. The program automatically searches for 7z.exe / UnRAR.exe.\n"
            "You can also install rarfile with: pip install rarfile, but rarfile usually still requires a system extraction backend."
        ),
        "extracting_log": "Extracting {name} ...",
        "unsupported_format_runtime": "Unsupported archive format: {suffix}",
        "no_images": "No supported image files were found in the archive.",
        "scanned_images": "Scanned {count} images in total.",
        "unclassified_header": "{count} images could not be classified and were ignored:",
        "unclassified_more": "  ... {count} additional images omitted from the log",
        "skip_group": "Skipping incomplete/duplicated group: {group} ({counts})",
        "no_complete_groups": (
            "No complete IR + RGB + depth data groups were found.\n\n"
            "Make sure each original data subfolder contains exactly 1 IR, 1 RGB/Color, and 1 depth image, "
            "and that the filenames contain the corresponding keywords."
        ),
        "build_groups": "Building data groups from the original subfolders...",
        "complete_groups": "Complete data groups: {count}.",
        "skipped_groups": "Skipped abnormal groups: {count}.",
        "group_mapping": "[{current}/{total}] {group}  →  IR/{number} | RGB/{number} | depth/{number}",
        "cancelled_export": "Export cancelled by user.",
        "final_export": "Final export file: {path}",
        "done": "Done",
        "log_done": "Processing complete.",
        "log_complete_groups": "Complete data groups: {count}",
        "log_image_count": "Image count: {count}",
        "log_skipped": "Skipped abnormal groups: {count}",
        "log_zip": "ZIP file: {path}",
        "complete_extra": "\nSkipped abnormal/incomplete groups: {count}",
        "complete_message": (
            "Processing complete!\n\n"
            "Complete data groups: {groups}\n"
            "Images exported: {images}{extra}\n\n"
            "ZIP file saved to:\n{path}"
        ),
        "failed_title": "Processing failed",
        "failed_log": "Processing failed: {error}",
        "selected_log": "Selected: {path}",
        "start_log": "Starting: {name}",
    }
}



def detect_default_language():
    """Detect the operating system UI language.

    Chinese UI -> Chinese. Any other/unknown UI language -> English.
    English is intentionally the fallback so an international user is never
    trapped in a Chinese-only first-launch interface.
    """
    locale_name = ""

    # Windows: GetUserDefaultUILanguage reflects the Windows display/UI locale
    # more reliably than environment variables.
    if os.name == "nt":
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            locale_name = locale.windows_locale.get(lang_id, "") or ""
        except Exception:
            pass

    # Cross-platform fallback.
    if not locale_name:
        try:
            locale_name = locale.getlocale()[0] or ""
        except Exception:
            locale_name = ""

    if not locale_name:
        locale_name = (
            os.environ.get("LC_ALL")
            or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG")
            or ""
        )

    normalized = locale_name.lower().replace("-", "_")
    return "zh" if normalized.startswith("zh") else "en"


class ImageArchiveGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry("900x640")
        self.root.minsize(800, 560)
        self.root.title(APP_NAME)

        # Use the same branded icon in the window as in the packaged EXE.
        try:
            icon_path = resource_path(ICON_FILENAME)
            if icon_path.is_file():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            # The application should still start even if a platform cannot apply .ico files.
            pass

        self.lang = detect_default_language()
        self.language_display = tk.StringVar(
            value="中文 (Chinese)" if self.lang == "zh" else "English"
        )
        self.input_archive = tk.StringVar()
        self.status_text = tk.StringVar()
        self.progress_value = tk.DoubleVar(value=0)

        self._status_key = "status_initial"
        self._status_kwargs = {}

        self.work_dir = None
        self.processed_dir = None
        self.processed_count = 0
        self.group_count = 0
        self.skipped_group_count = 0

        self.build_ui()
        self.refresh_ui_language()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def t(self, key, **kwargs):
        text = TRANSLATIONS[self.lang][key]
        return text.format(**kwargs) if kwargs else text

    def set_status_key(self, key, **kwargs):
        self._status_key = key
        self._status_kwargs = kwargs
        text = self.t(key, **kwargs)
        self.root.after(0, lambda value=text: self.status_text.set(value))

    def build_ui(self):
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 14))

        self.headline_label = ttk.Label(
            header,
            font=("Microsoft YaHei UI", 15, "bold")
        )
        self.headline_label.pack(side="left", anchor="w", fill="x", expand=True)

        language_frame = ttk.Frame(header)
        language_frame.pack(side="right", padx=(12, 0))

        # Keep this label bilingual at all times so a user who cannot read
        # the current UI language can still find the language control.
        self.language_label = ttk.Label(
            language_frame,
            text="🌐 Language / 语言"
        )
        self.language_label.pack(side="left", padx=(0, 6))

        self.language_combo = ttk.Combobox(
            language_frame,
            textvariable=self.language_display,
            values=("English", "中文 (Chinese)"),
            state="readonly",
            width=14
        )
        self.language_combo.pack(side="left")
        self.language_combo.bind("<<ComboboxSelected>>", self.change_language)

        self.input_frame = ttk.LabelFrame(main, padding=12)
        self.input_frame.pack(fill="x")

        entry = ttk.Entry(self.input_frame, textvariable=self.input_archive)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.select_button = ttk.Button(
            self.input_frame,
            command=self.select_archive
        )
        self.select_button.pack(side="right")

        self.info_label = ttk.Label(
            main,
            justify="left",
            wraplength=850
        )
        self.info_label.pack(anchor="w", pady=14)

        control_frame = ttk.Frame(main)
        control_frame.pack(fill="x")

        self.start_button = ttk.Button(
            control_frame,
            command=self.start_processing
        )
        self.start_button.pack(side="left")

        self.progress = ttk.Progressbar(
            control_frame,
            variable=self.progress_value,
            maximum=100
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(14, 0))

        ttk.Label(
            main,
            textvariable=self.status_text
        ).pack(anchor="w", pady=(10, 8))

        self.log_frame = ttk.LabelFrame(main, padding=8)
        self.log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            self.log_frame,
            height=18,
            wrap="word",
            state="disabled"
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            self.log_frame,
            orient="vertical",
            command=self.log_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def change_language(self, _event=None):
        self.lang = "zh" if self.language_display.get().startswith("中文") else "en"
        self.refresh_ui_language()

    def refresh_ui_language(self):
        self.root.title(APP_NAME)
        self.headline_label.configure(text=self.t("headline"))
        self.input_frame.configure(text=self.t("step1"))
        self.select_button.configure(text=self.t("select_archive"))
        self.info_label.configure(text=self.t("info"))
        self.start_button.configure(text=self.t("step2"))
        self.log_frame.configure(text=self.t("log_frame"))
        self.status_text.set(self.t(self._status_key, **self._status_kwargs))

    def log(self, text):
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, append)

    def set_progress(self, value):
        self.root.after(0, lambda: self.progress_value.set(value))

    def select_archive(self):
        path = filedialog.askopenfilename(
            title=self.t("dialog_select_title"),
            filetypes=[
                (self.t("filetype_supported"), "*.zip *.7z *.rar"),
                (self.t("filetype_zip"), "*.zip"),
                (self.t("filetype_7z"), "*.7z"),
                (self.t("filetype_rar"), "*.rar"),
                (self.t("filetype_all"), "*.*")
            ]
        )
        if path:
            self.input_archive.set(path)
            self.set_status_key("status_selected")
            self.log(self.t("selected_log", path=path))

    def start_processing(self):
        archive_path = Path(self.input_archive.get().strip())

        if not archive_path.is_file():
            messagebox.showerror(self.t("error"), self.t("invalid_archive"))
            return

        suffix = archive_path.suffix.lower()
        if suffix not in SUPPORTED_ARCHIVES:
            messagebox.showerror(
                self.t("unsupported"),
                self.t("unsupported_archive")
            )
            return

        if suffix == ".zip" and not zipfile.is_zipfile(archive_path):
            messagebox.showerror(self.t("error"), self.t("invalid_zip"))
            return

        self.cleanup_temp()
        self.start_button.configure(state="disabled")
        self.progress_value.set(0)
        self.set_status_key("status_processing")
        self.log("=" * 68)
        self.log(self.t("start_log", name=archive_path.name))

        thread = threading.Thread(
            target=self.process_archive,
            args=(archive_path,),
            daemon=True
        )
        thread.start()

    def validate_member_path(self, destination, member_name):
        """Reject absolute paths and ../ traversal before extraction."""
        normalized = member_name.replace("\\", "/")
        pure = PurePosixPath(normalized)

        if pure.is_absolute() or ".." in pure.parts:
            raise RuntimeError(self.t("unsafe_path", member=member_name))

        destination = destination.resolve()
        target = (destination / Path(*pure.parts)).resolve()
        try:
            target.relative_to(destination)
        except ValueError as exc:
            raise RuntimeError(self.t("unsafe_path", member=member_name)) from exc

    def safe_extract_zip(self, archive_path, destination):
        destination = destination.resolve()

        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.infolist()
            total = max(len(members), 1)

            for member in members:
                self.validate_member_path(destination, member.filename)

            for index, member in enumerate(members, start=1):
                zf.extract(member, destination)
                self.set_progress(index / total * 35)

    @staticmethod
    def find_7zip_executable():
        """Find 7-Zip on PATH or in common Windows install locations."""
        for command in ("7z", "7zz", "7za"):
            found = shutil.which(command)
            if found:
                return found

        if os.name == "nt":
            candidates = []
            for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
                base = os.environ.get(env_name)
                if base:
                    candidates.append(Path(base) / "7-Zip" / "7z.exe")

            local_appdata = os.environ.get("LOCALAPPDATA")
            if local_appdata:
                candidates.append(Path(local_appdata) / "Programs" / "7-Zip" / "7z.exe")

            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)

        return None

    @staticmethod
    def find_unrar_executable():
        """Find UnRAR/WinRAR command line extractor when available."""
        for command in ("unrar", "UnRAR"):
            found = shutil.which(command)
            if found:
                return found

        if os.name == "nt":
            candidates = []
            for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
                base = os.environ.get(env_name)
                if base:
                    candidates.append(Path(base) / "WinRAR" / "UnRAR.exe")

            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)

        return None

    @staticmethod
    def _subprocess_kwargs():
        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace"
        }
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return kwargs

    def validate_archive_with_7zip(self, seven_zip, archive_path, destination):
        """List archive contents with 7-Zip and validate member paths first."""
        cmd = [seven_zip, "l", "-slt", "-sccUTF-8", str(archive_path)]
        result = subprocess.run(cmd, **self._subprocess_kwargs())
        if result.returncode != 0:
            raise RuntimeError(
                self.t("sevenzip_read_failed", details=result.stdout[-2000:])
            )

        in_items = False
        for line in result.stdout.splitlines():
            if line.strip().startswith("----------"):
                in_items = True
                continue
            if in_items and line.startswith("Path = "):
                member_name = line[7:].strip()
                if member_name:
                    self.validate_member_path(destination, member_name)

    def extract_with_7zip(self, seven_zip, archive_path, destination):
        self.validate_archive_with_7zip(seven_zip, archive_path, destination)
        cmd = [
            seven_zip,
            "x",
            str(archive_path),
            f"-o{destination}",
            "-y",
            "-sccUTF-8",
            "-bso0",
            "-bsp0"
        ]
        result = subprocess.run(cmd, **self._subprocess_kwargs())
        if result.returncode != 0:
            raise RuntimeError(
                self.t("sevenzip_extract_failed", details=result.stdout[-2000:])
            )
        self.set_progress(35)

    def safe_extract_7z(self, archive_path, destination):
        try:
            import py7zr  # type: ignore
        except ImportError:
            py7zr = None

        if py7zr is not None:
            try:
                with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                    names = archive.getnames()
                    for name in names:
                        self.validate_member_path(destination, name)
                    archive.extractall(path=destination)
                self.set_progress(35)
                return
            except Exception as exc:
                self.log(self.t("py7zr_failed", error=exc))

        seven_zip = self.find_7zip_executable()
        if seven_zip:
            self.log(self.t("using_7zip", path=seven_zip))
            self.extract_with_7zip(seven_zip, archive_path, destination)
            return

        raise RuntimeError(self.t("no_7z_backend"))

    def extract_with_unrar(self, unrar, archive_path, destination):
        list_cmd = [unrar, "lb", str(archive_path)]
        listed = subprocess.run(list_cmd, **self._subprocess_kwargs())
        if listed.returncode != 0:
            raise RuntimeError(
                self.t("unrar_read_failed", details=listed.stdout[-2000:])
            )

        for line in listed.stdout.splitlines():
            member_name = line.strip()
            if member_name:
                self.validate_member_path(destination, member_name)

        extract_cmd = [
            unrar, "x", "-o+", "-y", str(archive_path), str(destination) + os.sep
        ]
        result = subprocess.run(extract_cmd, **self._subprocess_kwargs())
        if result.returncode != 0:
            raise RuntimeError(
                self.t("unrar_extract_failed", details=result.stdout[-2000:])
            )
        self.set_progress(35)

    def safe_extract_rar(self, archive_path, destination):
        seven_zip = self.find_7zip_executable()
        if seven_zip:
            self.log(self.t("using_7zip_rar", path=seven_zip))
            self.extract_with_7zip(seven_zip, archive_path, destination)
            return

        unrar = self.find_unrar_executable()
        if unrar:
            self.log(self.t("using_unrar", path=unrar))
            self.extract_with_unrar(unrar, archive_path, destination)
            return

        try:
            import rarfile  # type: ignore
        except ImportError:
            rarfile = None

        if rarfile is not None:
            try:
                with rarfile.RarFile(archive_path) as rf:
                    members = rf.infolist()
                    total = max(len(members), 1)
                    for member in members:
                        self.validate_member_path(destination, member.filename)
                    for index, member in enumerate(members, start=1):
                        rf.extract(member, destination)
                        self.set_progress(index / total * 35)
                return
            except Exception as exc:
                raise RuntimeError(self.t("rar_extract_failed", error=exc)) from exc

        raise RuntimeError(self.t("no_rar_backend"))

    def extract_archive(self, archive_path, destination):
        suffix = archive_path.suffix.lower()
        archive_type = suffix.upper().lstrip(".")
        self.set_status_key("status_extracting", archive_type=archive_type)
        self.log(self.t("extracting_log", name=archive_path.name))

        if suffix == ".zip":
            self.safe_extract_zip(archive_path, destination)
        elif suffix == ".7z":
            self.safe_extract_7z(archive_path, destination)
        elif suffix == ".rar":
            self.safe_extract_rar(archive_path, destination)
        else:
            raise RuntimeError(self.t("unsupported_format_runtime", suffix=suffix))

    @staticmethod
    def classify_image(image_path):
        """
        Classify image from filename.
        Supported common names include RGB/Color/Colour, IR/Infrared and Depth.
        """
        stem = image_path.stem.lower()
        tokens = [t for t in re.split(r"[^a-z0-9]+", stem) if t]
        token_set = set(tokens)

        if "depth" in token_set or stem.startswith("depth") or "depth" in stem:
            return "depth"

        if (
            "ir" in token_set
            or "infrared" in token_set
            or "infrared" in stem
            or "infra-red" in stem
        ):
            return "IR"

        if (
            "rgb" in token_set
            or "color" in token_set
            or "colour" in token_set
            or "rgb" in stem
            or "color" in stem
            or "colour" in stem
        ):
            return "RGB"

        return None

    @staticmethod
    def natural_sort_key(value):
        text = str(value).replace("\\", "/").lower()
        return [
            int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", text)
        ]

    def collect_complete_groups(self, extract_dir):
        image_files = sorted(
            [
                p for p in extract_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            ],
            key=lambda p: self.natural_sort_key(p.relative_to(extract_dir))
        )

        if not image_files:
            raise RuntimeError(self.t("no_images"))

        self.log(self.t("scanned_images", count=len(image_files)))

        groups = {}
        unclassified = []

        for image_file in image_files:
            category = self.classify_image(image_file)
            if category is None:
                unclassified.append(image_file)
                continue

            group_dir = image_file.parent
            groups.setdefault(group_dir, {name: [] for name in OUTPUT_CATEGORIES})
            groups[group_dir][category].append(image_file)

        if unclassified:
            self.log(self.t("unclassified_header", count=len(unclassified)))
            for path in unclassified[:20]:
                self.log(f"  - {path.relative_to(extract_dir)}")
            if len(unclassified) > 20:
                self.log(self.t("unclassified_more", count=len(unclassified) - 20))

        complete_groups = []
        skipped = 0

        group_dirs = sorted(
            groups.keys(),
            key=lambda p: self.natural_sort_key(p.relative_to(extract_dir))
        )

        for group_dir in group_dirs:
            category_map = groups[group_dir]
            counts = {name: len(category_map[name]) for name in OUTPUT_CATEGORIES}
            rel = group_dir.relative_to(extract_dir)

            if all(counts[name] == 1 for name in OUTPUT_CATEGORIES):
                complete_groups.append((group_dir, category_map))
                continue

            skipped += 1
            count_text = ", ".join(f"{name}={counts[name]}" for name in OUTPUT_CATEGORIES)
            self.log(self.t("skip_group", group=rel, counts=count_text))

        if not complete_groups:
            raise RuntimeError(self.t("no_complete_groups"))

        return complete_groups, skipped

    def process_archive(self, archive_path):
        try:
            self.work_dir = Path(tempfile.mkdtemp(prefix="image_extract_gui_"))
            extract_dir = self.work_dir / "unpacked"
            self.processed_dir = self.work_dir / "organized"

            extract_dir.mkdir(parents=True, exist_ok=True)
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            for category in OUTPUT_CATEGORIES:
                (self.processed_dir / category).mkdir(parents=True, exist_ok=True)

            self.extract_archive(archive_path, extract_dir)

            self.set_status_key("status_pairing")
            self.log(self.t("build_groups"))
            complete_groups, skipped = self.collect_complete_groups(extract_dir)

            self.group_count = len(complete_groups)
            self.skipped_group_count = skipped
            processed = 0

            self.log(self.t("complete_groups", count=self.group_count))
            if skipped:
                self.log(self.t("skipped_groups", count=skipped))

            for group_index, (group_dir, category_map) in enumerate(complete_groups, start=1):
                number = f"{group_index:0{NUMBER_WIDTH}d}"
                rel_group = group_dir.relative_to(extract_dir)

                for category in OUTPUT_CATEGORIES:
                    source = category_map[category][0]
                    destination = (
                        self.processed_dir
                        / category
                        / f"{number}{source.suffix.lower()}"
                    )
                    shutil.copy2(source, destination)
                    processed += 1

                self.log(
                    self.t(
                        "group_mapping",
                        current=group_index,
                        total=self.group_count,
                        group=rel_group,
                        number=number
                    )
                )
                self.set_progress(35 + group_index / self.group_count * 45)

            self.processed_count = processed

            self.set_progress(80)
            self.set_status_key(
                "status_ready_export",
                groups=self.group_count,
                images=processed
            )

            self.root.after(0, self.ask_save_location)

        except Exception as exc:
            self.root.after(0, lambda e=exc: self.processing_failed(e))

    @staticmethod
    def append_timestamp(output_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(output_path)
        stem = output_path.stem.strip() or "Image_Dataset"
        return output_path.with_name(f"{stem}_{timestamp}.zip")

    def ask_save_location(self):
        output_path = filedialog.asksaveasfilename(
            title=self.t("dialog_save_title"),
            defaultextension=".zip",
            initialfile="Image_Dataset.zip",
            filetypes=[
                (self.t("filetype_zip"), "*.zip"),
                (self.t("filetype_all"), "*.*")
            ]
        )

        if not output_path:
            self.log(self.t("cancelled_export"))
            self.set_status_key("status_cancelled")
            self.start_button.configure(state="normal")
            self.cleanup_temp()
            return

        output_path = Path(output_path)
        if output_path.suffix.lower() != ".zip":
            output_path = output_path.with_suffix(".zip")

        output_path = self.append_timestamp(output_path)

        self.log(self.t("final_export", path=output_path))
        self.set_status_key("status_creating_zip")

        thread = threading.Thread(
            target=self.create_output_zip,
            args=(output_path,),
            daemon=True
        )
        thread.start()

    def create_output_zip(self, output_path):
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            files = sorted(
                [p for p in self.processed_dir.rglob("*") if p.is_file()],
                key=lambda p: self.natural_sort_key(p.relative_to(self.processed_dir))
            )
            total = max(len(files), 1)

            with zipfile.ZipFile(
                output_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6
            ) as zf:
                for index, file_path in enumerate(files, start=1):
                    arcname = file_path.relative_to(self.processed_dir)
                    zf.write(file_path, arcname=str(arcname).replace("\\", "/"))
                    self.set_progress(80 + index / total * 20)

            self.set_progress(100)
            self.root.after(0, lambda: self.processing_complete(output_path))

        except Exception as exc:
            self.root.after(0, lambda e=exc: self.processing_failed(e))

    def processing_complete(self, output_path):
        self.log("=" * 68)
        self.log(self.t("log_done"))
        self.log(self.t("log_complete_groups", count=self.group_count))
        self.log(self.t("log_image_count", count=self.processed_count))
        if self.skipped_group_count:
            self.log(self.t("log_skipped", count=self.skipped_group_count))
        self.log(self.t("log_zip", path=output_path))

        self.set_status_key(
            "status_complete",
            groups=self.group_count,
            images=self.processed_count
        )
        self.start_button.configure(state="normal")

        extra = ""
        if self.skipped_group_count:
            extra = self.t("complete_extra", count=self.skipped_group_count)

        messagebox.showinfo(
            self.t("done"),
            self.t(
                "complete_message",
                groups=self.group_count,
                images=self.processed_count,
                extra=extra,
                path=output_path
            )
        )

        self.cleanup_temp()

    def processing_failed(self, exc):
        self.log(self.t("failed_log", error=exc))
        self.set_status_key("status_failed")
        self.progress_value.set(0)
        self.start_button.configure(state="normal")

        messagebox.showerror(self.t("failed_title"), str(exc))
        self.cleanup_temp()

    def cleanup_temp(self):
        if self.work_dir and self.work_dir.exists():
            try:
                shutil.rmtree(self.work_dir, ignore_errors=True)
            except Exception:
                pass

        self.work_dir = None
        self.processed_dir = None

    def on_close(self):
        self.cleanup_temp()
        self.root.destroy()


def main():
    root = tk.Tk()

    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass

    ImageArchiveGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
