# Payroll business rules

These rules come from reading `payroll.cob` closely. Each rule cites the COBOL
line numbers it comes from (`L104` = line 104), so anyone can check it against
the source. The Python rewrite (`payroll.py`) implements these rules and nothing more.

## COBOL notation used below

| Notation | Meaning |
|---|---|
| `PIC X(n)` | Text field, exactly *n* characters, padded with spaces. |
| `PIC 9(n)` | Unsigned number with *n* digits. |
| `V` | An *implied* decimal point. Nothing is stored for it, so `9(3)V99` occupies 5 characters and `04250` means `042.50`. |
| `Z` | In an output (edited) picture: a digit, shown as a space when it is a leading zero. |
| `,` `.` in an edited picture | A literal comma or decimal point. A comma with only suppressed zeros to its left also turns into a space. |
| `COMPUTE … ROUNDED` | Round the result to the target field's decimal places, half away from zero. All values here are non-negative, so this is the same as half-up. |
| `COMPUTE` without `ROUNDED` | Drop any extra decimal places (truncate). |
| `MOVE` a number into a smaller field | Drop high-order digits that don't fit, silently. |

## 1. Input (L21–31)

- Input is read from **stdin** (`ASSIGN TO KEYBOARD`, L21). Each line is one record
  (`LINE SEQUENTIAL`, L22). A missing newline after the last line is fine.
- Each record is 35 characters:

| Columns | Field | PIC | Meaning | Example |
|---|---|---|---|---|
| 1–5 | `EMP-ID` (L28) | `X(5)` | Employee ID, text | `00003` |
| 6–25 | `EMP-NAME` (L29) | `X(20)` | Name, space-padded | `Chen Wei␣␣␣…` |
| 26–30 | `EMP-HOURS` (L30) | `9(3)V99` | Hours worked, 0.00–999.99 | `05500` = 55.00 |
| 31–35 | `EMP-RATE` (L31) | `9(3)V99` | Hourly rate, 0.00–999.99 | `04575` = 45.75 |

- **Valid input** means every line is exactly 35 characters of printable ASCII,
  and columns 26–35 are digits only.
- The COBOL program does **not** validate. A short line is padded with spaces and
  the blank numeric field prints as garbage (`   .00`). That behaviour is out of
  scope: `payroll.py` exits with an error on invalid input instead of copying it.

## 2. Regular and overtime hours (L38, L104–110)

- Standard week: `WS-STD-HOURS` = 40.00 (L38).
- If hours **> 40** (strictly greater, L104): regular = 40.00 and overtime = hours − 40 (L105–106).
- Otherwise: regular = hours and overtime = 0 (L108–109). Exactly 40 hours means no overtime.
- Both values are exact, because hours have 2 decimal places and so does the target field.

## 3. Pay (L39, L112–115)

| Step | Formula | Rounding | Line |
|---|---|---|---|
| Regular pay | regular hours × rate | **ROUNDED** to cents | L112 |
| Overtime pay | overtime hours × rate × 1.5 | **ROUNDED** to cents | L113–114 |
| Gross | regular pay + overtime pay | none (already cents) | L115 |

- The overtime factor `WS-OT-FACTOR` is 1.5 (L39).
- Overtime pay is computed **in full and rounded once**. It is *not*
  `round(hours × rate) × 1.5`. Example: 15.00 h × 45.75 × 1.5 = 1029.375 → **1029.38**.
- Each pay component is rounded **separately** before they are added. Gross is
  not rounded as a whole.

## 4. Tax (L40–42, L117–123)

- Bracket threshold `WS-BRACKET` = 1000.00 (L40). Low rate 15% (L41), high rate 25% (L42).
- If gross **> 1000.00** (strictly greater, L117):
  tax = 1000.00 × 0.15 + (gross − 1000.00) × 0.25, **ROUNDED** once at the end (L118–120).
- Otherwise: tax = gross × 0.15, **ROUNDED** (L122).
- Gross of exactly 1000.00 is taxed entirely at 15% (150.00).
- Half-cent example: 226.50 × 0.15 = 33.975 → **33.98**.

## 5. Net (L125)

- Net = gross − tax. No rounding is needed (both are in cents).

## 6. Totals (L54–57, L127–130)

- Count of employees (`9(5)`), and running sums of gross, tax and net (`9(9)V99` each).
- The sums add the **already-rounded** per-employee amounts. Nothing is rounded again.
- Behaviour on overflow (more than 99,999 employees, or a total ≥ 1,000,000,000.00)
  is not specified, because the `ADD` statements have no `ON SIZE ERROR` clause.
  It is out of scope.

## 7. Output (L59–87, L92, L132–145)

All lines go to **stdout** via `DISPLAY`, one line each, with no trailing spaces
(every line ends with a field, not with filler).

### Header (L59–65, printed first at L92)

```
ID    NAME                   HOURS        GROSS         TAX         NET
```

Built from fixed-width text fields, each padded on the right with spaces to its
`PIC X(n)` width: `ID` → 6, `NAME` → 21, `␣␣HOURS` (7 characters) → 8, then
`␣␣␣␣␣␣␣GROSS`, `␣␣␣␣␣␣␣␣␣TAX` and `␣␣␣␣␣␣␣␣␣NET` at 12 each. Total width is 71.
Detail and totals lines are 69 characters wide.

### Detail line, one per employee in input order (L67–78, L132–138)

| Width | Content | PIC |
|---|---|---|
| 5 | ID, as read | `X(5)` |
| 1 | space | |
| 20 | name, as read (including its padding) | `X(20)` |
| 1 | space | |
| 6 | hours | `ZZ9.99` |
| 2 | spaces | |
| 10 | gross | `ZZZ,ZZ9.99` |
| 2 | spaces | |
| 10 | tax | `ZZZ,ZZ9.99` |
| 2 | spaces | |
| 10 | net | `ZZZ,ZZ9.99` |

- Edited numbers are right-aligned, leading zeros become spaces, and a thousands
  comma appears only once there are digits to its left. At least one integer
  digit is always shown: `0.00` rather than `.00`.
- **Silent truncation:** `ZZZ,ZZ9.99` holds 6 integer digits. A gross of
  1,479,970.20 prints as `479,970.20`, with the leading digit dropped (L135–137).
  In other words, the value printed is the amount mod 1,000,000.

### Totals line, printed after all records (L80–87, L140–145)

| Width | Content | PIC |
|---|---|---|
| 7 | `TOTALS ` | |
| 5 | employee count | `ZZZZ9` |
| 10 | ` EMPLOYEES` | |
| 11 | spaces | |
| 12 | total gross | `Z,ZZZ,ZZ9.99` |
| 12 | total tax | `Z,ZZZ,ZZ9.99` |
| 12 | total net | `Z,ZZZ,ZZ9.99` |

- Each total is printed mod 10,000,000 (7 integer digits).
- **No separator between total columns:** when a total uses all 7 integer digits,
  it touches the previous column, e.g. `369,892.551,110,077.65`. This is the
  legacy output and the rewrite must reproduce it.
- With no input records, the header and a totals line of zeros are still printed.
