      *> PAYROLL - weekly payroll report.
      *> Reads fixed-width employee records from stdin, writes a
      *> report to stdout. This is the legacy program to be migrated.
      *>
      *> Input record (35 chars, one per line):
      *>   cols  1-5   EMP-ID   X(5)
      *>   cols  6-25  NAME     X(20)
      *>   cols 26-30  HOURS    9(3)V99   e.g. 04250 = 42.50 h
      *>   cols 31-35  RATE     9(3)V99   e.g. 02500 = 25.00 /h
      *>
      *> Rules:
      *>   - Overtime: hours over 40 paid at 1.5x rate.
      *>   - Tax: 15% on the first 1000.00 of gross, 25% above that.
      *>   - Amounts rounded half-up to cents (COBOL ROUNDED).
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMP-FILE ASSIGN TO KEYBOARD
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  EMP-FILE.
       01  EMP-REC.
           05  EMP-ID          PIC X(5).
           05  EMP-NAME        PIC X(20).
           05  EMP-HOURS       PIC 9(3)V99.
           05  EMP-RATE        PIC 9(3)V99.

       WORKING-STORAGE SECTION.
       01  WS-EOF              PIC X VALUE "N".
           88  END-OF-FILE     VALUE "Y".

       01  WS-CONSTANTS.
           05  WS-STD-HOURS    PIC 9(3)V99   VALUE 40.
           05  WS-OT-FACTOR    PIC 9V9       VALUE 1.5.
           05  WS-BRACKET      PIC 9(5)V99   VALUE 1000.
           05  WS-LOW-RATE     PIC V99       VALUE .15.
           05  WS-HIGH-RATE    PIC V99       VALUE .25.

       01  WS-CALC.
           05  WS-REG-HOURS    PIC 9(3)V99.
           05  WS-OT-HOURS     PIC 9(3)V99.
           05  WS-REG-PAY      PIC 9(7)V99.
           05  WS-OT-PAY       PIC 9(7)V99.
           05  WS-GROSS        PIC 9(7)V99.
           05  WS-TAX          PIC 9(7)V99.
           05  WS-NET          PIC 9(7)V99.

       01  WS-TOTALS.
           05  WS-COUNT        PIC 9(5)      VALUE 0.
           05  WS-TOT-GROSS    PIC 9(9)V99   VALUE 0.
           05  WS-TOT-TAX      PIC 9(9)V99   VALUE 0.
           05  WS-TOT-NET      PIC 9(9)V99   VALUE 0.

       01  WS-HEADER.
           05  FILLER  PIC X(6)  VALUE "ID".
           05  FILLER  PIC X(21) VALUE "NAME".
           05  FILLER  PIC X(8)  VALUE "  HOURS".
           05  FILLER  PIC X(12) VALUE "       GROSS".
           05  FILLER  PIC X(12) VALUE "         TAX".
           05  FILLER  PIC X(12) VALUE "         NET".

       01  WS-DETAIL.
           05  D-ID            PIC X(5).
           05  FILLER          PIC X     VALUE SPACE.
           05  D-NAME          PIC X(20).
           05  FILLER          PIC X     VALUE SPACE.
           05  D-HOURS         PIC ZZ9.99.
           05  FILLER          PIC XX    VALUE SPACES.
           05  D-GROSS         PIC ZZZ,ZZ9.99.
           05  FILLER          PIC XX    VALUE SPACES.
           05  D-TAX           PIC ZZZ,ZZ9.99.
           05  FILLER          PIC XX    VALUE SPACES.
           05  D-NET           PIC ZZZ,ZZ9.99.

       01  WS-TOTAL-LINE.
           05  FILLER          PIC X(7)  VALUE "TOTALS ".
           05  T-COUNT         PIC ZZZZ9.
           05  FILLER          PIC X(10) VALUE " EMPLOYEES".
           05  FILLER          PIC X(11) VALUE SPACES.
           05  T-GROSS         PIC Z,ZZZ,ZZ9.99.
           05  T-TAX           PIC Z,ZZZ,ZZ9.99.
           05  T-NET           PIC Z,ZZZ,ZZ9.99.

       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT EMP-FILE
           DISPLAY WS-HEADER
           PERFORM UNTIL END-OF-FILE
               READ EMP-FILE
                   AT END SET END-OF-FILE TO TRUE
                   NOT AT END PERFORM PROCESS-EMPLOYEE
               END-READ
           END-PERFORM
           CLOSE EMP-FILE
           PERFORM PRINT-TOTALS
           STOP RUN.

       PROCESS-EMPLOYEE.
           IF EMP-HOURS > WS-STD-HOURS
               MOVE WS-STD-HOURS TO WS-REG-HOURS
               COMPUTE WS-OT-HOURS = EMP-HOURS - WS-STD-HOURS
           ELSE
               MOVE EMP-HOURS TO WS-REG-HOURS
               MOVE 0 TO WS-OT-HOURS
           END-IF

           COMPUTE WS-REG-PAY ROUNDED = WS-REG-HOURS * EMP-RATE
           COMPUTE WS-OT-PAY ROUNDED =
               WS-OT-HOURS * EMP-RATE * WS-OT-FACTOR
           COMPUTE WS-GROSS = WS-REG-PAY + WS-OT-PAY

           IF WS-GROSS > WS-BRACKET
               COMPUTE WS-TAX ROUNDED =
                   WS-BRACKET * WS-LOW-RATE
                   + (WS-GROSS - WS-BRACKET) * WS-HIGH-RATE
           ELSE
               COMPUTE WS-TAX ROUNDED = WS-GROSS * WS-LOW-RATE
           END-IF

           COMPUTE WS-NET = WS-GROSS - WS-TAX

           ADD 1        TO WS-COUNT
           ADD WS-GROSS TO WS-TOT-GROSS
           ADD WS-TAX   TO WS-TOT-TAX
           ADD WS-NET   TO WS-TOT-NET

           MOVE EMP-ID    TO D-ID
           MOVE EMP-NAME  TO D-NAME
           MOVE EMP-HOURS TO D-HOURS
           MOVE WS-GROSS  TO D-GROSS
           MOVE WS-TAX    TO D-TAX
           MOVE WS-NET    TO D-NET
           DISPLAY WS-DETAIL.

       PRINT-TOTALS.
           MOVE WS-COUNT     TO T-COUNT
           MOVE WS-TOT-GROSS TO T-GROSS
           MOVE WS-TOT-TAX   TO T-TAX
           MOVE WS-TOT-NET   TO T-NET
           DISPLAY WS-TOTAL-LINE.
