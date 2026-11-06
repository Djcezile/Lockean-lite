# M6 data and licensing matrix

The products below are diligence leads. Evidence IDs refer to the
[evidence register](EVIDENCE-REGISTER.md). No contract, entitlement, account, quote
or dataset was obtained. Legal usability is UNKNOWN for the exact proposed use.

| Candidate | Minimum product coverage and frequency | Required timestamp and integrity evidence | Public documentation lead | Acquisition and recurring cost exposure |
|---|---|---|---|---|
| Trend-following momentum | Daily ETF bars and distributions/splits, point-in-time listings and delistings, executable quote/depth observations at scheduled entry/exit | Session completion, publication and actual availability of bars/actions, as-known adjustments, provider and local custody, stable instrument IDs | D5–D8. Verify ETF quote schema and corporate-action coverage separately. | UNKNOWN. Fewer high-resolution windows, plus history, storage, archive and license costs. |
| Post-earnings announcement drift | As-released EPS and revision history, pre-release consensus snapshots, announcement timestamps, daily equity data and entry/exit quotes | Comparable EPS basis and fiscal period, first release vs EDGAR acceptance, forecast cutoff and actual receipt, issuer/security links, delisting and actions | D1–D2 for filings and timing caveats. D4 for expectations. D5–D7 for prices/actions. | UNKNOWN. Potential separate estimates and release archives, quality review and revision storage. |
| Intraday ETF momentum | One-minute bars, ordered trades, synchronized top-of-book and depth where required, calendar, flags for auctions and halts | End of interval plus availability lag, corrections, event/provider receipt time, historical local availability, pre-close order cutoff | D5–D7. Confirm venue coverage or consolidated quote source and whether the schema represents the intended route. | UNKNOWN. Repeated high-resolution reads, compute, retention and live licensing if later approved. |
| Short-term mean reversion | Daily universe and total-return inputs, execution quotes and size, issuer event flags, delisting returns and eligible action history | Stale quotes and spread bounce detection, known-at event exclusions, proper mapping and fill window | D5–D7 plus a separately verified event and delisting source. | UNKNOWN. Broad-universe joins and execution data, plus high turnover and borrow if added. |
| News-reaction trading | Licensed story versions and entity mappings, first release and correction history, synchronized quotes/trades with resolution finer than the intended reaction window | Original dissemination and each revision, source and vendor arrival, local availability, ordering, clock alignment and deduplication | D3 and D5–D7. D1–D2 only for a separately scoped filings strategy. | UNKNOWN. Multiple feeds, large revision archive, low-latency processing and ongoing curation. |

## Rights gate

Every exact product and version requires independent, dated proof of the issuer's
authority and scope, including venue terms if applicable. Apply this matrix per
product and per proposed use, including SEC material and its third-party attachments.

| Use | Current status | Evidence before admission |
|---|---|---|
| Internal research and internal non-display | UNKNOWN | Effective grant, named user/entity, historical environments and allowed computations. |
| Commercial internal use | UNKNOWN | Explicit grant for commercial entity, environments, feeds and non-display use. |
| Model or feature development | UNKNOWN | Permission to extract features, train and evaluate models, and retain model artifacts. |
| Raw retention | UNKNOWN | Allowed location, access controls, retention window and termination/deletion terms. |
| Derived-feature storage | UNKNOWN | Derived-data definition, retention and portability rules, including after termination. |
| Redistribution, reviewer access or external reporting | UNKNOWN | Exact audience, raw/derived publication rights, permitted displays and attribution. |
| Live use or deployment | UNKNOWN | Separate grant, fees and separate Founder approval for any operational use. |

Historical access and public documentation do not establish commercial rights.
Authenticate the applicable agreement or written issuer confirmation, freeze
its version and effective dates, and maintain a separately trusted rights record.
Require a written cost estimate for the fixed universe, date windows and schemas,
including exchange fees, renewal, cloud and termination costs. Verify actual
coverage, timestamp semantics and corrections under a separately authorized pilot.
A withheld or unaffordable quote blocks admission under the eventual budget and
leaves the economic hypothesis unresolved. Unverified access or timestamps also
block admission. No acquisition is authorized by this matrix.
