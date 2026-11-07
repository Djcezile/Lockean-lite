# M8 continuity handoff

2026-11-06, America/New_York. Pinned baseline
`b0fd722d6316c7dd4250d282007c0ea2fdd90eb9`. Review branch
`research/001-m8-data-provider-qualification`. Review should bind to the exact
draft PR head. Acquisition status is **BLOCKED**.

## Deliverables

- [Provider comparison](PROVIDER-COMPARISON.md)
- [Product and rights evidence](PRODUCT-AND-RIGHTS-EVIDENCE.md)
- [ETF eligibility matrix](ETF-DATA-ELIGIBILITY-MATRIX.md)
- [Acquisition cost scenarios](ACQUISITION-COST-SCENARIOS.md)
- [Proposed study dates](PROPOSED-RESEARCH-DATES.md)
- [Earnings preflight](EARNINGS-DATA-PREFLIGHT.md)
- [Decision record and unsent vendor inquiry](ACQUISITION-DECISION-RECORD.md)
- This handoff

## Review and next action

M8 used public documentation, calendar metadata/rules, and generated synthetic
witnesses. It left M0–M7 and operational paths outside the change scope.
The merged M7 holdout and full-fold contract govern the proposed envelope.
M8 ran the 121-test M5/M7 synthetic suites and an offline calendar-plus-M7
check that verified 52 synthetic decision witnesses, successful synthetic
eligibility, missing rights/cost refusal and a blocked short holding horizon.
A first integration attempt exposed pandas UTC versus the M7 exact UTC type
requirement. The external planning harness normalized the timestamp type.
The production contract and inputs to prior canonical fixtures were preserved.
The separate evidence ledger records commands, exit codes, and hashes.

Independent review should verify the source-to-claim mappings, product and
legal scope distinctions, calendar calculations, full-fold and embargo checks,
and cost unknowns. Prioritize Alpaca SIP historical bars/quotes and a Databento
reference sidecar for written diligence. Massive Stocks Business is the
alternative. Founder approval is needed before sending inquiries, committing
funds, granting access or acquiring anything. Earnings remains deferred.
