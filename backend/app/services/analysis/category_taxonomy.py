from __future__ import annotations

import re

CATEGORY_TAXONOMY: dict[str, list[str]] = {
    "food": [
        "groceries",
        "fruits_vegetables",
        "dairy_bakery",
        "dining_out",
        "coffee_tea",
        "snacks",
        "delivery_fees",
        "other",
    ],
    "transport": [
        "fuel",
        "public_transport",
        "cab_ride_hailing",
        "parking",
        "tolls",
        "vehicle_service",
        "other",
    ],
    "housing": [
        "rent",
        "maintenance_hoa",
        "property_tax",
        "repairs_service",
        "cleaning",
        "furnishing",
        "other",
    ],
    "utilities": [
        "electricity",
        "water",
        "gas",
        "internet_broadband",
        "mobile_phone",
        "tv_dth",
        "other",
    ],
    "health": [
        "medicines",
        "doctor_consultation",
        "diagnostics_labs",
        "insurance_health",
        "fitness_gym",
        "other",
    ],
    "education": [
        "books",
        "courses",
        "online_subscriptions",
        "exam_fees",
        "workshops",
        "other",
    ],
    "family_kids": [
        "school_fees",
        "daycare",
        "toys_games",
        "clothes",
        "events_birthdays",
        "other",
    ],
    "entertainment": [
        "movies_events",
        "streaming_subscriptions",
        "games_apps",
        "outing",
        "other",
    ],
    "shopping": [
        "clothing",
        "footwear",
        "accessories",
        "electronics_gadgets",
        "appliances",
        "home_decor",
        "other",
    ],
    "subscriptions": [
        "saas_tools",
        "cloud_ai",
        "newsletters",
        "music_video",
        "storage_backup",
        "other",
    ],
    "personal_care": [
        "salon_spa",
        "grooming",
        "cosmetics",
        "hygiene",
        "other",
    ],
    "gifts_donations": [
        "gifts_personal",
        "charity_donation",
        "festivals",
        "other",
    ],
    "finance_fees": [
        "bank_charges",
        "late_fees",
        "interest",
        "brokerage",
        "other",
    ],
    "business": [
        "software_tools",
        "hosting_domains",
        "marketing_ads",
        "contractor_payments",
        "travel_business",
        "office_supplies",
        "other",
    ],
    "travel": [
        "flights",
        "hotels",
        "train_bus",
        "visa_passport",
        "local_transport",
        "food_travel",
        "other",
    ],
    "home": [
        "household_supplies",
        "cleaning_supplies",
        "kitchenware",
        "small_repairs",
        "pest_control",
        "other",
    ],
    "pet": ["food", "vet", "grooming", "supplies", "other"],
    "taxes": ["income_tax", "gst", "professional_tax", "filing_fees", "other"],
    "investments": [
        "mutual_funds",
        "stocks",
        "fd_rd",
        "gold",
        "crypto",
        "brokerage_fees",
        "other",
    ],
    "misc": ["uncategorized", "rounding", "other"],
}

MANUAL_ALIASES: dict[str, list[str]] = {
    "food": ["grocery", "meal", "meals", "restaurant", "dining", "lunch", "dinner"],
    "transport": ["uber", "ola", "cab", "taxi", "petrol", "diesel", "commute"],
    "shopping": ["purchase", "buy", "bought", "mall"],
    "health": ["medical", "hospital", "clinic"],
    "housing": ["home_rent", "house_rent"],
}


def normalize_category_token(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def expand_category_terms(
    raw_category: str | None,
    *,
    household_categories: list[str] | None = None,
) -> list[str]:
    if not raw_category:
        return []
    token = normalize_category_token(raw_category)
    if not token:
        return []

    terms: set[str] = {token}

    for canonical, subcategories in CATEGORY_TAXONOMY.items():
        normalized_canonical = normalize_category_token(canonical)
        normalized_subs = {normalize_category_token(item) for item in subcategories}
        if token == normalized_canonical or token in normalized_subs:
            terms.add(normalized_canonical)
            terms.update(normalized_subs)

    for canonical, aliases in MANUAL_ALIASES.items():
        normalized_canonical = normalize_category_token(canonical)
        normalized_aliases = {normalize_category_token(item) for item in aliases}
        if token == normalized_canonical or token in normalized_aliases:
            terms.add(normalized_canonical)
            terms.update(normalized_aliases)

    for item in household_categories or []:
        normalized_item = normalize_category_token(item)
        if not normalized_item:
            continue
        if normalized_item in terms or token in normalized_item or normalized_item in token:
            terms.add(normalized_item)

    terms.discard("")
    return sorted(terms)


def resolve_member_name(raw_member: str | None, *, household_members: list[str] | None) -> str | None:
    if not raw_member:
        return None
    needle = raw_member.strip().lower()
    if not needle:
        return None
    members = [m.strip() for m in (household_members or []) if m and m.strip()]
    if not members:
        return raw_member.strip()
    exact = [m for m in members if m.lower() == needle]
    if exact:
        return exact[0]
    contains = [m for m in members if needle in m.lower() or m.lower() in needle]
    if contains:
        return contains[0]
    return raw_member.strip()
