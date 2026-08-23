# Smap2LIF

Smap2LIF converts native 2D source-map JSON files into validated VDMA
LIF 1.0.0 layout files.

The project provides both a Windows desktop interface and a command-line
interface. Generated files are validated with the bundled official LIF 1.0.0
JSON Schema before they are written.

## Version 0.1 scope

Implemented:

- Native 2D source-map parsing and validation.
- Duplicate-ID and broken-reference detection.
- Topological point conversion to LIF nodes.
- Straight and cubic Bezier path conversion to LIF edges.
- Cubic Bezier conversion to degree-3 NURBS trajectories.
- Forward and reverse tangential vehicle orientation.
- Linear and rotational edge-speed limits.
- Node rotation restrictions derived from the source `spin` property.
- Action-point, charging-point and bin-location station export.
- Standard `pick`, `drop` and `startCharging` node actions.
- Official LIF 1.0.0 Schema validation.
- Additional semantic validation for IDs, references, timestamps, angles and
  trajectories.
- Critical review prompts for source safety information that LIF 1.0.0 cannot
  represent directly.
- Tkinter desktop GUI.
- Command-line conversion.
- PyInstaller configuration and Windows build script.

## Important distinction

LIF is a layout interchange format used with fleet-management systems. It is
not a VDA 5050 MQTT `order`, `state` or `visualization` message.

The generated layout can later be used by an FMS to calculate routes and build
VDA 5050 orders.

## Source-to-LIF mapping

| Source data | LIF output |
| --- | --- |
| Topological point | `node` |
| Straight path | `edge` without trajectory |
| Cubic Bezier path | `edge` with degree-3 NURBS trajectory |
| Direction `0` | Tangential orientation `0.0` radians |
| Direction `1` | Tangential orientation `Pi` radians |
| `maxspeed` | `maxSpeed` |
| `maxrot` | `maxRotationSpeed` |
| `spin=false` | Endpoint rotation permission `NONE` |
| `spin=true` | Endpoint rotation permission `BOTH` |
| Load task | Conditional `pick` action |
| Unload task | Conditional `drop` action |
| Charging point | Conditional `startCharging` action |
| Task end height | Action parameter `height` |

The vehicle type ID and map ID entered in the GUI must match the values used by
the target robot and its VDA 5050 Factsheet/configuration.

## Safety review

LIF 1.0.0 does not provide direct standard fields for every source-map object.
The converter marks the following as critical when detected:

- Forbidden lines.
- Polygon safety-speed areas.
- Shielded safety areas.
- Unknown station task types.
- Ambiguous physical station positions.

The GUI does not write the output until the user explicitly accepts critical
warnings. The command-line interface requires `--accept-critical`.

Accepting a warning does not convert or restore the omitted safety behavior.
Generated maps must be reviewed before real robot routing or VDA 5050 order
generation.

## Development setup on Windows

Open PowerShell in the project directory:

```powershell
cd B:\Robo-Project\tools\Smap2LIF
```

Create the project-specific virtual environment:

```powershell
python -m venv .venv
```

Install the project without activating the virtual environment:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -e .
```

Run all tests:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

Start the GUI:

```powershell
& ".\.venv\Scripts\python.exe" -m smap2lif --gui
```

Alternatively, double-click:

```text
run_gui.bat
```

The BAT file uses the virtual-environment interpreter directly, so PowerShell
script execution policy does not need to be changed.

## Command-line conversion

```powershell
& ".\.venv\Scripts\python.exe" -m smap2lif `
    --input "C:\Maps\source.json" `
    --output "C:\Maps\source_LIF_1.0.0.json" `
    --vehicle-type-id "AGV.TYPE-01" `
    --map-id "MAP-01"
```

If critical warnings have been reviewed and accepted:

```powershell
& ".\.venv\Scripts\python.exe" -m smap2lif `
    --input "C:\Maps\source.json" `
    --output "C:\Maps\source_LIF_1.0.0.json" `
    --vehicle-type-id "AGV.TYPE-01" `
    --map-id "MAP-01" `
    --accept-critical
```

## Build the Windows executable

Run from PowerShell or double-click the file:

```powershell
.\build.bat
```

The script performs the following operations:

1. Creates `.venv` if it does not exist.
2. Installs application and build dependencies.
3. Runs the complete unit-test suite.
4. Builds a clean one-file Windows GUI executable.
5. Runs an executable startup smoke test.
6. Creates a hidden Tk window from the packaged executable to verify that the
   GUI runtime and DLLs were bundled correctly.

Successful output:

```text
dist\Smap2LIF.exe
```

The executable includes the official LIF Schema and does not require Python on
the target computer.

## Tkinter packaging troubleshooting

If the build reports that Tkinter or Tcl/Tk is unavailable, verify the selected
project interpreter before packaging:

```powershell
& ".\.venv\Scripts\python.exe" -m tkinter
```

A small Tk demonstration window must open. If it does not, install a standard
64-bit Python release with Tcl/Tk support, delete and recreate this project's
`.venv`, and run `build.bat` again. The build script now stops automatically if
either the build-time Tk runtime or the packaged GUI runtime is incomplete.

The Windows build also supports a project `venv` created from a Conda-based
Python installation. In that case, the PyInstaller configuration automatically
adds the base installation's `Library\bin` directory while resolving Tcl/Tk
DLLs.

## Repository safety

Virtual environments, build products, source maps and converted customer maps
are ignored by Git. Only sanitized files under `tests/fixtures` may be
committed.
