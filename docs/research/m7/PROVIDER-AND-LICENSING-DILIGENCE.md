# M7 provider and licensing decision package

Public documentation accessed 2026-11-06, America/New_York. These are product
leads and written diligence requirements. No account, quote, entitlement,
sample feed or market dataset was accessed.

| Candidate | Product lead and documented capability | Required written confirmation |
|---|---|---|
| ETF trend | Databento catalogue lists datasets, schemas, coverage, license and pricing metadata. Its timestamp guide distinguishes event time from capture receipt. [Catalogue](https://databento.com/docs/portal/data-catalog) · [Timestamping](https://databento.com/docs/architecture/timestamping-guide) | Exact eligible ETF identities, historic active/delisted coverage, as-known distributions/splits, executable quote sides/sizes and venues, correction history and separate local-availability evidence. |
| ETF trend | Databento Corporate Actions advertises point-in-time updates. Its product page describes internal use and excludes external redistribution by file/API. [Corporate Actions](https://databento.com/corporate-actions) | Exact governing terms and version, retained as-known data, historical coverage, derived-feature rights and reviewer access. General product language cannot resolve project-specific rights. |
| Earnings drift | LSEG I/B/E/S Actuals describes comparable and restated actuals plus announcement and activation fields. The quant brochure describes Point-in-Time daily snapshots. [Actuals](https://www.lseg.com/en/data-catalogue/company-data/ibes-estimates/actuals) · [Quant research brochure](https://www.lseg.com/content/dam/data-analytics/en_us/documents/brochures/data-for-quant-research.pdf) | Exact as-issued comparable EPS, snapshot effective/receipt timestamps, prior consensus ordering and revisions, fiscal basis/currency, historical securities and rights. Daily snapshots cannot establish intraday pre-release availability by themselves. |
| Earnings drift | SEC EDGAR documentation distinguishes filing acceptance from website availability and describes variable dissemination delay. [SEC timing FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) | An original issuer release and evidenced delivery timestamps. Do not treat acceptance or filing date as first publication or historical local receipt. Verify applicable reuse terms and third-party materials separately. |
| Both | Databento documents historical byte-based pricing and distinct live non-display/distribution licensing categories. [Usage pricing](https://databento.com/docs/faqs/usage-pricing-and-data-credits) · [Licensing guide](https://databento.com/docs/portal/live-data) | Binding estimate for exact historical products and dates. Itemize exchange, quote, correction, identifier, venue, reviewer, renewal and cloud charges. Verify restrictions for the intended entity and environments. |

| Rights gate | Current decision | Evidence required |
|---|---|---|
| Internal research and non-display | UNKNOWN | Product, rights issuer, entity and environments, agreement version and effective period. |
| Commercial research and model development | UNKNOWN | Express scope for commercial research, derived features, models and any licensed third-party content. |
| Raw and derived retention | UNKNOWN | Separate retention limits, backup locations, deletion, termination and portability terms. |
| Independent reviewer and external reporting | UNKNOWN | Named reviewer or role, access method and audit/disclosure rights. External distribution needs separate express scope. |
| Live, operational or broker use | Outside this milestone | Separate Founder authorization and applicable rights. |

Founder decision is to approve whether to request written terms and quotes for
the exact trend products, with the conditional earnings package separately
gated. Product rights, local historical receipt, price and contract acceptance
remain unresolved. No commercial or timestamp assumption substitutes for an
independently verified entitlement or custody record.
