from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest


COMPETITION_STARTING_EQUITY = Decimal("100000.00")


@dataclass(frozen=True)
class PaperPositionSnapshot:
    symbol: str
    asset_class: str
    qty: Decimal
    market_value: Decimal
    cost_basis: Decimal
    current_price: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal


@dataclass(frozen=True)
class PaperPortfolioSnapshot:
    status: str
    currency: str
    trading_blocked: bool
    cash: Decimal
    equity: Decimal
    last_equity: Decimal
    buying_power: Decimal
    options_buying_power: Decimal
    portfolio_value: Decimal
    starting_equity: Decimal
    total_pl: Decimal
    day_pl: Decimal
    unrealized_pl: Decimal
    positions: tuple[PaperPositionSnapshot, ...]
    option_contract_units: Decimal
    managed_spreads: int
    pending_spread_units: int = 0


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _enum_text(value) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _is_option_asset_class(asset_class: str) -> bool:
    return "option" in asset_class.lower()


def _pending_mleg_units(open_orders) -> int:
    units = Decimal("0")

    for order in open_orders:
        order_class = _enum_text(
            getattr(order, "order_class", "")
        ).lower()

        if order_class != "mleg":
            continue

        qty = abs(
            _decimal(getattr(order, "qty", 0))
        )
        filled_qty = abs(
            _decimal(getattr(order, "filled_qty", 0))
        )
        remaining = max(
            qty - filled_qty,
            Decimal("0"),
        )
        units += remaining

    return int(
        units.to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def create_paper_portfolio_snapshot(
    *,
    account,
    positions,
    open_orders=(),
    starting_equity: Decimal = COMPETITION_STARTING_EQUITY,
) -> PaperPortfolioSnapshot:
    position_snapshots = tuple(
        PaperPositionSnapshot(
            symbol=str(position.symbol),
            asset_class=_enum_text(
                getattr(position, "asset_class", "")
            ),
            qty=_decimal(getattr(position, "qty", 0)),
            market_value=_decimal(
                getattr(position, "market_value", 0)
            ),
            cost_basis=_decimal(
                getattr(position, "cost_basis", 0)
            ),
            current_price=_decimal(
                getattr(position, "current_price", 0)
            ),
            unrealized_pl=_decimal(
                getattr(position, "unrealized_pl", 0)
            ),
            unrealized_plpc=_decimal(
                getattr(position, "unrealized_plpc", 0)
            ),
        )
        for position in positions
    )

    option_contract_units = sum(
        (
            abs(position.qty)
            for position in position_snapshots
            if _is_option_asset_class(
                position.asset_class
            )
        ),
        start=Decimal("0"),
    )

    managed_spreads = int(
        (
            option_contract_units
            / Decimal("2")
        ).to_integral_value(
            rounding=ROUND_CEILING
        )
    )

    pending_spread_units = (
        _pending_mleg_units(open_orders)
    )

    equity = _decimal(
        getattr(account, "equity", 0)
    )
    last_equity = _decimal(
        getattr(account, "last_equity", 0)
    )

    unrealized_pl = sum(
        (
            position.unrealized_pl
            for position in position_snapshots
        ),
        start=Decimal("0"),
    )

    return PaperPortfolioSnapshot(
        status=_enum_text(
            getattr(account, "status", "")
        ),
        currency=str(
            getattr(account, "currency", "USD")
        ),
        trading_blocked=bool(
            getattr(account, "trading_blocked", False)
        ),
        cash=_decimal(
            getattr(account, "cash", 0)
        ),
        equity=equity,
        last_equity=last_equity,
        buying_power=_decimal(
            getattr(account, "buying_power", 0)
        ),
        options_buying_power=_decimal(
            getattr(account, "options_buying_power", 0)
        ),
        portfolio_value=_decimal(
            getattr(
                account,
                "portfolio_value",
                equity,
            )
        ),
        starting_equity=starting_equity,
        total_pl=equity - starting_equity,
        day_pl=equity - last_equity,
        unrealized_pl=unrealized_pl,
        positions=position_snapshots,
        option_contract_units=(
            option_contract_units
        ),
        managed_spreads=managed_spreads,
        pending_spread_units=(
            pending_spread_units
        ),
    )


def read_live_paper_portfolio_snapshot(
    *,
    trading_client,
    starting_equity: Decimal = COMPETITION_STARTING_EQUITY,
) -> PaperPortfolioSnapshot:
    account = trading_client.get_account()
    positions = trading_client.get_all_positions()
    open_orders = trading_client.get_orders(
        filter=GetOrdersRequest(
            status=QueryOrderStatus.OPEN,
            limit=100,
            nested=True,
        )
    )

    return create_paper_portfolio_snapshot(
        account=account,
        positions=positions,
        open_orders=open_orders,
        starting_equity=starting_equity,
    )


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def render_paper_portfolio_snapshot(
    snapshot: PaperPortfolioSnapshot,
) -> str:
    committed_spreads = (
        snapshot.managed_spreads
        + snapshot.pending_spread_units
    )

    lines = [
        "LOCKEAN ALPACA PAPER TELEMETRY",
        "==============================",
        f"ACCOUNT STATUS: {snapshot.status}",
        f"STARTING EQUITY: {_money(snapshot.starting_equity)}",
        f"CURRENT EQUITY:  {_money(snapshot.equity)}",
        f"TOTAL P&L:       {_money(snapshot.total_pl)}",
        f"DAY P&L:         {_money(snapshot.day_pl)}",
        f"UNREALIZED P&L:  {_money(snapshot.unrealized_pl)}",
        f"CASH:            {_money(snapshot.cash)}",
        f"BUYING POWER:    {_money(snapshot.buying_power)}",
        (
            "OPTIONS BUYING POWER: "
            f"{_money(snapshot.options_buying_power)}"
        ),
        f"OPEN POSITIONS: {len(snapshot.positions)}",
        (
            "MANAGED SPREAD UNITS: "
            f"{snapshot.managed_spreads}"
        ),
        (
            "PENDING SPREAD UNITS: "
            f"{snapshot.pending_spread_units}"
        ),
        (
            "COMMITTED SPREAD UNITS: "
            f"{committed_spreads}"
        ),
    ]

    if snapshot.positions:
        lines.extend(
            [
                "",
                "OPEN ALPACA POSITIONS:",
            ]
        )

        for position in snapshot.positions:
            lines.append(
                " | ".join(
                    [
                        position.symbol,
                        f"qty={position.qty}",
                        (
                            "value="
                            f"{_money(position.market_value)}"
                        ),
                        (
                            "uP&L="
                            f"{_money(position.unrealized_pl)}"
                        ),
                    ]
                )
            )

    return "\n".join(lines)
