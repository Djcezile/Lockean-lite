# M8 ETF market data provider comparison

**Decision: BLOCKED for acquisition.** The leading quote request is Alpaca
Market Data API Historical Stock Bars and Historical Quotes with
`feed=sip`, plus point-in-time Security Master and Corporate Actions
reference data. No provider has cleared the [M7 evidence gates](ETF-DATA-ELIGIBILITY-MATRIX.md).

| Priority | Exact product and intended role | Documented coverage | Technical and commercial gap |
|---|---|---|---|
| 1 · Price and quote diligence | Alpaca Historical Stock Bars, `timeframe=1Day`, `adjustment=raw`, `feed=sip`; Historical Quotes, `feed=sip` | Alpaca lists US stocks and ETFs and history since 2016 for Basic and Algo Trader Plus. SIP covers US exchanges. Historical SIP availability under Basic is subject to the documented recency restriction. Quotes expose bid/ask prices, sizes, venues and timestamp. Bars allow split, dividend and spin-off adjustments. A1–A4. | Confirm the exact date/symbol/field coverage and business research contract. Bar timestamps label intervals. Historical quote timestamps and symbol `asof` mapping alone cannot prove when a corrected bar, security record or distribution reached a consumer. Corporate Actions SSE documents replay of mutations but the required historical replay horizon and terms remain unknown. A5–A6. |
| 2 · Commercial alternative | Massive Stocks Business historical US stocks/ETF Custom Bars, Quotes, All Tickers, Splits and Dividends | Public documentation lists bars and tick NBBO history as far back as 2003-09-10 for listed securities, with Business access to the archive. REST bars default to split adjustment and can return raw bars. Dividends are separate. Date-keyed active/inactive ticker snapshots and some list/delist fields are available. M1–M4. | Confirm business historical-only pricing and whether any expansion or exchange fees apply. Vendor documents that public split/dividend endpoints lack record availability timestamps and that current REST bars can reflect later corrections. Require a revision and publication sidecar. M5–M7. |
| Reference lead; conditional quote fallback | Databento Security Master, Corporate Actions and Adjustment Factors. Databento US Equities Mini (`EQUS.MINI`) OHLCV-1d and MBP-1 only as a separately assessed comparator or bounded execution input. | Security Master documents point-in-time listed and delisted records. Corporate Actions and Adjustment Factors document event identity, update times, revisions and rescissions. Mini aggregates component ATS and Reg NMS feeds and exposes event and capture timestamps. D1–D5. | Mini is a component-venue composite. Venue identity and sequence are suppressed, and top size aggregates odd lots across venues. It cannot substitute for SIP NBBO or venue-executable size under the proposed design. Verify exact archival depth, reference version/ETF event coverage, license, and full costs per schema. D4–D7. |

The **first diligence request** is a narrowly scoped historical-only Alpaca SIP
package. Its documented depth can cover the proposed 2019–2026 envelope and
its quote fields provide a candidate input for conservative execution estimates.
The proposed reference sidecar is Databento Security Master and Corporate
Actions, with Adjustment Factors as a cross-check. Use independent source
documentation and retained revision evidence for point-in-time availability.
Massive Stocks Business is the consolidated alternative if it can document
equivalent evidence and a feasible historical-only contract. Separate venue
data or richer order books are higher-cost options if quote sizes or venue
eligibility cannot support the execution model.

Daily OHLCV is a feature and benchmark input. A vendor's current adjusted
series is a reconciliation control. Build as-known total return from raw
prices and lawful, timestamped distribution and split vintages using a
predeclared reinvestment convention. A displayed quote is evidence for a
conservative fill model, with staleness, size, conditions, halts, spread,
slippage and partial or missed fills accounted for. ETF results remain a
hypothesis, separate from [published futures trend evidence](https://fairmodel.econ.yale.edu/ec439/mosk.pdf).

Source IDs and exact open questions are in the [evidence register](PRODUCT-AND-RIGHTS-EVIDENCE.md).
