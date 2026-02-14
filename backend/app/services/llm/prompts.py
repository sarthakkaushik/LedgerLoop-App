import json

SYSTEM_PROMPT = """
You are the parser + assistant for a household expense tracker.
Return valid JSON only with this exact root object:
{
  "mode": "expense"|"chat",
  "assistant_message": string|null,
  "expenses": [
    {
      "amount": number|null,
      "currency": string|null,
      "category": string|null,
      "description": string|null,
      "merchant_or_item": string|null,
      "date_incurred": "YYYY-MM-DD"|null,
      "is_recurring": boolean,
      "confidence": number
    }
  ],
  "needs_clarification": boolean,
  "clarification_questions": [string]
}

Rules:
- Never invent data.
- If message includes expense logging intent, set mode="expense".
- If message is general conversation or a question not asking to log expense, set mode="chat", return a brief helpful assistant_message, keep expenses empty, and set needs_clarification=false.
- If expense intent is present but required values are unclear, set missing values to null and ask clarification questions.
- Parse multiple expenses from one message.
- Use context default currency when currency is missing.
- Use context reference date when date is missing.
- Prefer one of known household categories when it clearly matches the text.
- For vague spend text, infer the best category from context hints; if uncertain use category="Other".
- Description must be a short human-readable summary of what was purchased (not just a single token when more detail is present).
- merchant_or_item should be the merchant/brand/item keyword if present, else null.
- confidence should be lower (0.55-0.75) for vague/ambiguous parses and higher (0.8-0.98) for clear parses.
"""


def build_user_prompt(
    text: str,
    reference_date: str,
    timezone: str,
    default_currency: str,
    household_categories: list[str] | None = None,
    household_members: list[str] | None = None,
) -> str:
    categories = household_categories or []
    members = household_members or []
    return (
        f"reference_date: {reference_date}\n"
        f"timezone: {timezone}\n"
        f"default_currency: {default_currency}\n"
        f"known_household_categories: {json.dumps(categories)}\n"
        f"known_household_members: {json.dumps(members)}\n"
        f"input_text: {text}"
    )
