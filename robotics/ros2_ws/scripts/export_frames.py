#!/usr/bin/env python3
import csv
from pathlib import Path

import cv2
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions

def export_frames(bag_dir: str, image_topic: str, out_dir: str, every_n: int = 1, limit: int = 0):
    out_dir = Path(out_dir)
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=bag_dir, storage_id="sqlite3"),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if image_topic not in topic_types:
        raise RuntimeError(f"Topic not found: {image_topic}\nAvailable: {list(topic_types.keys())}")

    msg_type = get_message(topic_types[image_topic])
    bridge = CvBridge()

    csv_path = out_dir / "frames.csv"
    fcsv = open(csv_path, "w", newline="", encoding="utf-8")
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
        cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")  # 你的原始就是 bgr8
        fn = img_dir / f"{saved:06d}.png"
        cv2.imwrite(str(fn), cv_img)

        writer.writerow([saved, int(t_ns), str(fn)])
        saved += 1
        if limit > 0 and saved >= limit:
            break

    fcsv.close()
    print(f"[OK] Exported {saved} frames -> {img_dir}")
    print(f"[OK] Mapping CSV -> {csv_path}")

if __name__ == "__main__":
    export_frames(
        bag_dir="/home/hechen/datasets_rosbag2/recordtest1_2026-01-02_12-05-07/bag/",
        image_topic="/camera/image_raw",
        out_dir="/home/hechen/datasets_rosbag2/recordtest1_2026-01-02_12-05-07/frames_exported/",
        every_n=5,   # 比如 5 表示每 5 帧取一帧（减少标注量）
        limit=0      # 0 表示不限制
    )
