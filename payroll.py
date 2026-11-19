"""Python rewrite of payroll.cob.

Reads fixed-width employee records on stdin and writes the payroll report on
stdout, byte-for-byte identical to the COBOL program. See BUSINESS_RULES.md;
comments of the form "L112" refer to lines in payroll.cob.

All money is decimal.Decimal. No floats are used anywhere.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

# WS-CONSTANTS (L37-42)
STD_HOURS = Decimal("40.00")
OT_FACTOR = Decimal("1.5")
BRACKET = Decimal("1000.00")
LOW_RATE = Decimal("0.15")
HIGH_RATE = Decimal("0.25")

CENT = Decimal("0.01")
RECORD_LEN = 35

# WS-HEADER (L59-65): each VALUE padded right to its PIC X(n) width.
HEADER = (
    "ID".ljust(6)
    + "NAME".ljust(21)
    + "  HOURS".ljust(8)
    + "       GROSS"
    + "         TAX"
    + "         NET"
)


class InvalidRecord(ValueError):
    pass


@dataclass(frozen=True)
class Employee:
    emp_id: str  # X(5)
    name: str  # X(20)
    hours: Decimal  # 9(3)V99
    rate: Decimal  # 9(3)V99


@dataclass(frozen=True)
class Pay:
    gross: Decimal
    tax: Decimal
    net: Decimal


def rounded(value: Decimal) -> Decimal:
    """COMPUTE ... ROUNDED into a V99 field (half away from zero; values are >= 0)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def implied_decimal(digits: str) -> Decimal:
    """PIC 9(3)V99: '04250' -> 42.50 (the V is an implied decimal point)."""
    return Decimal(digits).scaleb(-2)


def parse_record(line: str, line_no: int) -> Employee:
    """EMP-REC (L27-31)."""
    if len(line) != RECORD_LEN:
        raise InvalidRecord(f"line {line_no}: expected {RECORD_LEN} characters, got {len(line)}")
    if not all(" " <= ch <= "~" for ch in line):
        raise InvalidRecord(f"line {line_no}: non-printable or non-ASCII character")
    hours, rate = line[25:30], line[30:35]
    if not (hours.isdigit() and rate.isdigit()):
        raise InvalidRecord(f"line {line_no}: hours and rate must be digits")
    return Employee(line[0:5], line[5:25], implied_decimal(hours), implied_decimal(rate))


def compute_pay(emp: Employee) -> Pay:
    """PROCESS-EMPLOYEE (L103-125)."""
    # L104-110: strictly more than 40 hours is overtime.
    if emp.hours > STD_HOURS:
        reg_hours, ot_hours = STD_HOURS, emp.hours - STD_HOURS
    else:
        reg_hours, ot_hours = emp.hours, Decimal("0.00")

    reg_pay = rounded(reg_hours * emp.rate)  # L112 ROUNDED
    ot_pay = rounded(ot_hours * emp.rate * OT_FACTOR)  # L113-114 ROUNDED, once
    gross = reg_pay + ot_pay  # L115, exact

    # L117-123: strictly more than 1000.00 enters the high bracket.
    if gross > BRACKET:
        tax = rounded(BRACKET * LOW_RATE + (gross - BRACKET) * HIGH_RATE)
    else:
        tax = rounded(gross * LOW_RATE)

    net = gross - tax  # L125, exact
    return Pay(gross, tax, net)


def edit(value: Decimal, int_digits: int) -> str:
    """MOVE a V99 amount into a Z...,ZZ9.99 edited field with `int_digits` integer digits.

    Leading zeros (and commas with nothing to their left) become spaces, and
    digits beyond the field's capacity are dropped from the left, silently, as
    COBOL MOVE does.
    """
    cents = int((value * 100).to_integral_exact())
    cents %= 10 ** (int_digits + 2)  # high-order truncation
    whole, frac = divmod(cents, 100)
    width = int_digits + (int_digits - 1) // 3 + 3  # digits + commas + ".99"
    return f"{whole:,}.{frac:02d}".rjust(width)


def detail_line(emp: Employee, pay: Pay) -> str:
    """WS-DETAIL (L67-78), filled at L132-137."""
    return (
        emp.emp_id
        + " "
        + emp.name
        + " "
        + edit(emp.hours, 3)  # ZZ9.99
        + "  "
        + edit(pay.gross, 6)  # ZZZ,ZZ9.99
        + "  "
        + edit(pay.tax, 6)
        + "  "
        + edit(pay.net, 6)
    )


def totals_line(count: int, gross: Decimal, tax: Decimal, net: Decimal) -> str:
    """WS-TOTAL-LINE (L80-87), filled at L141-144. No separators between totals."""
    return (
        "TOTALS "
        + str(count % 100_000).rjust(5)  # ZZZZ9
        + " EMPLOYEES"
        + " " * 11
        + edit(gross, 7)  # Z,ZZZ,ZZ9.99
        + edit(tax, 7)
        + edit(net, 7)
    )


def run(lines: Iterable[str]) -> list[str]:
    """MAIN-PARA (L90-101): header, one detail line per record, totals."""
    out = [HEADER]
    count = 0
    tot_gross = tot_tax = tot_net = Decimal("0.00")
    for line_no, line in enumerate(lines, start=1):
        emp = parse_record(line, line_no)
        pay = compute_pay(emp)
        count += 1  # L127-130
        tot_gross += pay.gross
        tot_tax += pay.tax
        tot_net += pay.net
        out.append(detail_line(emp, pay))
    out.append(totals_line(count, tot_gross, tot_tax, tot_net))
    return out


def read_records(data: bytes) -> list[str]:
    """Split LINE SEQUENTIAL input; a final newline is optional."""
    text = data.decode("ascii", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def main() -> int:
    try:
        report = run(read_records(sys.stdin.buffer.read()))
    except InvalidRecord as exc:
        print(f"payroll.py: invalid input: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write("".join(line + "\n" for line in report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
