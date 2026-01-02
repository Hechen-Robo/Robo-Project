#!/usr/bin/env python3
#! cant use in remote ssh and no DISPLAY
import csv
from pathlib import Path

import cv2
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions


def export_frames(
    bag_dir: str,
    image_topic: str,
    out_dir: str | Path,
    every_n: int = 1,
    limit: int = 0,
):
    out_dir = Path(out_dir).expanduser().resolve()
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(Path(bag_dir).expanduser().resolve()), storage_id="sqlite3"),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if image_topic not in topic_types:
        raise RuntimeError(
            f"Topic not found: {image_topic}\nAvailable: {list(topic_types.keys())}"
        )

    msg_type = get_message(topic_types[image_topic])
    bridge = CvBridge()

    csv_path = out_dir / "frames.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["frame", "timestamp_ns", "file"])

        idx = 0
        saved = 0
        while reader.has_next():
            topic, data, t_ns = reader.read_next()
            if topic != image_topic:
                continue

            idx += 1
            if every_n > 1 and (idx % every_n) != 0:
                continue

            msg = deserialize_message(data, msg_type)
            cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")  # 你当前是 bgr8
            fn = img_dir / f"{saved:06d}.png"
            cv2.imwrite(str(fn), cv_img)

            writer.writerow([saved, int(t_ns), str(fn)])
            saved += 1

            if limit > 0 and saved >= limit:
                break

    print(f"[OK] Exported {saved} frames -> {img_dir}")
    print(f"[OK] Mapping CSV -> {csv_path}")


def pick_dir_gui(
    title: str,
    must_contain: str | None = None,
    initialdir: str | Path | None = None,
) -> Path:
    """
    Folder picker with initial directory.
    - If must_contain is set, selected folder must contain that file (e.g., metadata.yaml).
    - If GUI not available (SSH/no DISPLAY), fallback to CLI input.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        init = str(Path(initialdir).expanduser().resolve()) if initialdir else None

        while True:
            d = filedialog.askdirectory(title=title, initialdir=init)
            if not d:
                raise SystemExit("Cancelled.")
            p = Path(d).expanduser().resolve()

            if must_contain and not (p / must_contain).exists():
                messagebox.showerror(
                    "Invalid folder",
                    f"Selected folder does not contain '{must_contain}'.\n\nPlease select a rosbag2 folder.",
                )
                init = str(p.parent)
                continue

            return p

    except Exception:
        # CLI fallback
        while True:
            d = input(f"{title}\nEnter directory path: ").strip()
            if not d:
                raise SystemExit("Cancelled.")
            p = Path(d).expanduser().resolve()

            if must_contain and not (p / must_contain).exists():
                print(f"[ERR] '{must_contain}' not found in {p}. Try again.")
                continue

            return p


def main():
    # 默认打开目录：~/dataset_rosbag
    bag_dir = pick_dir_gui(
        "Select rosbag2 folder (contains metadata.yaml)",
        must_contain="metadata.yaml",
        initialdir="~",
    )

    # 输出目录默认：选中 bag 目录的上一级目录
    default_out_dir = bag_dir.parent

    # 允许用户选择输出目录；默认打开到上一级目录；取消则用默认
    try:
        out_dir = pick_dir_gui(
            "Select output folder (images/ will be created inside)",
            initialdir=default_out_dir,
        )
    except SystemExit:
        out_dir = default_out_dir

    # 你可以按需改成参数/下拉选择
    image_topic = "/camera/image_raw"

    export_frames(
        bag_dir=str(bag_dir),
        image_topic=image_topic,
        out_dir=str(out_dir),
        every_n=5,   # 每 5 帧取 1 帧，减少标注量
        limit=0,     # 0 表示不限制
    )
    print("[ALL DONE]")

if __name__ == "__main__":
    main()