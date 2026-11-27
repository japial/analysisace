"""Labels used in emails (D31), in English and Bangla.

Copied from frontend/packages/i18n/messages (`market.status`, `market.regime` and
`personal.enum.alertType`) so an email reads like the web page.
`tests/test_email_render.py` fails if the copies drift apart.
"""

EMAIL_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        "shariahStatus": {
            "COMPLIANT": "Shariah compliant",
            "NON_COMPLIANT": "Not compliant",
            "UNDER_REVIEW": "Under review",
        },
        "regimeRate": {
            "EASING": "Easing",
            "TIGHTENING": "Tightening",
            "FLAT": "Rates flat",
            "UNKNOWN": "Rate trend unknown",
        },
        "regimeInflation": {
            "LOW": "inflation low",
            "MODERATE": "inflation moderate",
            "HIGH": "inflation high",
            "UNKNOWN": "inflation unknown",
        },
        "regimeOil": {"CALM": "oil calm", "SHOCK": "oil shock", "UNKNOWN": "oil unknown"},
        "alertType": {
            "ALLOCATION_DRIFT": "Allocation drift",
            "VOLATILITY": "Volatility",
            "GOAL_REACHED": "Goal reached",
            "MATURITY_DUE": "Maturity and auctions",
            "REVALUATION_DUE": "Value update due",
            "HAWL_APPROACHING": "Zakat date",
            "MONTHLY_REPORT": "Monthly report",
            "SHARIAH_STATUS": "Shariah status change",
            "REGIME_CHANGE": "Macro regime change",
            "SHOCK_EVENT": "Market shock",
        },
    },
    "bn": {
        "shariahStatus": {
            "COMPLIANT": "শরিয়াহসম্মত",
            "NON_COMPLIANT": "শরিয়াহসম্মত নয়",
            "UNDER_REVIEW": "পর্যালোচনাধীন",
        },
        "regimeRate": {
            "EASING": "সুদহার কমছে",
            "TIGHTENING": "সুদহার বাড়ছে",
            "FLAT": "সুদহার স্থির",
            "UNKNOWN": "সুদহারের গতি অজানা",
        },
        "regimeInflation": {
            "LOW": "মূল্যস্ফীতি কম",
            "MODERATE": "মূল্যস্ফীতি মাঝারি",
            "HIGH": "মূল্যস্ফীতি বেশি",
            "UNKNOWN": "মূল্যস্ফীতি অজানা",
        },
        "regimeOil": {"CALM": "তেলের দাম শান্ত", "SHOCK": "তেলের দামে ধাক্কা", "UNKNOWN": "তেলের দাম অজানা"},
        "alertType": {
            "ALLOCATION_DRIFT": "বণ্টনের বিচ্যুতি",
            "VOLATILITY": "অস্থিরতা",
            "GOAL_REACHED": "লক্ষ্য অর্জিত",
            "MATURITY_DUE": "মেয়াদপূর্তি ও নিলাম",
            "REVALUATION_DUE": "মূল্য হালনাগাদ বাকি",
            "HAWL_APPROACHING": "যাকাতের তারিখ",
            "MONTHLY_REPORT": "মাসিক প্রতিবেদন",
            "SHARIAH_STATUS": "শরিয়াহ অবস্থার পরিবর্তন",
            "REGIME_CHANGE": "সামষ্টিক পরিস্থিতির পরিবর্তন",
            "SHOCK_EVENT": "বাজারে ধাক্কা",
        },
    },
}
