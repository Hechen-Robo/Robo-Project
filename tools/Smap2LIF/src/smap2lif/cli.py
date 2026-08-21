from __future__ import annotations

from collections.abc import Sequence

from . import __version__


def main(
    argv: Sequence[str] | None = None,
) -> int:
    del argv

    print(
        f"Smap2LIF {__version__}: "
        "project skeleton is ready."
    )

    return 0