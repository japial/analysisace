"""Back-adjustment of closing prices for bonus shares, rights and splits (PRD 7.2).

A price before an ex-date is multiplied by that action's factor, so the adjusted series has
no jump caused by the action itself. Cash dividends do not adjust prices.

Factors, where C is the last close before the ex-date:
- SPLIT with ratio r (new shares per old share): 1 / r
- BONUS with ratio b (bonus shares per share held): 1 / (1 + b)
- RIGHTS with ratio q (rights shares per share held) at issue price P:
  (C + q * P) / ((1 + q) * C), the theoretical ex-rights price divided by C
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.market import CorporateActionType

_PRICE_QUANTUM = Decimal("0.0001")
_ONE = Decimal(1)


@dataclass(frozen=True)
class Action:
    ex_date: date
    type: CorporateActionType
    ratio: Decimal | None = None
    amount: Decimal | None = None


def adjustment_factor(action: Action, prev_close: Decimal) -> Decimal:
    """Multiplier applied to every price before `action.ex_date`."""
    if action.type is CorporateActionType.CASH_DIVIDEND:
        return _ONE
    if action.ratio is None or action.ratio <= 0:
        raise ValueError(f"{action.type} on {action.ex_date} needs a positive ratio")
    if action.type is CorporateActionType.SPLIT:
        return _ONE / action.ratio
    if action.type is CorporateActionType.BONUS:
        return _ONE / (_ONE + action.ratio)
    if action.type is CorporateActionType.RIGHTS:
        if action.amount is None or action.amount < 0:
            raise ValueError(f"RIGHTS on {action.ex_date} needs an issue price in `amount`")
        if prev_close <= 0:
            raise ValueError(f"RIGHTS on {action.ex_date} needs a positive prior close")
        return (prev_close + action.ratio * action.amount) / ((_ONE + action.ratio) * prev_close)
    raise ValueError(f"Unknown corporate action type: {action.type}")


def back_adjust(
    closes: Sequence[tuple[date, Decimal]], actions: Sequence[Action]
) -> list[tuple[date, Decimal]]:
    """Return (date, adjusted close) in ascending date order.

    `closes` holds one ticker's raw closes with unique dates, in any order. An action whose
    ex-date is on or before the first price has no earlier price to adjust and is ignored.
    An action whose ex-date is after the newest price has not happened yet and is ignored.
    """
    ordered = sorted(closes)
    dates = [d for d, _ in ordered]
    if len(set(dates)) != len(dates):
        raise ValueError("closes contains duplicate dates")
    if not ordered:
        return []

    newest = dates[-1]
    pending = sorted((a for a in actions if a.ex_date <= newest), key=lambda a: a.ex_date)
    adjusted: list[tuple[date, Decimal]] = []
    cumulative = _ONE
    # Walk from the newest price to the oldest, applying each action as its ex-date is passed.
    for index in range(len(ordered) - 1, -1, -1):
        day, close = ordered[index]
        while pending and pending[-1].ex_date > day:
            # `close` is the last close before this ex-date.
            cumulative *= adjustment_factor(pending.pop(), close)
        adjusted.append((day, (close * cumulative).quantize(_PRICE_QUANTUM)))
    adjusted.reverse()
    return adjusted
