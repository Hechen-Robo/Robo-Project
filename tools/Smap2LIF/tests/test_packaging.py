from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_windows_batch_files_are_ascii(self) -> None:
        for filename in ("build.bat", "run_gui.bat"):
            payload = (PROJECT_ROOT / filename).read_bytes()
            payload.decode("ascii")

    def test_pyinstaller_spec_builds_windowed_one_file_app(self) -> None:
        content = (PROJECT_ROOT / "Smap2LIF.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn('includes=["schemas/*"]', content)
        self.assertIn('name="Smap2LIF"', content)
        self.assertIn("console=False", content)
        self.assertIn('version="version_info.txt"', content)
        self.assertIn("tcltk_info.tcl_shared_library", content)
        self.assertIn("tcltk_info.tk_shared_library", content)
        self.assertIn('"_tcl_data"', content)
        self.assertIn('"_tk_data"', content)
        self.assertIn('"Library" / "bin"', content)

    def test_build_script_checks_packaged_tk_runtime(self) -> None:
        content = (PROJECT_ROOT / "build.bat").read_text(
            encoding="ascii"
        )

        self.assertIn("Checking build-time Tk runtime", content)
        self.assertIn("--tk-smoke-test", content)
        self.assertIn("print('Base Python:', sys.base_prefix)", content)
        self.assertNotIn("for /f", content.lower())

    def test_launcher_uses_package_entry_point(self) -> None:
        content = (PROJECT_ROOT / "smap2lif_launcher.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from smap2lif.cli import main", content)
        self.assertIn("raise SystemExit(main())", content)

    def test_official_schema_and_license_are_packaged(self) -> None:
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn('"schemas/*.schema"', pyproject)
        self.assertIn('"schemas/*.LIF"', pyproject)
        self.assertTrue(
            (PROJECT_ROOT / "src/smap2lif/schemas/LIF.schema").is_file()
        )
        self.assertTrue(
            (PROJECT_ROOT / "src/smap2lif/schemas/LICENSE.LIF").is_file()
        )


if __name__ == "__main__":
    unittest.main()
