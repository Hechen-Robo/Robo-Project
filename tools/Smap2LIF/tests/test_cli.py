import io
import unittest
from contextlib import redirect_stdout

from smap2lif.cli import main


class CliTests(unittest.TestCase):
    def test_project_skeleton_runs(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Smap2LIF 0.1.0",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()