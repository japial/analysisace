"""Zakat calculation (PRD 7.3, FR13.2 to FR13.4, FR13.7).

Pure: every rule arrives as an argument taken from config/zakat.yaml, so nothing here is a
constant. All rules are provisional until the Shariah advisor approves them (Q2).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)

# Flags explain a line to the reader. They are message keys, not verdicts.
FLAG_INTEREST_EXCLUDED = "INTEREST_EXCLUDED"  # profit on an interest-bearing item left out
FLAG_INTEREST_BEARING = "INTEREST_BEARING"  # the person may wish to decide for themselves
FLAG_MARKET_VALUE_FALLBACK = "MARKET_VALUE_FALLBACK"  # zakatable assets unknown
FLAG_NOT_RECOVERABLE = "NOT_RECOVERABLE"
FLAG_NO_RULE = "NO_RULE"  # unknown asset type: counted in full so it is not missed


@dataclass(frozen=True)
class ZakatAsset:
    label: str
    rule: str  # key into `assets` in config/zakat.yaml
    value: Decimal  # current value of the whole asset
    owner_pct: Decimal = HUNDRED  # this person's share
    principal: Decimal | None = None  # amount paid in, for PRINCIPAL treatment
    profit_received: Decimal = Decimal(0)
    is_interest_bearing: bool = False
    is_recoverable: bool = True
    # The company's or business's zakatable assets attributable to this holding.
    zakatable_assets_value: Decimal | None = None
    asset_kind: str | None = None
    asset_id: str | None = None


@dataclass(frozen=True)
class ZakatDebt:
    label: str
    due_within_year: Decimal
    owner_pct: Decimal = HUNDRED
    asset_id: str | None = None


@dataclass(frozen=True)
class ZakatLine:
    label: str
    asset_kind: str | None
    asset_id: str | None
    rule: str
    treatment: str
    value: Decimal
    owner_pct: Decimal
    zakatable: Decimal
    flags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "asset_kind": self.asset_kind,
            "asset_id": self.asset_id,
            "rule": self.rule,
            "treatment": self.treatment,
            "value": str(self.value),
            "owner_pct": str(self.owner_pct),
            "zakatable": str(self.zakatable),
            "flags": list(self.flags),
        }


@dataclass(frozen=True)
class ZakatResult:
    nisab_basis: str
    price_per_gram: Decimal
    nisab_value: Decimal
    shares_method: str
    lines: list[ZakatLine] = field(default_factory=list)
    deductions: list[ZakatLine] = field(default_factory=list)
    total_zakatable: Decimal = Decimal(0)
    total_deductions: Decimal = Decimal(0)
    net_zakatable: Decimal = Decimal(0)
    above_nisab: bool = False
    zakat_due: Decimal = Decimal(0)


def nisab_value(basis: str, price_per_gram: Decimal, nisab: Mapping[str, Any]) -> Decimal:
    """Nisab in taka: 87.48 g of gold or 612.36 g of silver at the given price (FR13.2)."""
    grams = nisab["gold_grams"] if basis == "GOLD" else nisab["silver_grams"]
    return (Decimal(str(grams)) * price_per_gram).quantize(Q2)


def _share(amount: Decimal, owner_pct: Decimal) -> Decimal:
    return (amount * owner_pct / HUNDRED).quantize(Q2)


def _line(asset: ZakatAsset, rules: Mapping[str, Any], shares_method: str) -> ZakatLine:
    rule = rules.get(asset.rule)
    flags: list[str] = []
    if rule is None:
        treatment, base = "FULL", asset.value
        flags.append(FLAG_NO_RULE)
    else:
        treatment = str(rule["treatment"])
        base = Decimal(0)
        if treatment == "FULL":
            base = asset.value
            if rule.get("include_profit_received"):
                base += asset.profit_received
        elif treatment == "PRINCIPAL":
            # Principal only: profit on an interest-bearing item is left out and shown.
            principal = asset.principal if asset.principal is not None else asset.value
            base = min(principal, asset.value) if asset.value > 0 else principal
            if rule.get("flag_interest") and asset.value > principal:
                flags.append(FLAG_INTEREST_EXCLUDED)
        elif treatment == "SHARES_METHOD":
            if shares_method == "ZAKATABLE_ASSETS" and asset.zakatable_assets_value is not None:
                base = asset.zakatable_assets_value
            else:
                base = asset.value
                if shares_method == "ZAKATABLE_ASSETS":
                    flags.append(FLAG_MARKET_VALUE_FALLBACK)
        elif treatment == "BUSINESS_ZAKATABLE_ASSETS":
            if asset.zakatable_assets_value is not None:
                base = asset.zakatable_assets_value
            else:
                base = asset.value
                flags.append(FLAG_MARKET_VALUE_FALLBACK)
        elif treatment == "IF_RECOVERABLE":
            if asset.is_recoverable:
                base = asset.value
            else:
                flags.append(FLAG_NOT_RECOVERABLE)
        elif treatment != "EXEMPT":
            raise ValueError(f"Unknown Zakat treatment {treatment!r} for rule {asset.rule!r}")
    if asset.is_interest_bearing and FLAG_INTEREST_EXCLUDED not in flags:
        flags.append(FLAG_INTEREST_BEARING)
    return ZakatLine(
        label=asset.label,
        asset_kind=asset.asset_kind,
        asset_id=asset.asset_id,
        rule=asset.rule,
        treatment=treatment,
        value=asset.value.quantize(Q2),
        owner_pct=asset.owner_pct,
        zakatable=_share(base, asset.owner_pct),
        flags=tuple(flags),
    )


def compute_zakat(
    assets: Sequence[ZakatAsset],
    debts: Sequence[ZakatDebt],
    *,
    config: Mapping[str, Any],
    nisab_basis: str,
    price_per_gram: Decimal,
    shares_method: str | None = None,
) -> ZakatResult:
    """One person's Zakat: 2.5% of net zakatable wealth when it reaches nisab (FR13.2)."""
    method = shares_method or str(config["shares_method"])
    rules: Mapping[str, Any] = config["assets"]
    lines = [_line(asset, rules, method) for asset in assets]
    deductions = [
        ZakatLine(
            label=debt.label,
            asset_kind="LIABILITY",
            asset_id=debt.asset_id,
            rule="debt_due_within_year",
            treatment="DEDUCT",
            value=debt.due_within_year.quantize(Q2),
            owner_pct=debt.owner_pct,
            zakatable=_share(debt.due_within_year, debt.owner_pct),
        )
        for debt in debts
        if debt.due_within_year > 0
    ]
    total = sum((line.zakatable for line in lines), Decimal(0))
    deducted = sum((line.zakatable for line in deductions), Decimal(0))
    net = max(total - deducted, Decimal(0))
    nisab = nisab_value(nisab_basis, price_per_gram, config["nisab"])
    above = net >= nisab and net > 0
    due = (net * Decimal(str(config["rate_pct"])) / HUNDRED).quantize(Q2) if above else Decimal(0)
    return ZakatResult(
        nisab_basis=nisab_basis,
        price_per_gram=price_per_gram,
        nisab_value=nisab,
        shares_method=method,
        lines=lines,
        deductions=deductions,
        total_zakatable=total,
        total_deductions=deducted,
        net_zakatable=net,
        above_nisab=above,
        zakat_due=due,
    )
