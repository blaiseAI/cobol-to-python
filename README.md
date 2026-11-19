# cobol-to-python

Migrating a legacy COBOL batch job to Python, and **proving** the rewrite
produces the same output, character for character.

> `payroll.cob` is a small sample program created to model a legacy batch payroll
> job. The migration approach, business-rule extraction and parity testing are
> the focus of this project. The program is intentionally shaped like real legacy code:
> fixed-width records on stdin, implied-decimal numeric fields, `ROUNDED` at
> specific steps, edited numeric output, and a few silent quirks of the kind a
> real migration has to preserve.

## The problem

Batch jobs like this one often run unchanged for decades. The source code *is*
the specification, and downstream systems depend on the exact report layout,
down to a column's position or how a half cent rounds. A rewrite that is
"basically right" is wrong: a one-cent drift in tax or a shifted column breaks
reconciliation for everything downstream.

## The approach

1. **Rules first.** [`BUSINESS_RULES.md`](BUSINESS_RULES.md) extracts every rule
   from `payroll.cob`, with line references: input layout, overtime, tax brackets,
   *where* rounding happens, totals and output format. Writing it surfaced two
   behaviours that would be easy to "fix" by accident:
   - Amounts too large for a report column lose their leading digits silently
     (`1,479,970.20` prints as `479,970.20`).
   - Total columns have no separator, so 7-digit totals run together
     (`369,892.551,110,077.65`).
2. **Rebuild.** [`payroll.py`](payroll.py) implements those rules with
   `decimal.Decimal` and `ROUND_HALF_UP` at exactly the COBOL `ROUNDED` steps.
   No floats are used anywhere. A small `edit()` function reproduces COBOL
   edited pictures such as `ZZZ,ZZ9.99`, including the truncation.
3. **Prove parity.** The tests run both programs and require identical output.

## Running it

Requires GnuCOBOL (`cobc`) and Python 3.10+.

```sh
# macOS: brew install gnucobol    Ubuntu/Debian: sudo apt-get install gnucobol
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# legacy job
cobc -x payroll.cob -o payroll
./payroll < input.txt > cobol_output.txt

# rewrite
python payroll.py < input.txt

# parity tests
pytest -v
```

Input is one 35-character record per line: 5-character ID, 20-character name,
hours and rate as 5 digits with an implied decimal point (`04250` = 42.50). See
`input.txt` and `BUSINESS_RULES.md` §1.

## What the tests guarantee

| Test | What it checks | Needs `cobc` |
|---|---|---|
| `test_golden_output` | `payroll.py` on `input.txt` equals the committed `cobol_output.txt` byte for byte. | no |
| `test_live_parity` | Both programs give identical output on hand-picked edge inputs: empty file, no trailing newline, overflowing columns, gross exactly $1,000.00 and one cent over. | yes |
| `test_generated_parity` | 300 random valid employee files (0–25 records each) give identical output from both programs. The generator deliberately builds exact half-cent pay and tax, 0 h, 39.99/40.00/40.01 h, big overtime and gross near $1,000. | yes |
| `test_invalid_record_is_rejected` | Malformed lines are rejected with an error. | no |

Any mismatch fails with a line-by-line unified diff. As a sanity check, switching
`ROUND_HALF_UP` to banker's rounding (`ROUND_HALF_EVEN`) makes all three parity
tests fail. Hypothesis shrinks that case to 1.00 h at $0.30, where tax is
exactly 0.045.

CI (`.github/workflows/ci.yml`) installs GnuCOBOL on `ubuntu-latest`, compiles
`payroll.cob`, and runs the suite with `REQUIRE_COBOL=1`, so a missing compiler
fails the build instead of silently skipping the COBOL comparisons.

### What they don't guarantee

- **Invalid input.** COBOL accepts malformed records and prints garbage (a blank
  hours field shows as `   .00`). The rewrite deliberately rejects such records
  instead, so parity is only claimed for valid input.
- **Accumulator overflow** (more than 99,999 employees, or a total ≥ $1 billion)
  is unspecified in the COBOL, because there is no `ON SIZE ERROR` clause, and it
  is not tested.
- Parity is tested against GnuCOBOL (3.2 locally; CI uses whatever version Ubuntu's apt ships). A mainframe
  compiler could differ in details such as how stdin is read.

## Layout

```
payroll.cob          legacy batch job (the source of truth)
input.txt            sample employee records
cobol_output.txt     golden output from ./payroll < input.txt
BUSINESS_RULES.md    rules extracted from payroll.cob, with line references
payroll.py           Python rewrite
tests/               parity tests (pytest + hypothesis)
```
