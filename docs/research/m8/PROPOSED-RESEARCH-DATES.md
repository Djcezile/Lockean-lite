# M8 proposed ETF study dates

These dates are a prospective design for separately authorized research
against historical inputs. They were selected using calendar rules and
chronological spacing, without inspecting market observations or outcomes.
The confirmation fold remains designated for independent custody and needs
a power and prior-exposure review before it can be called unseen.

## Calendar computation

Use the first scheduled XNYS session in each listed month, including early
closes when the regular-hours decision and execution are both feasible. Use 10:00 New York
decision and 10:15 later execution, subject to authenticated availability
and eligible quotes. At session index i the earliest feature/benchmark
dependency is i−252, the last required outcome session is i+21, and the
coverage span also includes every declared fold session. The proposed exit quote window begins at 10:15 New York on i+21. Embargo counts
the sessions strictly between adjacent expanded spans. The prospective
execution and benchmark rules must use those same boundaries and a
predeclared rule for missing inputs, overlapping positions and fills.

| Fold | Inclusive declared span, New York | First / last decision | Monthly decisions | First lookback | Last label/holding date | Expanded end | Prior embargo |
|---|---|---|---:|---|---|---|---:|
| Development | 2020-01-02 – 2021-06-30 | 2020-01-02 / 2021-06-01 | 18 | 2019-01-02 | 2021-06-30 | 2021-06-30 | — |
| Validation | 2022-09-01 – 2023-10-31 | 2022-09-01 / 2023-10-02 | 14 | 2021-09-01 | 2023-10-31 | 2023-10-31 | 43 |
| Independent holdout | 2025-01-02 – 2026-08-31 | 2025-01-02 / 2026-08-03 | 20 | 2024-01-02 | 2026-09-01 | 2026-09-01 | 41 |

The continuous daily coverage envelope is **2019-01-02 through 2026-09-01**,
1,927 eligible sessions under the planning calendar. No evaluation or
selection uses observations from the gaps. Preserve the required full-span
coverage and scope any later custody to the approved use. Both embargoes
exceed the 21-session minimum. Reserve the holdout and its dependencies for
independent access under a separately reviewed protocol. Twenty holdout
decisions may be insufficient after dependence and execution attrition.
Require an ex ante power calculation and stop if the effective sample
cannot support the agreed minimum effect. Changing dates after exposure
requires a separately approved confirmation design.

The plan ends before **October 20–December 31, 2026, inclusive, America/New_York**.
Reject any fold, lookback, benchmark or holding span touching or straddling
that range. Quote queries, if separately approved, must also obey the
boundary after UTC conversion. Keep calendar labels, half days, time zones
and session identifiers in the frozen protocol. For planning, computed offline
with [exchange-calendars 4.13.2](https://pypi.org/project/exchange-calendars/4.13.2/)
XNYS rules, including the [January 9, 2025 NYSE closure](https://www.nyse.com/publicdocs/nyse/markets/american-options/rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf).
Confirm exact venue calendars and exceptions against independent exchange
evidence before registration. [NYSE schedules](https://www.nyse.com/trade/hours-calendars)

The local evidence bundle records the calendar-only calculation, protected
boundary checks and M7 simulation with generated witnesses. Those results
do not verify vendor coverage or authorize use of real observations.
