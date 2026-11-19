"""Shared helpers: run either implementation end to end and compare output."""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run_python(stdin: bytes) -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / "payroll.py")],
        input=stdin, capture_output=True, check=True,
    )
    return result.stdout.decode("ascii")


def run_cobol(binary: Path, stdin: bytes) -> str:
    result = subprocess.run([str(binary)], input=stdin, capture_output=True, check=True)
    return result.stdout.decode("ascii")


def assert_same_output(expected: str, actual: str, expected_name: str, actual_name: str) -> None:
    """Fail with a line-by-line diff if the two reports differ in any character."""
    if expected == actual:
        return
    diff = difflib.unified_diff(
        expected.splitlines(keepends=True),
        actual.splitlines(keepends=True),
        fromfile=expected_name,
        tofile=actual_name,
    )
    pytest.fail("Outputs differ:\n" + "".join(diff), pytrace=False)


@pytest.fixture(scope="session")
def cobol_binary(tmp_path_factory) -> Path:
    """Compile payroll.cob fresh for this test session (skip if cobc is missing)."""
    cobc = shutil.which("cobc")
    if cobc is None:
        if os.environ.get("REQUIRE_COBOL") == "1":
            pytest.fail("cobc (GnuCOBOL) not installed but REQUIRE_COBOL=1", pytrace=False)
        pytest.skip("cobc (GnuCOBOL) not installed")
    binary = tmp_path_factory.mktemp("cobol") / "payroll"
    subprocess.run([cobc, "-x", "-o", str(binary), str(ROOT / "payroll.cob")], check=True)
    return binary
