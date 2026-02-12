import json

from app.services.llm.types import ParseResult


def _extract_first_json_block(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def parse_result_from_text(text: str) -> ParseResult:
    candidate = _extract_first_json_block(text)
    data = json.loads(candidate)
    return ParseResult.model_validate(data)
