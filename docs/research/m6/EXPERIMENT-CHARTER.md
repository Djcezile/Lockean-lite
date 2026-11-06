# M6 experiment charter

These are prospective specifications. A separately authorized protocol must freeze
data products, exact dates, universe rules, costs, decision times and reviewer
access before any empirical work. Candidate-specific choices below are design
proposals. Any later change after viewing validation evidence counts as a new
trial and requires a fresh confirmation period.

## Shared protocol

1. Verify point-in-time rights and data provenance before any evaluation. Bind
   source/product, version, instrument IDs, raw digests and custody, first
   dissemination, revisions and provider/local availability, approved purpose
   and trust evidence. M5 synthetic qualification does not establish real-data
   admissibility. Authenticate external inputs under a separately reviewed protocol.
2. In America/New_York, exclude **October 20 through December 31, 2026, inclusive**.
   No actual observations from that interval may be acquired, inspected, used for
   tuning, selection or evaluation under M6. A future study must also exclude it
   unless separately authorized and independently reviewed. Reject study folds
   whose features, lookback, benchmark, holding or label windows overlap it.
   Select an eligible contiguous period outside the protected interval.
3. Allocate chronological development, validation, then untouched holdout by
   preregistered date boundaries, fixed using permitted coverage metadata and
   sample-size planning. In development use expanding windows. Purge training
   labels and exposures that overlap evaluation windows. Embargo at least the
   maximum label/holding horizon at folds, lengthened where dependence demands it.
   Compute inputs and eligibility as of each decision from completed observations.
   Preserve revisions, bankruptcies, delistings, as-known actions and exchange calendars.
4. Define one primary one-sided comparison per authorized candidate against its
   stated baseline. Use paired portfolio or event returns, with date/issuer
   clustering or a block bootstrap suited to the unit of dependence. Predeclare
   the dependence structure, sample-size/power calculation, minimum economically
   relevant effect, and familywise alpha of 0.05. Apply Holm to the complete
   confirmatory family, including all tested candidates, signals and horizons if
   they are used for inference. Record every attempted variant. Report adverse
   regimes and intervals. Exploratory subgroup, regime and variant comparisons
   cannot rescue a failed primary test.
5. Separate gross prediction from net execution and all-in costs. The primary
   statistical endpoint is the candidate-specific gross contrast below. A
   predeclared after-cost hurdle and a stressed cost/capacity test are separate
   mandatory gates. Reject progression for a nonpassing primary contrast, a net
   result below the preregistered hurdle, material dependence on optimistic
   fills, concentration outside approved constraints, or failure of cost/capital
   stress. Insufficient effective sample size is inconclusive. Invalidating
   conditions include leakage, evidence or rights gaps, lost lineage, mismatched
   clocks, unauthorized windows, holdout inspection, and protocol drift.
6. Independent acceptance requires exact code and configuration, frozen dataset
   and rights identities, as-of joins, exclusions, dependency and calendar
   versions, validation/holdout isolation, rejected proposals, full trial ledger,
   cost inputs, raw-to-report hashes, and reproduction by an authorized reviewer.
   Evaluate the holdout once under independently reviewed custody. No
   proposal enters live Authority or Gateway from this study.

## Candidate experiments

### Trend-following momentum

- H1 is a positive incremental 21-session return for a positive trailing
  252-completed-session ETF return, compared with a preregistered exposure-matched
  passive allocation. H0 is no positive incremental contrast. Use a fixed
  monthly decision schedule, long/cash, and equal notional allocations without
  volatility scaling in the primary comparison. Include buy-and-hold and cash as
  descriptive comparators. Return is measured from the next eligible executable
  window, with a fixed holding horizon and dividends included.
- Require historical ETF identifiers and listings, actions and distributions as
  known, completed daily bars, executable quotes and sufficient eligible sessions
  for the lookback and horizon. Freeze membership and weights before entry.
- Apply schedule-matched turnover, bid/ask, commissions, slippage, missed fills,
  impact and cash yield. Report conditional performance in abrupt reversal and
  high-turnover periods. A result explainable by passive beta, cash timing or
  optional scaling fails the incremental hypothesis.

### Post-earnings announcement drift

- H1 is a positive 20-session sector- and liquidity-matched excess return for
  positive pre-release consensus surprises. H0 is no positive contrast. Freeze
  the EPS basis and surprise threshold before data access. Compare eligible
  positive surprises against matched nonsurprise releases and a passive
  same-risk comparator. First study is long/cash.
- Require original release and receipt, as-issued actual and pre-release
  consensus version with exact fiscal mapping, daily returns, actions, issuer
  and security history, and execution quotes. Skip an event if the first eligible
  regular session lacks independently verified availability before the
  decision cutoff. Never replace original values with restated values.
- Model next-session gaps, spread, fees, slippage, capacity and event clustering.
  Failure includes loss of signal in the predeclared liquid universe or under
  independently evidenced event delay. Short-side borrow and financing are
  separate evidence if a future design adds shorting.

### Intraday ETF momentum

- H1 is positive signed final-half-hour return relative to a timing-matched
  no-direction baseline, with signed direction fixed by prior close to first
  half-hour end. H0 is no positive contrast. Compare with a predeclared
  unconditional same-window directional exposure at equal risk and cash.
- Require completed opening windows, prior close, quotes/trades, auction flags,
  exchange schedule and halt records. For the primary design use regular full
  sessions and enter only after the pre-close authorization decision and modeled
  latency. Exit at a fixed tradable cutoff. Auction fills require independently
  validated eligibility and cutoff rules.
- Model fees, quote crossings, late fills, partial fills and clustered close
  impact. Failure includes edge vanishing at executable entry and exit or relying
  on unapproved closing-price fills.

### Short-term mean reversion

- H1 is a positive one-session residual return for the liquid-stock basket with
  the most negative completed prior-session sector-adjusted move. H0 is no
  positive matched contrast. Compare with a neutral residual-move basket
  matched by sector, turnover and liquidity. Fix the cutoff and one-session
  holding period, and use long/cash in the initial study.
- Require point-in-time listed and delisted universe, actions, event flags and
  tradeable quotes around the next-session decision and exit. Diagnose bid/ask
  bounce using quote midpoints for prediction only and executable sides for fills.
- Model daily turnover, spreads, commissions, gap/slippage, impact and rejects.
  Failure includes the residual disappearing with stale quotes removed or at
  executable quote sides.

### News-reaction trading

- H1 is a positive signed return over 30 minutes from the first eligible decision
  after verified local availability of a directional, novel corporate headline.
  H0 is no positive contrast. Compare against timestamp-, sector- and
  volatility-matched no-news windows and a frozen neutral classifier. Predefine
  event types, signal construction, repeated-story treatment and an
  executable long/cash mapping.
- Require a versioned licensed news archive, an immutable mapping from articles
  to securities, contemporaneous quotes/trades and a latency budget from
  dissemination through decision, independent approval and execution. Align
  clocks and retain event receipt, not just publication time. Remove earnings
  overlap by a predeclared, as-known rule.
- Apply headline-specific spread, gaps, fees, latency, adverse selection and
  missed fills. Reject if feasible decision latency consumes the apparent edge
  or the signal depends on duplicate or revised stories.

See the [economic cost model](ECONOMIC-COST-MODEL.md) for the economic gates and
the [data matrix](DATA-AND-LICENSING-MATRIX.md) for required rights.
