from html import escape

from lockean_lite.autonomous_cycle import (
    AutonomousTradeCycleResult,
)


def _value(
    value,
) -> str:
    return escape(
        str(value)
    )


def render_execution_result_html(
    result: AutonomousTradeCycleResult,
) -> str:
    proof = (
        result.execution_proof
    )

    if proof is None:
        proof_content = """
            <div class="empty-proof">
                NO EXECUTION PROOF
            </div>
        """
    else:
        proof_content = f"""
            <div class="proof-row">
                <span>Proposal ID</span>
                <strong>
                    {_value(proof.proposal_id)}
                </strong>
            </div>

            <div class="proof-row">
                <span>Proposal Fingerprint</span>
                <strong class="mono">
                    {_value(proof.proposal_fingerprint)}
                </strong>
            </div>

            <div class="proof-row">
                <span>Authorization Receipt ID</span>
                <strong>
                    {_value(proof.authorization_receipt_id)}
                </strong>
            </div>

            <div class="proof-row">
                <span>
                    Execution Authority Verification
                </span>
                <strong>
                    {_value(proof.authorization_verification)}
                </strong>
            </div>

            <div class="proof-row">
                <span>Alpaca Broker Order ID</span>
                <strong>
                    {_value(proof.broker_order_id)}
                </strong>
            </div>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Lockean Execution Result</title>

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
            width: min(900px, 100%);
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

        .card {{
            background: #111820;
            border: 1px solid #26313d;
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 18px;
        }}

        .section-label {{
            margin: 0 0 16px;
            color: #8d9baa;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .status {{
            margin: 0;
            font-size: 36px;
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

        .proof-row {{
            display: flex;
            justify-content: space-between;
            gap: 24px;
            padding: 13px 0;
            border-bottom: 1px solid #202a34;
        }}

        .proof-row:last-child {{
            border-bottom: 0;
        }}

        .proof-row span {{
            color: #b7c0ca;
        }}

        .proof-row strong {{
            text-align: right;
            overflow-wrap: anywhere;
        }}

        .mono {{
            font-family:
                ui-monospace,
                SFMono-Regular,
                Consolas,
                monospace;
        }}

        .empty-proof {{
            padding: 18px 0;
            color: #9aa7b5;
            font-weight: 700;
            letter-spacing: 0.05em;
        }}

        @media (max-width: 700px) {{
            body {{
                padding: 24px 16px;
            }}

            .proof-row {{
                flex-direction: column;
                gap: 6px;
            }}

            .proof-row strong {{
                text-align: left;
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
            <p>Execution Result</p>
        </header>

        <article class="card">
            <p class="section-label">
                Lockean Result
            </p>

            <h2 class="status">
                {_value(result.status)}
            </h2>

            <div class="reason">
                {_value(result.reason)}
            </div>
        </article>

        <article class="card">
            <p class="section-label">
                Execution Proof
            </p>

            {proof_content}
        </article>
    </main>
</body>
</html>
"""