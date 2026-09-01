from html import escape

from lockean_lite.decision_report import (
    MarketDecisionReport,
)


def _condition_row(
    *,
    label: str,
    passed: bool,
) -> str:
    result = (
        "PASS"
        if passed
        else "FAIL"
    )

    status_class = (
        "pass"
        if passed
        else "fail"
    )

    return (
        '<div class="condition-row">'
        f"<span>{escape(label)}</span>"
        f'<strong class="{status_class}">'
        f"{result}"
        "</strong>"
        "</div>"
    )


def _downstream_value(
    *,
    reached: bool,
    reached_text: str,
    blocked_text: str,
) -> str:
    return (
        reached_text
        if reached
        else blocked_text
    )


def render_market_decision_html(
    report: MarketDecisionReport,
) -> str:
    decision_class = (
        "rejected"
        if report.status == "REJECTED"
        else "eligible"
    )

    ai_status = _downstream_value(
        reached=report.ai_recommendation_reached,
        reached_text="REACHED",
        blocked_text="NOT REACHED",
    )

    authority_status = _downstream_value(
        reached=report.authority_reached,
        reached_text="REACHED",
        blocked_text="NOT REACHED",
    )

    receipt_status = _downstream_value(
        reached=report.receipt_issued,
        reached_text="ISSUED",
        blocked_text="NOT ISSUED",
    )

    broker_status = _downstream_value(
        reached=report.broker_order_submitted,
        reached_text="ORDER SUBMITTED",
        blocked_text="NO ORDER",
    )

    conditions = "".join(
        (
            _condition_row(
                label="Trend",
                passed=report.trend_passed,
            ),
            _condition_row(
                label="Momentum",
                passed=report.momentum_passed,
            ),
            _condition_row(
                label="Breakout",
                passed=report.breakout_passed,
            ),
            _condition_row(
                label="Volatility",
                passed=report.volatility_passed,
            ),
        )
    )

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Lockean Decision Report</title>
    <style>
        :root {{
            color-scheme: dark;
            font-family:
                Inter,
                ui-sans-serif,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            min-height: 100vh;
            background: #090d12;
            color: #f5f7fa;
            display: flex;
            justify-content: center;
            padding: 48px 24px;
        }}

        .dashboard {{
            width: min(960px, 100%);
        }}

        .brand {{
            margin-bottom: 32px;
        }}

        .brand h1 {{
            margin: 0;
            font-size: 42px;
            letter-spacing: 0.08em;
        }}

        .brand p {{
            margin: 6px 0 0;
            color: #9aa7b5;
            font-size: 18px;
        }}

        .grid {{
            display: grid;
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
            gap: 18px;
        }}

        .card {{
            background: #111820;
            border: 1px solid #26313d;
            border-radius: 14px;
            padding: 22px;
        }}

        .wide {{
            grid-column: 1 / -1;
        }}

        .section-label {{
            margin: 0 0 16px;
            color: #8d9baa;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .market-value {{
            font-size: 30px;
            font-weight: 700;
        }}

        .source {{
            margin-top: 6px;
            color: #9aa7b5;
        }}

        .condition-row,
        .downstream-row {{
            display: flex;
            justify-content: space-between;
            gap: 20px;
            padding: 11px 0;
            border-bottom: 1px solid #202a34;
        }}

        .condition-row:last-child,
        .downstream-row:last-child {{
            border-bottom: 0;
        }}

        .pass {{
            color: #67d391;
        }}

        .fail {{
            color: #ff7474;
        }}

        .decision {{
            border-width: 2px;
        }}

        .decision.rejected {{
            border-color: #a94a4a;
        }}

        .decision.eligible {{
            border-color: #438d62;
        }}

        .decision-status {{
            margin: 0;
            font-size: 34px;
        }}

        .reason {{
            margin-top: 10px;
            color: #c4ccd5;
            font-family:
                ui-monospace,
                SFMono-Regular,
                Consolas,
                monospace;
        }}

        .as-of {{
            color: #7f8c99;
            font-size: 13px;
            margin-top: 18px;
        }}

        @media (max-width: 700px) {{
            body {{
                padding: 24px 16px;
            }}

            .grid {{
                grid-template-columns: 1fr;
            }}

            .wide {{
                grid-column: auto;
            }}

            .brand h1 {{
                font-size: 34px;
            }}
        }}
    </style>
</head>

<body>
    <main class="dashboard">
        <header class="brand">
            <h1>LOCKEAN</h1>
            <p>Independent AI Trade Authority</p>
        </header>

        <section class="grid">
            <article class="card">
                <p class="section-label">
                    Verifiable Market Evidence
                </p>

                <div class="market-value">
                    SPY {escape(str(report.spy_close))}
                </div>

                <div class="source">
                    Alpaca
                </div>
            </article>

            <article class="card">
                <p class="section-label">
                    Verifiable Market Evidence
                </p>

                <div class="market-value">
                    VIX {escape(str(report.vix_close))}
                </div>

                <div class="source">
                    Cboe
                </div>
            </article>

            <article class="card">
                <p class="section-label">
                    Deterministic Entry Policy
                </p>

                {conditions}
            </article>

            <article
                class="card decision {decision_class}"
            >
                <p class="section-label">
                    Lockean Decision
                </p>

                <h2 class="decision-status">
                    {escape(report.status)}
                </h2>

                <div class="reason">
                    {escape(report.reason)}
                </div>
            </article>

            <article class="card wide">
                <p class="section-label">
                    Downstream Authority
                </p>

                <div class="downstream-row">
                    <span>AI Recommendation</span>
                    <strong>
                        {ai_status}
                    </strong>
                </div>

                <div class="downstream-row">
                    <span>Authority</span>
                    <strong>
                        {authority_status}
                    </strong>
                </div>

                <div class="downstream-row">
                    <span>Authorization Receipt</span>
                    <strong>
                        {receipt_status}
                    </strong>
                </div>

                <div class="downstream-row">
                    <span>Broker Order</span>
                    <strong>
                        {broker_status}
                    </strong>
                </div>
            </article>
        </section>

        <div class="as-of">
            Evidence as of:
            {escape(report.as_of.isoformat())}
        </div>
    </main>
</body>
</html>
"""