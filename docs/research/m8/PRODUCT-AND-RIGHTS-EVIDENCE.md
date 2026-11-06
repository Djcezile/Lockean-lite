# M8 product and rights evidence register

Public documentation accessed **2026-11-06, America/New_York**. Access dates
apply to each row. Confidence is about the stated documentation claim.
Official specifications establish documented fields or terms, and vendor
product claims describe advertised coverage. Entitlement, exact archive
completeness, original availability and quoted cost need separate proof.

| ID | Product and public source | Verified documentation claim | Confidence and open question |
|---|---|---|---|
| A1 | Alpaca Basic and Algo Trader Plus. [Plan overview](https://docs.alpaca.markets/us/docs/about-market-data-api) | US stocks/ETFs, historical timeframe since 2016. Basic free and Plus USD 99/month on the Trading API plan table. | High for public offer. Exact business license, historical depth by endpoint and any fees unknown. |
| A2 | Alpaca SIP/IEX. [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) | SIP differs from single-venue IEX. FAQ describes the historical SIP recency rule and left-edge bar labels. | High for documented semantics. Confirm publication/finalization, archives, corrections and receipt. |
| A3 | Alpaca Historical Stock Bars. [Bars specification](https://docs.alpaca.markets/us/reference/stockbars) | Raw and adjusted variants and `asof` symbol resolution are documented. | High for fields. Verify listing history, adjustment vintage and regular-session aggregation. |
| A4 | Alpaca Historical Quotes. [Quotes specification](https://docs.alpaca.markets/us/reference/stockquotes-1) | Historical quote sides, sizes, venues, timestamp and pagination. | High for fields. Verify timestamp source, eligibility, gaps, corrections and clock/custody chain. |
| A5 | Alpaca Corporate Actions SSE. [Corporate-action events](https://docs.alpaca.markets/us/reference/subscribetocorporateactionseventssse) | Documents insert/update/delete events and historical replay cursor behavior. | High for API contract. Archive depth and applicability to full study period unknown. |
| A6 | Alpaca venue terms. [Disclosures and agreements](https://alpaca.markets/disclosures) | Lists separate Nasdaq subscriber and NYSE display agreements. | High for existence. Obtain controlling current commercial/non-display terms and legal review. |
| M1 | Massive Stocks Business. [Historical depth](https://massive.com/knowledge-base/article/how-much-historical-stock-data-does-massive-have) · [SIP and NBBO](https://massive.com/knowledge-base/article/what-are-the-securities-information-processors-sips) | Business documents access to listed archive for bars and tick NBBO, with a 2003-09-10 archive floor. NBBO is one level. | Medium for advertised archive. Exact coverage and source lineage by instrument and schema unknown. |
| M2 | Massive Stocks REST. [Stocks overview](https://massive.com/docs/rest/stocks/overview) · [Adjustment semantics](https://massive.com/knowledge-base/article/is-massives-stock-data-adjusted-for-splits-or-dividends) | Raw and split-adjusted aggregate views, separate distributions. | High for documented distinction. Confirm as-known inputs and delivery versions. |
| M3 | Massive All Tickers and Ticker Overview. [Historical security master guidance](https://massive.com/knowledge-base/article/does-massive-have-a-downloadable-security-master) | Date-keyed snapshots with inactive securities. List and delist fields can be missing. | High for documented limitations. Authenticate closure, effective dates and exact mappings separately. |
| M4 | Massive Stocks Business. [Business license classification](https://massive.com/knowledge-base/article/what-are-pro-and-non-pro-classifications-for-massives-stock-data) · [Market Data Terms](https://massive.com/legal/market-data-terms-of-service) | Business route carries commercial licensing subject to scope. Individual terms restrict business use and sharing. | High for published distinction. Confirm project agreement and exact non-display, retention, reviewer and benchmark rights. |
| M5 | Massive stock file schedule. [Publication and action FAQ](https://massive.com/knowledge-base/article/what-time-are-massives-flat-files-ready-each-day) | File delivery and REST availability differ. Splits and dividends lack a record-addition timestamp in the documented endpoints. | High for the stated limitation. Require an alternative historical custody source. |
| M6 | Massive aggregate behavior. [Corrections FAQ](https://massive.com/knowledge-base/article/why-is-massives-market-data-different-from-other-providers) | Late corrections can change an earlier stored bar relative to a current REST result. | High for documented caveat. Prior revisions and historical availability remain unknown. |
| M7 | Massive pricing. [Individual](https://massive.com/pricing?product=stocks) · [Business](https://massive.com/business) | Individual Stocks Advanced USD 199/month. Business Full Market Delayed and Full Market expansions list USD 499 and USD 1,999/month respectively. | High for displayed prices. Commercial historical-only base price, mandatory expansions, fees and minimum term unknown. |
| D1 | Databento Security Master. [Schema](https://databento.com/docs/schemas/security-master) | Point-in-time and latest listed/delisted security data with `ts_record`. | High for fields. Confirm vintage range, completeness and exchange-listing key. |
| D2 | Databento Corporate Actions. [Schema](https://databento.com/docs/schemas/corporate-actions) · [Product and usage](https://databento.com/corporate-actions) | Identifies actions, record change time and ex-date. Product describes internal display/non-display and bars external file/API redistribution. | High for published scope. Exact contract, ETF special distributions and reviewer rights unknown. |
| D3 | Databento Adjustment Factors. [Specification](https://databento.com/docs/datasets/adjustment-factors) | Multiple revisions and rescissions may occur around ex-date. | High for schema behavior. Verify archive snapshots and available publication/receipt evidence. |
| D4 | Databento US Equities Mini. [Feed specification](https://databento.com/docs/datasets/equs-mini) | Component composite, OHLCV-1d and MBP-1 among schemas, anonymized venues and aggregated odd lots. | High for composition. Exact date range and feasible trade/size representation unknown. |
| D5 | Databento timestamps. [Timestamping guide](https://databento.com/docs/architecture/timestamping-guide) | Distinguishes market event fields and capture receive time, with upstream precision limitations. | High for semantics. Capture is different from historical local receipt. |
| D6 | Databento acquisition. [Data catalogue](https://databento.com/docs/portal/data-catalog) · [Usage pricing](https://databento.com/docs/faqs/usage-pricing-and-data-credits) | Catalogue lists history/schema/license metadata and estimates. Historical usage pricing is described in byte terms. | High for published method. Exact volume, rate and applicable price unknown. |
| D7 | Databento licenses. [Live data guide](https://databento.com/docs/portal/live-data) | Display, non-display and redistribution are separate categories with venue-specific rules. | High for distinctions. Obtain the historical product terms and fees for exact use. |

## Required written grant

For each source and downstream join, capture rights issuer, product and schema,
agreement version, named entity/environments, effective dates and fee schedule.
Confirm commercial internal research and automated non-display, derived
total-return/benchmark and feature creation, raw and derived retention
including backup and termination, named independent reviewer access,
external reports and redistribution restrictions. Keep proof separately from
the submitted data. Public access, account tiers, product logos and hashes do
not establish scope. Draft questions are in the [decision record](ACQUISITION-DECISION-RECORD.md).
