"""Value sets used by the tables. Stored as strings so new values need no migration."""

from enum import StrEnum

# --- Market layer ---------------------------------------------------------------------


class ShariahStatus(StrEnum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNDER_REVIEW = "UNDER_REVIEW"  # FR1.1


class PeriodType(StrEnum):
    ANNUAL = "ANNUAL"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"


class EventType(StrEnum):
    WAR = "WAR"
    ENERGY = "ENERGY"
    POLITICAL = "POLITICAL"
    POLICY = "POLICY"
    OTHER = "OTHER"  # FR5.1


class SubjectType(StrEnum):
    TICKER = "TICKER"
    SECTOR = "SECTOR"
    INDEX = "INDEX"  # the market as a whole, for event metrics (F5)


class ScoreType(StrEnum):
    RATE_SENSITIVITY = "RATE_SENSITIVITY"  # with the market term (FR3.1)
    RATE_SENSITIVITY_NO_MARKET = "RATE_SENSITIVITY_NO_MARKET"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"  # fewer than the minimum valid weeks (FR3.2)


class NoteStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class BankStatus(StrEnum):
    NORMAL = "NORMAL"
    RESTRUCTURING = "RESTRUCTURING"  # under Bangladesh Bank restructuring (FR26.5)
    RESTRICTED = "RESTRICTED"  # withdrawal limits in force


# --- Personal finance -----------------------------------------------------------------


class HouseholdRole(StrEnum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"  # FR24.2


class AccountType(StrEnum):
    BO = "BO"  # DSE beneficiary owner account
    MUTUAL_FUND = "MUTUAL_FUND"
    SAVINGS_CERTIFICATE = "SAVINGS_CERTIFICATE"  # sanchayapatra
    FDR = "FDR"
    DPS = "DPS"
    PROVIDENT_FUND = "PROVIDENT_FUND"
    CASH = "CASH"
    ISLAMIC_BANK = "ISLAMIC_BANK"
    SUKUK = "SUKUK"
    FOREIGN_BROKERAGE = "FOREIGN_BROKERAGE"
    OTHER = "OTHER"  # FR14.1, FR14.5


class InstrumentType(StrEnum):
    DSE_SHARE = "DSE_SHARE"
    MUTUAL_FUND_UNIT = "MUTUAL_FUND_UNIT"
    SUKUK = "SUKUK"
    ISLAMIC_DEPOSIT = "ISLAMIC_DEPOSIT"
    SAVINGS_CERTIFICATE = "SAVINGS_CERTIFICATE"
    FDR = "FDR"
    DPS = "DPS"
    PROVIDENT_FUND = "PROVIDENT_FUND"
    CASH = "CASH"
    BANK_BALANCE = "BANK_BALANCE"
    FOREIGN_SECURITY = "FOREIGN_SECURITY"
    OTHER = "OTHER"


class TransactionType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    DIVIDEND = "DIVIDEND"
    PROFIT = "PROFIT"
    BONUS = "BONUS"
    FEE = "FEE"
    TAX = "TAX"


class AltAssetType(StrEnum):
    LAND = "LAND"
    FLAT = "FLAT"
    PLOT = "PLOT"
    RENTAL_PROPERTY = "RENTAL_PROPERTY"
    GOLD = "GOLD"
    SILVER = "SILVER"
    BUSINESS_STAKE = "BUSINESS_STAKE"
    PARTNERSHIP = "PARTNERSHIP"
    AGRICULTURE = "AGRICULTURE"
    PRIVATE_LOAN = "PRIVATE_LOAN"
    PRIVATE_EQUITY = "PRIVATE_EQUITY"
    COLLECTIBLE = "COLLECTIBLE"
    FAMILY_HOME = "FAMILY_HOME"
    PERSONAL_CAR = "PERSONAL_CAR"
    OTHER = "OTHER"  # F25


class Liquidity(StrEnum):
    UNDER_1_MONTH = "<1M"
    UNDER_1_YEAR = "<1Y"
    OVER_1_YEAR = ">1Y"  # FR25.1


class ShariahFlag(StrEnum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNKNOWN = "UNKNOWN"


class AssetKind(StrEnum):
    """What an owner share or a valuation points at."""

    HOLDING = "HOLDING"
    ALT_ASSET = "ALT_ASSET"
    LIABILITY = "LIABILITY"


class ValuationMethod(StrEnum):
    MANUAL = "MANUAL"
    MARKET_PRICE = "MARKET_PRICE"
    METAL_PRICE = "METAL_PRICE"  # gold and silver by weight and purity (FR25.2)


class CashFlowType(StrEnum):
    RENT = "RENT"
    PROFIT_SHARE = "PROFIT_SHARE"
    INSTALMENT = "INSTALMENT"
    CAPITAL_ADDED = "CAPITAL_ADDED"
    SALE_PROCEEDS = "SALE_PROCEEDS"
    OTHER = "OTHER"  # FR25.3


class LiabilityType(StrEnum):
    HOME_LOAN = "HOME_LOAN"
    PERSONAL_LOAN = "PERSONAL_LOAN"
    CREDIT_CARD = "CREDIT_CARD"
    PRIVATE_DEBT = "PRIVATE_DEBT"
    OTHER = "OTHER"


class Frequency(StrEnum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    HALF_YEARLY = "HALF_YEARLY"
    YEARLY = "YEARLY"
    AT_MATURITY = "AT_MATURITY"


class NisabBasis(StrEnum):
    GOLD = "GOLD"
    SILVER = "SILVER"  # FR13.2


class GoalType(StrEnum):
    NET_WORTH = "NET_WORTH"
    INVESTED_AMOUNT = "INVESTED_AMOUNT"
    FIRE_AGE = "FIRE_AGE"  # FR19.1
    MONTHLY_SAVINGS = "MONTHLY_SAVINGS"  # FR27.4: average saved a month, last 12 months


class AlertType(StrEnum):
    SHARIAH_STATUS = "SHARIAH_STATUS"  # FR7.1
    REGIME_CHANGE = "REGIME_CHANGE"
    SHOCK_EVENT = "SHOCK_EVENT"  # FR7.2
    ALLOCATION_DRIFT = "ALLOCATION_DRIFT"
    VOLATILITY = "VOLATILITY"
    GOAL_REACHED = "GOAL_REACHED"
    MATURITY_DUE = "MATURITY_DUE"
    REVALUATION_DUE = "REVALUATION_DUE"
    HAWL_APPROACHING = "HAWL_APPROACHING"  # FR20.1
    MONTHLY_REPORT = "MONTHLY_REPORT"  # FR20.2


class Channel(StrEnum):
    EMAIL = "EMAIL"
    PUSH = "PUSH"
    BOTH = "BOTH"
    APP = "APP"  # in the app only: no email, no push (D34)


class AlertFrequency(StrEnum):
    INSTANT = "INSTANT"
    DAILY_DIGEST = "DAILY_DIGEST"  # FR7.3


class FirmRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"  # FR9.3


class Plan(StrEnum):
    FREE = "FREE"
    PRO = "PRO"
    FIRM = "FIRM"


class SubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
