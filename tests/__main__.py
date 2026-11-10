"""Run every Python test with one command: ``python -m tests``.

``unittest`` discovery only collects ``TestCase`` classes, so module-level
``test_*`` functions were silently skipped. This runner adds them, providing
a temporary ``tmp_path`` directory for functions that ask for one.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent


def _wrap(function: Callable[..., object]) -> Callable[[], object]:
    parameters = inspect.signature(function).parameters
    if not parameters:
        return function
    if list(parameters) != ["tmp_path"]:
        def unsupported() -> None:
            raise unittest.SkipTest(f"unsupported parameters: {list(parameters)}")
        return unsupported

    def with_tmp_path() -> object:
        with tempfile.TemporaryDirectory() as directory:
            return function(Path(directory))
    return with_tmp_path


def build_suite(pattern: str = "test*.py") -> unittest.TestSuite:
    suite = unittest.defaultTestLoader.discover(
        str(TESTS_DIR), pattern=pattern, top_level_dir=str(PROJECT_ROOT)
    )
    for path in sorted(TESTS_DIR.glob(pattern)):
        try:
            module = importlib.import_module(f"tests.{path.stem}")
        except Exception:  # discovery already reports the import failure
            continue
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("test_") and function.__module__ == module.__name__:
                suite.addTest(unittest.FunctionTestCase(
                    _wrap(function), description=f"{module.__name__}.{name}"
                ))
    return suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all MarketCouncil Python tests.")
    parser.add_argument("-p", "--pattern", default="test*.py", help="test file pattern")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(PROJECT_ROOT))
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(
        build_suite(args.pattern)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
