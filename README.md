# Project

Personal practice repository for **Robotics, Embedded Systems, Deep Learning, Computer Vision**.

This repository is used to:

* Practice robotics algorithms and ROS 2 development
* Develop embedded drivers and bring-up workflows
* Practice Deep Learning and CV algorithms development
* Maintain portable tools for Linux system rescue and troubleshooting
* Develop minor engineering tools for daily work

The focus is on **engineering practice**, **reproducibility**, and **long-term maintainability**.

---

## Repository Structure

```text
Project/
├── docs/              # Notes, setup guides, and troubleshooting
├── tools/             # Reusable scripts and engineering tools
├── robotics/          # Robotics and ROS 2 related practice
├── embedded/          # Embedded systems, drivers, and bring-up
├── test_automation/   # Test automation frameworks and examples
├── rescue/            # System rescue tools and documentation
└── sandbox/           # Temporary experiments and prototypes
```

---

## Useful Tools Developed For This Repository

### Image Archive Tool

A Windows desktop utility for organizing **IR / RGB / depth image datasets**.

It is designed for datasets where each sample contains one IR image, one RGB image, and one depth image.

#### Features

* Supports **ZIP / 7Z / RAR** archive input
* Automatically detects **IR, RGB/Color, and depth** images
* Groups corresponding images from the same source folder
* Assigns the same unified ID to each IR / RGB / depth image group
* Organizes output into separate directories:

```text
IR/
├── 00000001.png
├── 00000002.png
└── ...

RGB/
├── 00000001.jpg
├── 00000002.jpg
└── ...

depth/
├── 00000001.png
├── 00000002.png
└── ...
```

* Automatically skips incomplete or duplicated image groups
* Generates processing logs
* Automatically adds a timestamp to exported ZIP archives
* Supports **English and Chinese**
* Provides a standalone Windows executable

#### Download

[![Download Image Archive Tool](https://img.shields.io/badge/Download-ImageArchiveTool.exe-blue?style=for-the-badge\&logo=windows)](https://github.com/Hechen-Robo/Project/releases/latest/download/ImageArchiveTool.exe)

**Windows 10 / Windows 11 · Standalone executable · No Python installation required**

[View the latest release](https://github.com/Hechen-Robo/Project/releases/latest)

#### Source Code

[`tools/ImageArchiveTool/`](./tools/ImageArchiveTool/)

---

## Build Image Archive Tool from Source

Clone the repository:

```bash
git clone https://github.com/Hechen-Robo/Project.git
cd Project/tools/ImageArchiveTool
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the application from source:

```bash
python image_archive_gui_IR_RGB_depth_international.py
```

To build the Windows executable, run:

```text
build.bat
```

The generated executable will be located in:

```text
dist/ImageArchiveTool.exe
```

---

## Releases

Compiled applications are distributed through **GitHub Releases** rather than being committed directly to the source repository.

Release versions follow semantic versioning where applicable:

```text
v1.0.0
v1.1.0
v1.2.0
...
```

The download link above always points to the latest released version of `ImageArchiveTool.exe`.

---

## Development

This repository contains personal engineering projects, experiments, utilities, and technical notes.

Some components may be experimental and are primarily intended for learning, testing, and internal engineering workflows.
