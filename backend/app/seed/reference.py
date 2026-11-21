"""Reference rows every installation needs. Safe to run in production, and to run twice."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExpenseCategory

# FR12.1: default categories in English and Bangla. (key, English, Bangla)
DEFAULT_EXPENSE_CATEGORIES = [
    ("food_bazar", "Food and bazar", "খাবার ও বাজার"),
    ("rent", "Rent", "বাড়ি ভাড়া"),
    ("transport", "Transport", "যাতায়াত"),
    ("utilities", "Utilities", "বিদ্যুৎ, গ্যাস ও পানি"),
    ("education", "Education", "শিক্ষা"),
    ("health", "Health", "স্বাস্থ্য"),
    ("family_support", "Family support", "পরিবারকে সহায়তা"),
    ("religious_giving", "Religious giving", "ধর্মীয় দান"),
    ("other", "Other", "অন্যান্য"),
]


def seed_reference(session: Session) -> int:
    """Add any missing default expense category. Returns how many were added."""
    existing = set(
        session.scalars(select(ExpenseCategory.key).where(ExpenseCategory.household_id.is_(None)))
    )
    added = 0
    for order, (key, name_en, name_bn) in enumerate(DEFAULT_EXPENSE_CATEGORIES, start=1):
        if key in existing:
            continue
        session.add(
            ExpenseCategory(
                household_id=None, key=key, name_en=name_en, name_bn=name_bn, sort_order=order * 10
            )
        )
        added += 1
    session.flush()
    return added
