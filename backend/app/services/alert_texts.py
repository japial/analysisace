"""Subjects and bodies of alert emails, in English and Bangla.

Kept apart from the logic because the lines are long. Placeholders are filled with readable
values (email_render.readable), and every email ends with the disclaimer (email_render).
Wording is descriptive: it says what happened, never what to do.
"""

EMAIL_TEXT: dict[str, dict[str, tuple[str, str]]] = {
    "ALLOCATION_DRIFT": {
        "en": (
            "Allocation drift from your target",
            "{asset_class} is {actual_pct}% of your portfolio. Your target is {target_pct}% with a band of {band_pct} points.",
        ),
        "bn": (
            "আপনার লক্ষ্য থেকে বণ্টনের বিচ্যুতি",
            "{asset_class} এখন আপনার পোর্টফোলিওর {actual_pct}%। আপনার লক্ষ্য {target_pct}%, সীমা {band_pct} পয়েন্ট।",
        ),
    },
    "VOLATILITY": {
        "en": (
            "Portfolio volatility above your limit",
            "Over the past year your listed holdings moved with an annualised volatility of {volatility_pct}%. Your limit is {limit_pct}%.",
        ),
        "bn": (
            "পোর্টফোলিওর অস্থিরতা আপনার সীমার উপরে",
            "গত এক বছরে আপনার তালিকাভুক্ত বিনিয়োগের বার্ষিক অস্থিরতা ছিল {volatility_pct}%। আপনার সীমা {limit_pct}%।",
        ),
    },
    "GOAL_REACHED": {
        "en": ("You reached a goal", 'Your goal "{name}" has been reached.'),
        "bn": ("আপনি একটি লক্ষ্য অর্জন করেছেন", 'আপনার লক্ষ্য "{name}" অর্জিত হয়েছে।'),
    },
    "MATURITY_DUE": {
        "en": ("A holding matures soon", "{name} matures on {date} ({days} days from now)."),
        "bn": (
            "একটি বিনিয়োগের মেয়াদ শিগগিরই শেষ হচ্ছে",
            "{name}-এর মেয়াদ {date} তারিখে শেষ হবে ({days} দিন পর)।",
        ),
    },
    "SUKUK_AUCTION": {
        "en": (
            "Government sukuk auction",
            "{name} is scheduled for auction on {date} ({days} days from now).",
        ),
        "bn": ("সরকারি সুকুক নিলাম", "{name}-এর নিলাম {date} তারিখে নির্ধারিত ({days} দিন পর)।"),
    },
    "REVALUATION_DUE": {
        "en": (
            "Time to update a value",
            "{name} was last valued more than {months} months ago. Enter its current value to keep your net worth up to date.",
        ),
        "bn": (
            "মূল্য হালনাগাদের সময় হয়েছে",
            "{name}-এর মূল্য {months} মাসের বেশি আগে দেওয়া হয়েছিল। আপনার নিট সম্পদ সঠিক রাখতে বর্তমান মূল্য দিন।",
        ),
    },
    "HAWL_APPROACHING": {
        "en": (
            "Your Zakat date is near",
            "The Zakat date for {name} is {date} ({days} days from now).",
        ),
        "bn": ("আপনার যাকাতের তারিখ নিকটে", "{name}-এর যাকাতের তারিখ {date} ({days} দিন পর)।"),
    },
    # Market alerts (F7). Status and regime codes are turned into words before they are
    # filled in (email_render.readable).
    "SHARIAH_STATUS_CHANGED": {
        "en": (
            "Shariah status changed: {ticker}",
            "The Shariah screening status of {ticker} changed from {from_status} to {to_status}.",
        ),
        "bn": (
            "শরিয়াহ অবস্থা বদলেছে: {ticker}",
            "{ticker}-এর শরিয়াহ স্ক্রিনিং অবস্থা {from_status} থেকে {to_status} হয়েছে।",
        ),
    },
    "REGIME_CHANGED": {
        "en": (
            "Macro regime label changed",
            "The rules-based macro regime label changed from {previous} to {label}.",
        ),
        "bn": (
            "সামষ্টিক অর্থনৈতিক অবস্থার লেবেল বদলেছে",
            "নিয়মভিত্তিক সামষ্টিক অর্থনৈতিক অবস্থার লেবেল {previous} থেকে {label} হয়েছে।",
        ),
    },
    "SHOCK_EVENT_PUBLISHED": {
        "en": (
            "New event in the shock playbook",
            "A new event was added to the shock playbook: {title_en} ({date}).",
        ),
        "bn": (
            "শক প্লেবুকে নতুন ঘটনা",
            "শক প্লেবুকে নতুন একটি ঘটনা যোগ হয়েছে: {title_bn} ({date})।",
        ),
    },
}
