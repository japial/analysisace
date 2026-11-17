"""Subjects and bodies of alert emails, in English and Bangla.

Kept apart from the logic because the lines are long. Every email ends with the disclaimer
(PRD section 0). Wording is descriptive: it says what happened, never what to do.
"""

DISCLAIMER = {
    "en": "Historical analysis for education only. Not investment advice.",
    "bn": "শুধুমাত্র শিক্ষামূলক ঐতিহাসিক বিশ্লেষণ। এটি বিনিয়োগ পরামর্শ নয়।",
}
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
}


REPORT_TEXT = {
    "en": (
        "Your analysisACE monthly report for {month}",
        "Spending in {month}: {spending}\nNet worth: {net_worth}\n{zakat}{fire}\nOpen your dashboard: {link}",
        "Zakat estimate: {amount}\n",
        "FIRE progress: {pct}% of your FIRE number\n",
    ),
    "bn": (
        "{month} মাসের analysisACE মাসিক প্রতিবেদন",
        "{month} মাসের খরচ: {spending}\nনিট সম্পদ: {net_worth}\n{zakat}{fire}\nআপনার ড্যাশবোর্ড খুলুন: {link}",
        "যাকাতের আনুমানিক হিসাব: {amount}\n",
        "FIRE অগ্রগতি: আপনার FIRE অঙ্কের {pct}%\n",
    ),
}
