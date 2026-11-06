# M6 economic cost model

All values and commercial rights are UNKNOWN until independently verified for the
exact products, routes, study dates and intended use. The model specifies the
ledger and gates. It supplies no strategy performance estimate.

| Layer | Measure | Evidence needed |
|---|---|---|
| Statistical predictability | Gross contrast and uncertainty relative to frozen baseline | Preregistered endpoint, point-in-time records and multiplicity-adjusted inference. |
| Tradable net returns | Realistic fill-based returns net of execution and carrying costs | Executable quotes, sizes, latency, fees, borrow, financing and calibrated impact. |
| Broker-level paper P&L | Broker simulator ledger and reconciliation to intended orders | Separately authorized simulation, simulated fills and account assumptions. Paper fills may omit liquidity and impact. |
| All-in business profitability | Tradable net dollars less data, rights, infrastructure, maintenance, capital and other business costs | Evidence for each recurring and one-time cost, usable capital and drawdown limits, plus independent reconciliation. |

## Ledger

Measure gross marked and realized cash flows with consistent conventions for
distributions, cash yield and actions. Attribute implementation shortfall versus
the decision benchmark to spread crossing, delay, slippage, market impact and
missed or partial orders. Record commissions, venue and regulatory fees, borrow
rates, recalls, funding and financing separately. Either book actual fill prices
or subtract modeled execution shortfall from the benchmark. Avoid counting spread,
slippage and impact twice. If a fill is unavailable, model no fill and retain the
opportunity cost diagnostic. Use time-specific quotes, order size, participation
caps and stressed fill quality.

Track historical acquisition, recurring feeds, exchange and vendor licensing,
retention and redistribution costs, compute, storage, bandwidth, data QA and
engineering, monitoring, incident handling and ongoing maintenance. Separate
fixed and variable expenses, one-off setup and renewals. Allocate shared costs
using a preregistered rule and include fixed cost at the proposed scale.
Reconcile broker P&L line by line to real cost evidence, including charges outside
the broker ledger. Report capital utilization, drawdown and opportunity cost of
capital under defined capital and liquidity constraints.

| Candidate | Dominant hypothesis-specific stress |
|---|---|
| Trend-following momentum | Delayed entry, beta exposure, whipsaw turnover, clustered ETF exits and spread widening. |
| Post-earnings announcement drift | Data contract, announcement gaps, sector concentration, illiquid fills and future short-side borrow constraints. |
| Intraday ETF momentum | Late orders, spread and impact near close, auction cutoff, no-fill scenarios and venue data expense. |
| Short-term mean reversion | Daily turnover, stale midpoint, adverse selection and capacity falling as size grows. |
| News-reaction trading | End-to-end latency, deterioration in liquidity, rights for text/models and ongoing ingestion reliability. |

Before a study, freeze a budget cap, minimum net effect, decision latency,
capital and drawdown constraints, and base and adverse cost scenarios. Require
empirical support for cost magnitudes and actionable depth at each candidate
size. Vary latency, spread/impact, fill rate, turnover, funding and volume
jointly under adverse but evidenced conditions. Estimate break-even scale only
after cost inputs exist. Reject progression if rights/availability cannot be
proved, spend exceeds the authorized cap, net edge fails the minimum hurdle,
stress or capital limits fail, or expected scale cannot cover all-in expense.
A lack of lawful, affordable evidence leaves economic potential unresolved.
Paper P&L alone does not pass the all-in gate.
