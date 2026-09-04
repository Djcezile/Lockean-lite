from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Streamlit Cloud stores secrets outside the repository. Bridge only the two
# paper-account credentials into the environment expected by Lockean's client
# factory. The client factory itself always creates TradingClient(..., paper=True).
for _name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
    if not os.getenv(_name):
        try:
            if _name in st.secrets:
                os.environ[_name] = str(st.secrets[_name])
        except Exception:
            pass

from alpaca.trading.enums import QueryOrderStatus  # noqa: E402
from alpaca.trading.requests import GetOrdersRequest  # noqa: E402

from lockean_lite.alpaca_client_factory import (  # noqa: E402
    create_paper_trading_client_from_environment,
)
from lockean_lite.paper_portfolio_snapshot import (  # noqa: E402
    COMPETITION_STARTING_EQUITY,
    read_live_paper_portfolio_snapshot,
)

MAX_MANAGED_SPREADS = 5
MAXIMUM_ALLOWED_LOSS = Decimal("150.00")
MAXIMUM_DAILY_LOSS = Decimal("750.00")

st.set_page_config(
    page_title="Lockean Lite | Alpaca Paper Control Room",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

INK = "#f4f8fb"
MUTED = "#91a6b8"
PANEL = "#0f1b27"
PANEL_2 = "#122434"
LINE = "#23445b"
BLUE = "#78b9ff"
CYAN = "#69e1dc"
GREEN = "#74e0a4"
RED = "#ff7b7b"
AMBER = "#ffd36f"
BG = "#071018"

st.markdown(
    f"""
    <style>
      .stApp {{ background: {BG}; color: {INK}; }}
      .block-container {{ max-width: 1280px; padding-top: 1.6rem; padding-bottom: 3rem; }}
      #MainMenu, footer {{ visibility: hidden; }}
      .hero {{
        border: 1px solid {LINE}; border-radius: 16px; padding: 22px 24px;
        background: linear-gradient(135deg, {PANEL_2}, {PANEL}); margin-bottom: 14px;
      }}
      .eyebrow {{ color: {CYAN}; font-size: .72rem; letter-spacing: .12em;
        text-transform: uppercase; font-weight: 700; }}
      .hero h1 {{ margin: .25rem 0 .15rem; font-size: 2rem; line-height: 1.1; color: {INK}; }}
      .hero p {{ margin: .25rem 0 0; color: {MUTED}; font-size: .95rem; }}
      .pill {{ display:inline-flex; align-items:center; gap:7px; border:1px solid {LINE};
        border-radius:999px; padding:5px 11px; font-size:.78rem; font-weight:700; }}
      .dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
      .card {{ background:{PANEL}; border:1px solid {LINE}; border-radius:12px;
        padding:14px 16px; min-height:102px; }}
      .label {{ color:{MUTED}; font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; }}
      .value {{ color:{INK}; font-size:1.7rem; font-weight:700; margin-top:5px; line-height:1.1; }}
      .sub {{ color:{MUTED}; font-size:.76rem; margin-top:6px; }}
      .section {{ color:{MUTED}; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
        font-weight:700; margin:22px 0 8px; }}
      .proof {{ background:{PANEL}; border:1px solid {LINE}; border-radius:12px; padding:13px 15px; }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      div[data-testid="stDataFrame"] {{ border:1px solid {LINE}; border-radius:10px; overflow:hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: Decimal, *, signed: bool = False) -> str:
    amount = Decimal(value)
    sign = "+" if signed and amount > 0 else ""
    return f"{sign}${amount:,.2f}"


def pct(value: Decimal) -> str:
    amount = Decimal(value) * Decimal("100")
    sign = "+" if amount > 0 else ""
    return f"{sign}{amount:.2f}%"


def pnl_colour(value: Decimal) -> str:
    if value > 0:
        return GREEN
    if value < 0:
        return RED
    return INK


def tile(label: str, value: str, sub: str = "", colour: str = INK) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{escape(label)}</div>'
        f'<div class="value" style="color:{colour}">{escape(value)}</div>'
        f'<div class="sub">{escape(sub)}</div>'
        "</div>"
    )


def order_rows(client) -> list[dict[str, str]]:
    try:
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=20,
            nested=True,
        )
        orders = client.get_orders(filter=request)
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    for order in orders:
        created = getattr(order, "created_at", None)
        created_text = (
            created.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            if created is not None
            else "—"
        )
        status = getattr(order, "status", "")
        status_text = getattr(status, "value", str(status))
        order_class = getattr(order, "order_class", "")
        class_text = getattr(order_class, "value", str(order_class))
        filled_avg = getattr(order, "filled_avg_price", None)
        limit_price = getattr(order, "limit_price", None)
        order_id = str(getattr(order, "id", ""))

        rows.append(
            {
                "Time": created_text,
                "Order": order_id[:8] if order_id else "—",
                "Class": class_text or "—",
                "Status": status_text or "—",
                "Qty": str(getattr(order, "qty", "—")),
                "Limit": str(limit_price) if limit_price is not None else "—",
                "Filled Avg": str(filled_avg) if filled_avg is not None else "—",
            }
        )

    return rows


@st.fragment(run_every="15s")
def live_control_room() -> None:
    try:
        client = create_paper_trading_client_from_environment()
        snapshot = read_live_paper_portfolio_snapshot(
            trading_client=client,
            starting_equity=COMPETITION_STARTING_EQUITY,
        )
        clock = client.get_clock()
    except Exception as exc:
        st.error(
            "Unable to read the linked Alpaca paper account. Configure "
            "ALPACA_API_KEY and ALPACA_SECRET_KEY in Streamlit secrets."
        )
        st.caption(f"Read-only telemetry error: {type(exc).__name__}")
        return

    market_colour = GREEN if clock.is_open else AMBER
    market_text = "MARKET OPEN" if clock.is_open else "MARKET CLOSED"

    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">ALPACA PAPER • LIVE READ-ONLY TELEMETRY</div>
          <h1>Lockean Lite Control Room</h1>
          <p>Same Alpaca paper account the autonomous agent trades. This dashboard cannot authorize or submit orders.</p>
          <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
            <span class="pill"><span class="dot" style="background:{market_colour}"></span>{market_text}</span>
            <span class="pill"><span class="dot" style="background:{GREEN}"></span>ACCOUNT {escape(snapshot.status)}</span>
            <span class="pill"><span class="dot" style="background:{CYAN}"></span>AUTO REFRESH 15s</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cards = [
        (
            "Current Equity",
            money(snapshot.equity),
            f"Starting equity {money(snapshot.starting_equity)}",
            INK,
        ),
        (
            "Total P&L",
            money(snapshot.total_pl, signed=True),
            "Directly derived from Alpaca account equity",
            pnl_colour(snapshot.total_pl),
        ),
        (
            "Day P&L",
            money(snapshot.day_pl, signed=True),
            f"vs. Alpaca last equity {money(snapshot.last_equity)}",
            pnl_colour(snapshot.day_pl),
        ),
        (
            "Unrealized P&L",
            money(snapshot.unrealized_pl, signed=True),
            "Sum of live Alpaca positions",
            pnl_colour(snapshot.unrealized_pl),
        ),
    ]
    for col, card in zip(cols, cards):
        with col:
            st.markdown(tile(*card), unsafe_allow_html=True)

    cols = st.columns(4)
    cards = [
        ("Cash", money(snapshot.cash), "Alpaca paper cash", INK),
        ("Buying Power", money(snapshot.buying_power), "Paper account buying power", INK),
        (
            "Options Buying Power",
            money(snapshot.options_buying_power),
            "Available from Alpaca",
            INK,
        ),
        (
            "Managed Spreads",
            f"{snapshot.managed_spreads} / {MAX_MANAGED_SPREADS}",
            f"{len(snapshot.positions)} open option legs",
            BLUE,
        ),
    ]
    for col, card in zip(cols, cards):
        with col:
            st.markdown(tile(*card), unsafe_allow_html=True)

    st.markdown('<div class="section">OPEN ALPACA POSITIONS</div>', unsafe_allow_html=True)
    if snapshot.positions:
        position_rows = []
        for position in snapshot.positions:
            position_rows.append(
                {
                    "Symbol": position.symbol,
                    "Qty": str(position.qty),
                    "Market Value": money(position.market_value),
                    "Cost Basis": money(position.cost_basis),
                    "Current Price": money(position.current_price),
                    "Unrealized P&L": money(position.unrealized_pl, signed=True),
                    "Return": pct(position.unrealized_plpc),
                }
            )
        st.dataframe(
            position_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No open Alpaca paper positions.")

    st.markdown('<div class="section">RECENT ALPACA BROKER ORDERS</div>', unsafe_allow_html=True)
    rows = order_rows(client)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No recent orders returned by Alpaca.")

    st.markdown('<div class="section">LOCKEAN SESSION CONTROLS</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            tile(
                "Position Cap",
                f"{MAX_MANAGED_SPREADS} spreads",
                "New entries halt at the cap",
                BLUE,
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            tile(
                "Per-Proposal Max Loss",
                money(MAXIMUM_ALLOWED_LOSS),
                "Enforced by Lockean Authority",
                GREEN,
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            tile(
                "Daily Loss Halt",
                "-" + money(MAXIMUM_DAILY_LOSS),
                "Blocks additional entries",
                RED,
            ),
            unsafe_allow_html=True,
        )
    with c4:
        next_event = (
            f"Closes {clock.next_close.astimezone().strftime('%H:%M %Z')}"
            if clock.is_open
            else f"Opens {clock.next_open.astimezone().strftime('%m/%d %H:%M %Z')}"
        )
        st.markdown(
            tile(
                "Alpaca Clock",
                "OPEN" if clock.is_open else "CLOSED",
                next_event,
                market_colour,
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section">SEPARATION OF POWERS</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="proof">
          <span style="color:{BLUE};font-weight:700;">AI Agent</span> — judgment only &nbsp;→&nbsp;
          <span style="color:{GREEN};font-weight:700;">Lockean Authority</span> — authorization only &nbsp;→&nbsp;
          <span style="color:{CYAN};font-weight:700;">Execution Gateway</span> — broker access only &nbsp;→&nbsp;
          <span style="color:#c79cff;font-weight:700;">Alpaca Paper</span>
          <div style="color:{MUTED};font-size:.78rem;margin-top:8px;">
            Dashboard is read-only. It never imports the autonomous loop, mints receipts, or submits orders.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    refreshed = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    st.caption(f"Last Alpaca telemetry refresh: {refreshed}")


live_control_room()
