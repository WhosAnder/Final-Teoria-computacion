#!/usr/bin/env python3
"""Thin wrapper: python scripts/compile.py --help"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from driver.cli import compile_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(compile_main())
