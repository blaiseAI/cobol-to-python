"""Parity tests: payroll.py must reproduce payroll.cob character for character."""

from __future__ import annotations

import subprocess
import sys

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import ROOT, assert_same_output, run_cobol, run_python

# --- 1. Golden test: no COBOL compiler needed -------------------------------


def test_golden_output():
    stdin = (ROOT / "input.txt").read_bytes()
    expected = (ROOT / "cobol_output.txt").read_text(encoding="ascii")
    assert_same_output(expected, run_python(stdin), "cobol_output.txt", "payroll.py")


# --- 2. Live test: both programs on the same inputs -------------------------

EDGE_INPUTS = {
    "sample": (ROOT / "input.txt").read_bytes(),
    "empty": b"",
    "no_trailing_newline": b"00008No Newline          0400001000",
    # Gross > 999,999.99 truncates on the detail line; totals columns touch.
    "max_values": b"99999Max Out             9999999999\n",
    "exactly_1000_gross": b"00001Bracket Edge        0400002500\n",
    # 1.01 h x 990.11 = 1000.0111 -> gross 1000.01, one cent into the high bracket.
    "one_cent_over_bracket": b"00002Cent Over           0010199011\n",
}


def test_live_parity(cobol_binary):
    for name, stdin in EDGE_INPUTS.items():
        assert_same_output(
            run_cobol(cobol_binary, stdin), run_python(stdin),
            f"./payroll ({name})", f"payroll.py ({name})",
        )


# --- 3. Generated test: random valid employee files -------------------------

ID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .'-"


def cents(n: int) -> str:
    """Integer hundredths -> PIC 9(3)V99 text, e.g. 4250 -> '04250'."""
    return f"{n:05d}"


any_amount = st.integers(0, 99_999)
odd_cents = st.integers(0, 49_999).map(lambda n: 2 * n + 1)

hours_strategy = st.one_of(
    any_amount,
    st.sampled_from([0, 3_999, 4_000, 4_001]),  # 0 h and around 40 h exactly
    st.integers(6_000, 99_999),  # big overtime
)

pay_strategy = st.one_of(
    st.tuples(hours_strategy, any_amount),
    # Gross near $1,000: 40 h at ~$25/h gives 996.00-1004.00.
    st.tuples(st.just(4_000), st.integers(2_490, 2_510)),
    # Half-cent pay: hours ending in .50 times an odd-cents rate.
    st.tuples(st.integers(0, 99).map(lambda n: 100 * n + 50), odd_cents),
    # Half-cent low-bracket tax: 1.00 h, so gross == rate, rate cents = 10 mod 20.
    st.tuples(st.just(100), st.integers(0, 4_999).map(lambda n: 20 * n + 10)),
    # Half-cent high-bracket tax: 2.00 h at an odd-cents rate over $500/h.
    st.tuples(st.just(200), st.integers(25_000, 49_999).map(lambda n: 2 * n + 1)),
)

record_strategy = st.builds(
    lambda emp_id, name, pay: emp_id + name.ljust(20) + cents(pay[0]) + cents(pay[1]),
    st.text(ID_CHARS, min_size=5, max_size=5),
    st.text(NAME_CHARS, max_size=20),
    pay_strategy,
)

file_strategy = st.builds(
    lambda records, final_newline: (
        "\n".join(records) + ("\n" if final_newline and records else "")
    ).encode("ascii"),
    st.lists(record_strategy, max_size=25),
    st.booleans(),
)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(stdin=file_strategy)
def test_generated_parity(cobol_binary, stdin):
    assert_same_output(
        run_cobol(cobol_binary, stdin), run_python(stdin), "./payroll", "payroll.py"
    )


# --- Input validation (deliberate divergence, see BUSINESS_RULES.md §1) -----


def test_invalid_record_is_rejected():
    result = subprocess.run(
        [sys.executable, str(ROOT / "payroll.py")],
        input=b"00007Short\n", capture_output=True,
    )
    assert result.returncode == 1
    assert b"expected 35 characters" in result.stderr
