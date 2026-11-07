# M8 ETF evidence gates mapped to M7

This matrix maps product leads to the merged [M7 contract](../m7/DATA-ELIGIBILITY-CONTRACT.md).
**Documented** means a public specification supports a capability. **Open**
requires external evidence. **Conflict** identifies a known limitation for
the proposed use. No product qualifies on this review.

| M7 evidence gate | Alpaca SIP plus reference sidecar | Massive Stocks Business | Databento products and fallback | Required exit evidence |
|---|---|---|---|---|
| Exact study identity and current checkpoint | Open | Open | Open | Independent pin to exact canonical protocol, licensed artifacts and revision. Separate evaluation time and purpose. Replay and revocation custody must be independently reviewed. |
| Source, product/version and raw integrity | A1–A5 document interfaces. Open | M1–M3 document interfaces. Open | D1–D5 document interfaces. Open | Verify lawful issuer and custody. Bind endpoint/schema/version, request range, instrument mapping, file identities and SHA-256 before parsing. Pin a separate receipt/attestation. |
| Daily ETF data and full coverage | A1–A3 document daily SIP and since-2016 plan history. Exact calendar completeness open. | M1–M2 advertise deeper archives. Exact completeness open. | D4 documents OHLCV-1d over component venues. Verify historical depth and session-aligned bars. | Cover every session in each declared fold and all dependencies. Validate planned 1,927-session envelope and expected missing/closed cases. Confirm calendar, special closures, halts and standard UTC representation. |
| Historical universe, listings and closures | A3 symbol as-of resolution, D1/D2 as sidecar. Open | M3 has date-keyed active/inactive snapshots and optional list/delist dates. Open | D1/D2 are documented reference leads. Open | Stable share-class/listing mapping, currency and venue as known. Confirm inception, closure/delisting, cash/terminal treatment and survivorship-safe frozen rules. No present-day survivor screen. |
| Actions and as-known total return | Raw bars A3, D2/D3 or A5 archive if complete. Open | M2 raw/split adjusted, dividends separate. M5 conflicts with native availability proof. | D2/D3 document actions, changed records and rescissions. Open | Preserve ordinary/special distributions, splits, original event terms, revisions and availability. Compute both trend and passive returns with the same approved reinvestment method and consistent raw basis. |
| Publication, receipt and corrections | A2 interval labels and A4 quote timestamp do not establish consumer receipt. A5 replay depth open. | M5/M6 distinguish current revisions and archive file delivery. Public REST does not prove original snapshots. | D5 capture timestamps distinct from local receipt. Version retention open. | Independently verify original publication, provider capture, approved local availability and corrections known at each decision. Later acquisition time or a backfilled hash cannot stand in for historical local receipt. |
| Execution and holding horizon | A4 quote sides, sizes and venues documented. Open | M1 one-level NBBO. Open | D4 composite and anonymized size conflict with SIP/venue equivalence. | Confirm quote eligibility, size, timestamp, halt and staleness handling and executable timing for entry, exit and benchmark. Require 21-session labels; conservative no-fill when quotes or executable size are missing. |
| Licensing, retention and independent reviewer | A6 separate agreements. Open | M4 Business lead. Individual terms conflict with commercial use. | D2 published internal scope and redistribution restriction; D7 scope categories. Open | Product-specific signed/versioned agreement, commercial non-display, derived/benchmark rights, raw/derived retention, reviewer environment and permitted reports. |
| Binding costs and caps | Open | Open | Open | Verified scoped historical quotes, fees, caps, first-year commitments and expiry. Refuse unknown line items or cap violations. |

IDs refer to the [product evidence register](PRODUCT-AND-RIGHTS-EVIDENCE.md).
Treat M7 coverage as an independently verified continuity claim. Neither a
calendar envelope nor boundary bars prove every interior bar, action, revision
or quote exists. Document a separate control for each gate and validate evidence
before any empirical authorization. No M7 changes are required for this preflight.
