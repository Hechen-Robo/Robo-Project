from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from smap2lif.cli import main


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "minimal_source_map.json"
)


class CliTests(unittest.TestCase):
    def test_no_arguments_launches_gui(self) -> None:
        with patch("smap2lif.gui.main", return_value=0) as gui_main:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        gui_main.assert_called_once_with()

    def test_tk_smoke_test_uses_runtime_check(self) -> None:
        with patch(
            "smap2lif.cli._run_tk_smoke_test",
            return_value=0,
        ) as runtime_check:
            exit_code = main(["--tk-smoke-test"])

        self.assertEqual(exit_code, 0)
        runtime_check.assert_called_once_with()

    def test_command_line_conversion_writes_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "converted.json"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--input",
                        str(FIXTURE_PATH),
                        "--output",
                        str(output_path),
                        "--vehicle-type-id",
                        "AGV.TYPE-01",
                        "--map-id",
                        "MAP-01",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.is_file())
            self.assertIn(
                "Official LIF schema validation: PASSED",
                output.getvalue(),
            )

    def test_critical_warning_requires_explicit_acceptance(self) -> None:
        source_text = FIXTURE_PATH.read_text(encoding="utf-8")
        source_text = source_text.replace(
            '"className": "FeatureArea"',
            '"className": "SafeSpeedLimitArea"',
        )

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "source.json"
            output_path = Path(directory) / "converted.json"
            input_path.write_text(source_text, encoding="utf-8")
            error = io.StringIO()
            output = io.StringIO()

            with redirect_stdout(output), redirect_stderr(error):
                exit_code = main(
                    [
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--vehicle-type-id",
                        "AGV.TYPE-01",
                        "--map-id",
                        "MAP-01",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertFalse(output_path.exists())
            self.assertIn("CRITICAL", error.getvalue())


if __name__ == "__main__":
    unittest.main()
