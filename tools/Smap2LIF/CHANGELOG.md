# Changelog

## Unreleased

## 0.1.1 - 2026-10-01

### Fixed

- Preserve the source `ignoreDir` meaning by omitting the LIF node `theta`,
  so downstream VDA 5050 orders do not impose a mandatory node orientation.
- Normalize constrained node angles to the VDA 5050 `[-Pi, Pi]` range.
- Explicitly bundle the Windows Tcl/Tk runtime used by the GUI.
- Discover Tcl/Tk DLLs in both standard CPython and Conda installations.
- Verify Tk both before packaging and from the finished executable.
- Fail the build instead of publishing an executable with a broken GUI.

All notable changes to Smap2LIF are documented here.

## 0.1.0 - 2026-08-24

### Added

- Native 2D source-map parser.
- LIF 1.0.0 node, edge, station and trajectory conversion.
- Linear and rotational speed conversion.
- Node rotation permission conversion.
- Standard charging, pick and drop station actions.
- Bundled official LIF Schema validation.
- Semantic graph and trajectory validation.
- GUI and command-line interfaces.
- Critical safety-review workflow.
- Windows PyInstaller build configuration.
- Automated unit and real-map regression testing.
