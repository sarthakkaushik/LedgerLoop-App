import re
from datetime import timedelta

from app.services.llm.base import ExpenseParserProvider
from app.services.llm.types import ParseContext, ParseResult, ParsedExpense

AMOUNT_PATTERN = re.compile(r"(?:INR|USD|EUR|RS\.?|\$|EUR)?\s*(\d+(?:\.\d{1,2})?)", re.I)

CATEGORY_KEYWORDS: dict[str, str] = {
    "grocer": "Groceries",
    "grocery": "Groceries",
    "food": "Food",
    "restaurant": "Dining",
    "dining": "Dining",
    "uber": "Transport",
    "taxi": "Transport",
    "bus": "Transport",
    "fuel": "Transport",
    "rent": "Rent",
    "electricity": "Bills",
    "internet": "Bills",
    "bill": "Bills",
    "movie": "Entertainment",
    "netflix": "Entertainment",
    "doctor": "Health",
    "medicine": "Health",
    "shopping": "Shopping",
}

RECURRING_HINTS = ("monthly", "every month", "subscription", "recurring")
CHAT_HINTS = (
    "hello",
    "hi",
    "how are you",
    "what can you do",
    "help",
    "thanks",
    "thank you",
    "who are you",
)
EXPENSE_HINTS = (
    "spent",
    "paid",
    "bought",
    "bill",
    "expense",
    "rent",
    "grocery",
    "electricity",
    "uber",
    "food",
)


def _infer_currency(text: str, default_currency: str) -> str:
    low = text.lower()
    if "inr" in low or "rs" in low:
        return "INR"
    if "$" in text or "usd" in low:
        return "USD"
    if "eur" in low:
        return "EUR"
    return default_currency


def _infer_category(text: str) -> str:
    low = text.lower()
    for key, value in CATEGORY_KEYWORDS.items():
        if key in low:
            return value
    return "Other"


def _extract_date(text: str, context: ParseContext) -> str:
    low = text.lower()
    if "yesterday" in low:
        return str(context.reference_date - timedelta(days=1))
    return str(context.reference_date)


def _description_from_clause(clause: str) -> str:
    cleaned = re.sub(AMOUNT_PATTERN, "", clause)
    cleaned = re.sub(r"\b(bought|paid|spent|for|and)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    return cleaned[:100] if cleaned else "Expense entry"


def _looks_like_general_chat(text: str) -> bool:
    low = text.lower().strip()
    has_chat_hint = any(hint in low for hint in CHAT_HINTS)
    has_expense_hint = any(hint in low for hint in EXPENSE_HINTS)
    has_amount = bool(AMOUNT_PATTERN.search(text))
    return (has_chat_hint or low.endswith("?")) and not has_expense_hint and not has_amount


class MockExpenseParserProvider(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        clauses = [part.strip() for part in re.split(r",| and ", text) if part.strip()]
        drafts: list[ParsedExpense] = []
        currency = _infer_currency(text, context.default_currency)
        for clause in clauses:
            amount_match = AMOUNT_PATTERN.search(clause)
            if not amount_match:
                continue
            amount = float(amount_match.group(1))
            category = _infer_category(clause)
            description = _description_from_clause(clause)
            drafts.append(
                ParsedExpense(
                    amount=amount,
                    currency=currency,
                    category=category,
                    description=description,
                    merchant_or_item=description,
                    date_incurred=_extract_date(clause, context),
                    is_recurring=any(hint in clause.lower() for hint in RECURRING_HINTS),
                    confidence=0.9 if category != "Other" else 0.75,
                )
            )

        if drafts:
            return ParseResult(expenses=drafts, mode="expense", needs_clarification=False)

        if _looks_like_general_chat(text):
            return ParseResult(
                mode="chat",
                assistant_message=(
                    "I can help with expense logging and summaries. "
                    "Share a spend message like 'paid 500 for groceries'."
                ),
                expenses=[],
                needs_clarification=False,
            )

        return ParseResult(
            expenses=[],
            mode="expense",
            needs_clarification=True,
            clarification_questions=[
                "I could not find a clear amount. Can you share how much was spent?"
            ],
        )
