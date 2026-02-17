from __future__ import annotations

import httpx

GROQ_AUDIO_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqTranscriptionConfigError(RuntimeError):
    """Raised when Groq transcription runtime config is missing."""


class GroqTranscriptionUpstreamError(RuntimeError):
    """Raised when Groq transcription API calls fail."""


def _normalize_optional_language(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


async def transcribe_audio_with_groq(
    *,
    api_key: str | None,
    model: str,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    language: str | None = None,
) -> tuple[str, str | None]:
    if not api_key or not api_key.strip():
        raise GroqTranscriptionConfigError(
            "Groq API key is missing. Set GROQ_API_KEY in backend .env."
        )

    payload: dict[str, str] = {"model": model.strip() or "whisper-large-v3-turbo"}
    normalized_language = _normalize_optional_language(language)
    if normalized_language:
        payload["language"] = normalized_language

    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    files = {
        "file": (
            filename or "voice-note.webm",
            audio_bytes,
            content_type or "application/octet-stream",
        )
    }

    timeout = httpx.Timeout(40.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                GROQ_AUDIO_TRANSCRIPTIONS_URL,
                headers=headers,
                data=payload,
                files=files,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            payload = exc.response.json()
            maybe_message = payload.get("error", {}).get("message")
            if isinstance(maybe_message, str) and maybe_message.strip():
                detail = maybe_message.strip()
        except Exception:
            detail = ""
        message = f"Groq transcription failed with status {exc.response.status_code}."
        if detail:
            message += f" {detail}"
        raise GroqTranscriptionUpstreamError(message) from exc
    except httpx.HTTPError as exc:
        raise GroqTranscriptionUpstreamError(
            "Could not reach Groq transcription service."
        ) from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise GroqTranscriptionUpstreamError(
            "Groq transcription returned an invalid response."
        ) from exc

    raw_text = ""
    if isinstance(response_payload, dict):
        maybe_text = response_payload.get("text")
        if isinstance(maybe_text, str):
            raw_text = maybe_text

    normalized_text = " ".join(raw_text.split()).strip()
    if not normalized_text:
        raise GroqTranscriptionUpstreamError(
            "No speech transcript was returned by Groq."
        )

    resolved_language = normalized_language
    if resolved_language is None and isinstance(response_payload, dict):
        resolved_language = _normalize_optional_language(
            response_payload.get("language")
            if isinstance(response_payload.get("language"), str)
            else None
        )

    return normalized_text, resolved_language
