#!/usr/bin/env python3
from __future__ import annotations

import os
import csv
from pathlib import Path
from typing import Optional, List, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

from ultralytics import YOLO  # pyright: ignore[reportPrivateImportUsage]

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rosidl_runtime_py.utilities import get_message
from rclpy.serialization import deserialize_message

# Optional ROS message types (strings)
IMG_MSG = "sensor_msgs/msg/Image"
CIMG_MSG = "sensor_msgs/msg/CompressedImage"

try:
    from cv_bridge import CvBridge  # type: ignore
    _HAS_CVBRIDGE = True
except Exception:  # pragma: no cover
    _HAS_CVBRIDGE = False
    CvBridge = None  # type: ignore

# Pillow resampling compatibility
try:  # Pillow>=9
    _RESAMPLE_BILINEAR = Image.Resampling.BILINEAR  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _RESAMPLE_BILINEAR = Image.BILINEAR  # type: ignore[attr-defined]


class OfflineYoloBagViewer(tk.Tk):
    """Offline rosbag2 image inference with YOLO + (optional) 2-stage color classification."""

    def __init__(self):
        super().__init__()
        self.title("Offline YOLO Validator (rosbag2 + Tk)")
        self.geometry("1100x700")

        # state
        self.bag_dir: Optional[Path] = None
        self.model_path: Optional[Path] = None
        self.reader: Optional[SequentialReader] = None
        self.topic_types: dict[str, str] = {}
        self.selected_topic = tk.StringVar(value="")
        self.model: Optional[YOLO] = None
        self.bridge = CvBridge() if _HAS_CVBRIDGE and CvBridge is not None else None

        self.playing = False
        self.frame_idx = 0
        self.skip_counter = 0

        # save options
        self.save_images_var = tk.BooleanVar(value=False)
        self.save_dir: Optional[Path] = None
        self.csv_file = None
        self.csv_writer = None

        # NEW: per-detection CSV (keeps the old pred.csv untouched)
        self.csv_det_file = None
        self.csv_det_writer = None

        # params
        self.conf_var = tk.DoubleVar(value=0.50)
        self.every_n_var = tk.IntVar(value=1)
        self.delay_ms_var = tk.IntVar(value=33)  # ~30fps display
        self.device_var = tk.StringVar(value="cpu")  # "cpu" or "0" (if GPU works)

        # NEW: 2-stage color classification switch
        self.color_enable_var = tk.BooleanVar(value=True)

        # NEW: simple color config (tune later if needed)
        self.color_sat_min_var = tk.IntVar(value=60)   # S threshold
        self.color_val_min_var = tk.IntVar(value=50)   # V threshold
        self.black_val_mean_var = tk.IntVar(value=60)  # mean V threshold for black

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        # bag
        ttk.Button(top, text="Select rosbag2 folder", command=self.pick_bag).grid(row=0, column=0, sticky="w")
        self.bag_label = ttk.Label(top, text="(none)")
        self.bag_label.grid(row=0, column=1, sticky="w", padx=8)

        # model
        ttk.Button(top, text="Select YOLO model (.pt)", command=self.pick_model).grid(row=1, column=0, sticky="w")
        self.model_label = ttk.Label(top, text="(none)")
        self.model_label.grid(row=1, column=1, sticky="w", padx=8)

        # topic dropdown
        ttk.Label(top, text="Image topic:").grid(row=2, column=0, sticky="w")
        self.topic_combo = ttk.Combobox(top, textvariable=self.selected_topic, width=60, state="readonly", values=[])
        self.topic_combo.grid(row=2, column=1, sticky="w", padx=8)

        # params row
        p = ttk.Frame(top)
        p.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(p, text="conf").grid(row=0, column=0, padx=(0, 6))
        ttk.Scale(p, from_=0.05, to=0.95, variable=self.conf_var, orient=tk.HORIZONTAL, length=200).grid(row=0, column=1)
        self.conf_label = ttk.Label(p, text="0.50")
        self.conf_label.grid(row=0, column=2, padx=6)

        ttk.Label(p, text="every_n").grid(row=0, column=3, padx=(18, 6))
        ttk.Spinbox(p, from_=1, to=100, textvariable=self.every_n_var, width=5).grid(row=0, column=4)

        ttk.Label(p, text="delay(ms)").grid(row=0, column=5, padx=(18, 6))
        ttk.Spinbox(p, from_=1, to=200, textvariable=self.delay_ms_var, width=6).grid(row=0, column=6)

        ttk.Label(p, text="device").grid(row=0, column=7, padx=(18, 6))
        ttk.Entry(p, textvariable=self.device_var, width=8).grid(row=0, column=8)

        # NEW: color switch + thresholds (keeps everything else)
        p2 = ttk.Frame(top)
        p2.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Checkbutton(p2, text="2-stage color classification (ROI HSV)", variable=self.color_enable_var).grid(
            row=0, column=0, sticky="w"
        )

        ttk.Label(p2, text="S_min").grid(row=0, column=1, padx=(18, 6))
        ttk.Spinbox(p2, from_=0, to=255, textvariable=self.color_sat_min_var, width=5).grid(row=0, column=2)

        ttk.Label(p2, text="V_min").grid(row=0, column=3, padx=(18, 6))
        ttk.Spinbox(p2, from_=0, to=255, textvariable=self.color_val_min_var, width=5).grid(row=0, column=4)

        ttk.Label(p2, text="black_Vmean").grid(row=0, column=5, padx=(18, 6))
        ttk.Spinbox(p2, from_=0, to=255, textvariable=self.black_val_mean_var, width=6).grid(row=0, column=6)

        # save
        s = ttk.Frame(top)
        s.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(s, text="Save annotated images + CSV", variable=self.save_images_var).grid(row=0, column=0, sticky="w")
        ttk.Button(s, text="Select output folder", command=self.pick_save_dir).grid(row=0, column=1, padx=10, sticky="w")
        self.save_label = ttk.Label(s, text="(none)")
        self.save_label.grid(row=0, column=2, sticky="w")

        # controls
        c = ttk.Frame(self)
        c.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        ttk.Button(c, text="Load", command=self.load_resources).pack(side=tk.LEFT)
        ttk.Button(c, text="Play", command=self.play).pack(side=tk.LEFT, padx=6)
        ttk.Button(c, text="Pause", command=self.pause).pack(side=tk.LEFT, padx=6)
        ttk.Button(c, text="Step", command=self.step_once).pack(side=tk.LEFT, padx=6)
        ttk.Button(c, text="Stop/Reset", command=self.stop_reset).pack(side=tk.LEFT, padx=6)

        self.status = ttk.Label(c, text="Ready.")
        self.status.pack(side=tk.LEFT, padx=20)

        # image canvas
        mid = ttk.Frame(self)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.image_label = tk.Label(mid)
        self.image_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        info = ttk.Frame(mid)
        info.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        self.info_text = tk.Text(info, width=38, height=30)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # update labels
        def _tick():
            self.conf_label.configure(text=f"{self.conf_var.get():.2f}")
            self.after(200, _tick)
        _tick()

    def pick_bag(self):
        default_dir = os.path.expanduser("~")
        d = filedialog.askdirectory(title="Select rosbag2 folder (contains metadata.yaml)", initialdir=default_dir)
        if not d:
            return
        p = Path(d).expanduser().resolve()
        if not (p / "metadata.yaml").exists():
            messagebox.showerror("Invalid bag", "Selected folder does not contain metadata.yaml")
            return
        self.bag_dir = p
        self.bag_label.configure(text=str(p))

    def pick_model(self):
        default_dir_pt = os.path.expanduser("~/workspace/Project/runs")
        f = filedialog.askopenfilename(
            title="Select YOLO model (.pt)",
            filetypes=[("PyTorch weights", "*.pt"), ("All files", "*.*")],
            initialdir=default_dir_pt
        )
        if not f:
            return
        p = Path(f).expanduser().resolve()
        if not p.exists():
            messagebox.showerror("Missing model", f"File not found:\n{p}")
            return
        self.model_path = p
        self.model_label.configure(text=str(p))

    def pick_save_dir(self):
        d = filedialog.askdirectory(title="Select output folder")
        if not d:
            return
        p = Path(d).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        self.save_dir = p
        self.save_label.configure(text=str(p))

    def load_resources(self):
        if not self.bag_dir:
            messagebox.showerror("Missing", "Please select rosbag2 folder first.")
            return
        if not self.model_path:
            messagebox.showerror("Missing", "Please select model (.pt) first.")
            return

        # open bag
        try:
            reader = SequentialReader()
            reader.open(
                StorageOptions(uri=str(self.bag_dir), storage_id="sqlite3"),
                ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
            )
            self.reader = reader
        except Exception as e:
            messagebox.showerror("Bag open failed", str(e))
            return

        # list topics
        assert self.reader is not None
        self.topic_types = {t.name: t.type for t in self.reader.get_all_topics_and_types()}
        img_topics = [name for name, t in self.topic_types.items() if t in (IMG_MSG, CIMG_MSG)]

        if not img_topics:
            messagebox.showerror("No image topics", f"No {IMG_MSG} or {CIMG_MSG} topics found in bag.")
            return

        img_topics.sort()
        self.topic_combo.configure(values=img_topics)
        if not self.selected_topic.get() or self.selected_topic.get() not in img_topics:
            self.selected_topic.set(img_topics[0])

        # load model
        try:
            self.model = YOLO(str(self.model_path))
        except Exception as e:
            messagebox.showerror("Model load failed", str(e))
            return

        # reset counters
        self.playing = False
        self.frame_idx = 0
        self.skip_counter = 0
        self._close_csv()

        self._log_info(f"Loaded bag: {self.bag_dir}")
        self._log_info(f"Loaded model: {self.model_path}")
        self._log_info(f"Selected topic: {self.selected_topic.get()}")
        self._log_info(
            f"Device: {self.device_var.get()}, conf={self.conf_var.get():.2f}, every_n={self.every_n_var.get()}, "
            f"color={'ON' if self.color_enable_var.get() else 'OFF'}"
        )
        self.status.configure(text="Loaded. Ready to play.")

    def play(self):
        if not self._ready():
            return
        if self.playing:
            return
        self.playing = True
        self.status.configure(text="Playing...")
        self._schedule_next()

    def pause(self):
        self.playing = False
        self.status.configure(text="Paused.")

    def step_once(self):
        if not self._ready():
            return
        self.playing = False
        self._process_one()

    def stop_reset(self):
        self.playing = False
        self.status.configure(text="Stopped/Reset.")
        self.frame_idx = 0
        self.skip_counter = 0
        self._close_csv()
        # Re-open reader to restart from beginning
        if self.bag_dir:
            try:
                reader = SequentialReader()
                reader.open(
                    StorageOptions(uri=str(self.bag_dir), storage_id="sqlite3"),
                    ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
                )
                self.reader = reader
            except Exception as e:
                messagebox.showerror("Reset failed", str(e))
                return

    def _schedule_next(self):
        if not self.playing:
            return
        self._process_one()
        self.after(max(1, int(self.delay_ms_var.get())), self._schedule_next)

    def _ready(self) -> bool:
        if self.reader is None or self.model is None:
            messagebox.showerror("Not ready", "Please click Load after selecting bag and model.")
            return False
        return True

    # -------------------------
    # 2-stage color classifier
    # -------------------------
    def _classify_pallet_color(self, roi_bgr: np.ndarray) -> str:
        if roi_bgr is None or roi_bgr.size == 0:
            return "unknown"

        # 1) Crop central area and blur
        h, w = roi_bgr.shape[:2]
        y0, y1 = int(0.08*h), int(0.92*h)
        x0, x1 = int(0.08*w), int(0.92*w)
        roi = roi_bgr[y0:y1, x0:x1]
        roi = cv2.GaussianBlur(roi, (5, 5), 0)

        # 2) LAB-based foreground segmentation
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.int16)

        ch, cw = lab.shape[:2]
        cy0, cy1 = int(0.30*ch), int(0.70*ch)
        cx0, cx1 = int(0.30*cw), int(0.70*cw)
        center = lab[cy0:cy1, cx0:cx1].reshape(-1, 3)

        ref = np.median(center, axis=0)  # reference color
        dist = np.linalg.norm(lab - ref, axis=2)

        # dist threshold
        fg = (dist < 24).astype(np.uint8) * 255

        # morphology
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k, iterations=2)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN,  k, iterations=1)
        fg_mask = fg > 0

        # quick checks
        fg_ratio = float(fg_mask.mean())
        if fg_ratio < 0.10:
            return "wood"

        # Convert to HSV
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        v_mean = float(np.mean(V[fg_mask]))
        if v_mean < 50:
            return "black"

        # Color classification
        paint = fg_mask & (S > 60) & (V > 60)
        paint_ratio = float(paint.sum()) / float(fg_mask.sum())

        # wood check
        if paint_ratio < 0.08:
            return "wood"

        h_vals = H[paint]
        red_ratio  = float(((h_vals <= 10) | (h_vals >= 170)).mean())
        blue_ratio = float(((h_vals >= 85) & (h_vals <= 140)).mean())

        # final decision
        if red_ratio > 0.55:
            return "red"
        if blue_ratio > 0.55:
            return "blue"

        return "wood"

    def _overlay_color_labels(self, base_vis: np.ndarray, raw_bgr: np.ndarray, r0) -> Tuple[np.ndarray, List[str]]:
        """Overlay EPAL-color labels on top of Ultralytics plot image."""
        colors: List[str] = []
        if not self.color_enable_var.get():
            return base_vis, colors

        if r0.boxes is None:
            return base_vis, colors

        # Iterate detections
        for i in range(len(r0.boxes)):
            xyxy = r0.boxes.xyxy[i].cpu().numpy().tolist()
            x1, y1, x2, y2 = [int(round(v)) for v in xyxy]

            # clamp
            h, w = raw_bgr.shape[:2]
            x1 = max(0, min(x1, w - 1))
            x2 = max(0, min(x2, w))
            y1 = max(0, min(y1, h - 1))
            y2 = max(0, min(y2, h))

            if x2 <= x1 or y2 <= y1:
                colors.append("unknown")
                continue

            # small padding to capture enough pixels
            pad = 4
            px1 = max(0, x1 - pad)
            py1 = max(0, y1 - pad)
            px2 = min(w, x2 + pad)
            py2 = min(h, y2 + pad)

            roi = raw_bgr[py1:py2, px1:px2]
            c = self._classify_pallet_color(roi)
            colors.append(c)

            # confidence (optional)
            conf = None
            try:
                conf = float(r0.boxes.conf[i].cpu().numpy().item())
            except Exception:
                conf = None

            label = f"{c}"

            # the class/conf label drawn by Ultralytics (usually above the bbox).
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.55
            thickness = 1
            (tw, th), bl = cv2.getTextSize(label, font, scale, thickness)

            # default: inside bbox near top-left
            tx = x1
            ty = y1 + th + 8  # text baseline

            # if too close to bottom, move above bbox with extra offset
            if ty + bl > h - 2:
                ty = y1 - 18
            # clamp within top boundary
            if ty - th - bl < 0:
                ty = th + bl + 2

            # clamp within width
            if tx + tw > w - 2:
                tx = max(0, w - tw - 2)

            # background box for readability
            xA, yA = tx, ty - th - bl
            xB, yB = tx + tw, ty + bl
            cv2.rectangle(base_vis, (xA, yA), (xB, yB), (0, 0, 0), -1)
            cv2.putText(base_vis, label, (tx, ty), font, scale, (0, 255, 0), thickness, cv2.LINE_AA)

        return base_vis, colors

    def _process_one(self):
        topic = self.selected_topic.get()
        if topic not in self.topic_types:
            self._log_info("Topic not in bag.")
            self.playing = False
            return

        msg_type_str = self.topic_types[topic]
        msg_type = get_message(msg_type_str)

        every_n = max(1, int(self.every_n_var.get()))
        assert self.reader is not None
        assert self.model is not None

        # read until we find next msg for topic, and pass every_n filter
        while True:
            if not self.reader.has_next():
                self.status.configure(text="End of bag.")
                self.playing = False
                self._close_csv()
                return

            t_name, data, t_ns = self.reader.read_next()
            if t_name != topic:
                continue

            self.skip_counter += 1
            if every_n > 1 and (self.skip_counter % every_n) != 0:
                continue

            # deserialize
            msg = deserialize_message(data, msg_type)

            # decode to cv image (BGR)
            try:
                cv_img = self._to_cv_image(msg, msg_type_str)
            except Exception as e:
                self._log_info(f"[WARN] decode failed: {e}")
                continue

            # run yolo
            conf = float(self.conf_var.get())
            device = str(self.device_var.get()).strip() or "cpu"

            results = self.model.predict(cv_img, conf=conf, device=device, verbose=False)
            r0 = results[0]
            det_n = 0 if (r0.boxes is None) else len(r0.boxes)

            # Keep original functionality: use ultralytics plot
            vis = r0.plot()  # BGR

            # NEW: overlay color labels (2-stage)
            vis, color_list = self._overlay_color_labels(vis, cv_img, r0)

            self._show_image(vis)

            self.frame_idx += 1

            # status: show dominant color (if any)
            dom = ""
            if color_list:
                # pick most common non-unknown
                filtered = [c for c in color_list if c != "unknown"]
                if filtered:
                    dom = max(set(filtered), key=filtered.count)
                    dom = f" | color~{dom}"

            self.status.configure(text=f"Frame {self.frame_idx} | det={det_n}{dom} | t_ns={int(t_ns)}")

            # optional save
            if self.save_images_var.get():
                self._ensure_save_ready()
                self._save_frame(vis, int(t_ns), det_n)

                # NEW: save per-detection details (boxes + color)
                if self.csv_det_writer is not None and r0.boxes is not None:
                    for i in range(len(r0.boxes)):
                        x1, y1, x2, y2 = r0.boxes.xyxy[i].cpu().numpy().tolist()
                        conf_i = float(r0.boxes.conf[i].cpu().numpy().item()) if hasattr(r0.boxes, "conf") else 0.0
                        c = color_list[i] if i < len(color_list) else "unknown"
                        self.csv_det_writer.writerow([
                            self.frame_idx, int(t_ns), i,
                            int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)),
                            f"{conf_i:.6f}", c
                        ])

            # update info panel
            extra = f" colors={color_list}" if color_list else ""
            self._log_info(f"frame={self.frame_idx}  det={det_n}  t_ns={int(t_ns)}{extra}")
            return

    def _to_cv_image(self, msg, msg_type_str: str) -> np.ndarray:
        if msg_type_str == IMG_MSG:
            if not _HAS_CVBRIDGE or self.bridge is None:
                raise RuntimeError("cv_bridge not available. Install ROS cv_bridge and source ROS env.")
            # Use bgr8 consistently
            return self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

        if msg_type_str == CIMG_MSG:
            # msg.data is bytes; msg.format like "jpeg"
            buf = np.frombuffer(bytearray(msg.data), dtype=np.uint8)
            np_arr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if np_arr is None:
                raise RuntimeError("Failed to decode compressed image")
            return np_arr

        raise RuntimeError(f"Unsupported message type: {msg_type_str}")

    def _show_image(self, bgr_img: np.ndarray):
        rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)

        # fit to UI area (keep aspect)
        w, h = pil.size
        max_w = 720
        max_h = 540
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            pil = pil.resize((int(w * scale), int(h * scale)), _RESAMPLE_BILINEAR)

        imgtk = ImageTk.PhotoImage(image=pil)
        # keep reference to prevent garbage collection
        object.__setattr__(self.image_label, "imgtk", imgtk)
        self.image_label.configure(image=imgtk)

    def _ensure_save_ready(self):
        if self.save_dir is None:
            # default: sibling folder next to bag
            if self.bag_dir is not None:
                self.save_dir = (self.bag_dir.parent / "yolo_verify_out").resolve()
                self.save_dir.mkdir(parents=True, exist_ok=True)
                self.save_label.configure(text=str(self.save_dir))
            else:
                return  # Cannot proceed if save_dir and bag_dir are both None

        if self.csv_writer is None:
            out_csv = self.save_dir / "pred.csv"
            self.csv_file = open(out_csv, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["frame", "timestamp_ns", "num_det", "image_file"])
            (self.save_dir / "pred_images").mkdir(parents=True, exist_ok=True)

        # NEW: per-detection csv (boxes + color)
        if self.csv_det_writer is None:
            out_csv_det = self.save_dir / "pred_detections.csv"
            self.csv_det_file = open(out_csv_det, "w", newline="", encoding="utf-8")
            self.csv_det_writer = csv.writer(self.csv_det_file)
            self.csv_det_writer.writerow(["frame", "timestamp_ns", "det_idx", "x1", "y1", "x2", "y2", "conf", "color"])

    def _save_frame(self, bgr_vis: np.ndarray, t_ns: int, det_n: int):
        if self.save_dir is None:
            return
        out_img = self.save_dir / "pred_images" / f"{self.frame_idx:06d}.png"
        cv2.imwrite(str(out_img), bgr_vis)
        if self.csv_writer is not None:
            self.csv_writer.writerow([self.frame_idx, t_ns, det_n, str(out_img)])

    def _close_csv(self):
        if self.csv_file:
            try:
                self.csv_file.close()
            except Exception:
                pass
        self.csv_file = None
        self.csv_writer = None

        if self.csv_det_file:
            try:
                self.csv_det_file.close()
            except Exception:
                pass
        self.csv_det_file = None
        self.csv_det_writer = None

    def _log_info(self, s: str):
        self.info_text.insert("end", s + "\n")
        self.info_text.see("end")


def main():
    app = OfflineYoloBagViewer()
    app.mainloop()


if __name__ == "__main__":
    main()