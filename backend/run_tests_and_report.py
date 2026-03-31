#!/usr/bin/env python3
"""
Run pytest API suite and write a timestamped Markdown report under backend/reports/.

Usage (from backend directory):
    python run_tests_and_report.py
    python run_tests_and_report.py -q
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    backend_root = Path(__file__).resolve().parent
    os.chdir(backend_root)
    os.environ["HUNTER_WRITE_TEST_REPORT"] = "1"

    import pytest

    args = ["tests", "-v", "--tb=short", *sys.argv[1:]]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
