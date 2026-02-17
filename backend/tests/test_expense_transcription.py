import pytest
from httpx import AsyncClient
import httpx

from app.api import expenses as expenses_api


async def register_and_get_token(client: AsyncClient, email: str) -> str:
    payload = {
        "email": email,
        "password": "testpass123",
        "full_name": "Test User",
        "household_name": "Test Family",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()["token"]["access_token"]


@pytest.mark.asyncio
async def test_transcribe_audio_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/expenses/transcribe-audio")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_transcribe_audio_requires_file(client: AsyncClient) -> None:
    token = await register_and_get_token(client, "voice-missing-file@example.com")
    response = await client.post(
        "/expenses/transcribe-audio",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_unsupported_media_type(
    client: AsyncClient,
) -> None:
    token = await register_and_get_token(client, "voice-unsupported@example.com")
    response = await client.post(
        "/expenses/transcribe-audio",
        files={"audio_file": ("note.txt", b"hello", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_oversized_upload(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await register_and_get_token(client, "voice-oversize@example.com")
    monkeypatch.setattr(expenses_api.settings, "voice_max_upload_mb", 0, raising=False)
    response = await client.post(
        "/expenses/transcribe-audio",
        files={"audio_file": ("note.webm", b"\x01\x02", "audio/webm")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_transcribe_audio_returns_503_when_groq_not_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await register_and_get_token(client, "voice-no-key@example.com")
    monkeypatch.setattr(expenses_api.settings, "groq_api_key", None, raising=False)
    response = await client.post(
        "/expenses/transcribe-audio",
        files={"audio_file": ("note.webm", b"voice", "audio/webm")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


@pytest.mark.asyncio
async def test_transcribe_audio_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await register_and_get_token(client, "voice-success@example.com")
    monkeypatch.setattr(expenses_api.settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        expenses_api.settings,
        "groq_whisper_model",
        "whisper-large-v3-turbo",
        raising=False,
    )
    monkeypatch.setattr(expenses_api.settings, "voice_max_upload_mb", 10, raising=False)

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"text": "Spent 500 on groceries", "language": "en"}

    class DummyClient:
        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, **kwargs: object) -> DummyResponse:
            assert "audio/transcriptions" in url
            assert kwargs.get("data", {}).get("model") == "whisper-large-v3-turbo"
            assert kwargs.get("data", {}).get("language") == "en"
            return DummyResponse()

    monkeypatch.setattr(
        "app.services.audio.groq_transcription.httpx.AsyncClient",
        lambda *args, **kwargs: DummyClient(),
    )

    response = await client.post(
        "/expenses/transcribe-audio",
        files={"audio_file": ("note.webm", b"voice-bytes", "audio/webm")},
        data={"language": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "Spent 500 on groceries"
    assert payload["language"] == "en"


@pytest.mark.asyncio
async def test_transcribe_audio_maps_upstream_error_to_502(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await register_and_get_token(client, "voice-upstream@example.com")
    monkeypatch.setattr(expenses_api.settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(expenses_api.settings, "voice_max_upload_mb", 10, raising=False)

    class DummyClient:
        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, **kwargs: object):  # noqa: ANN202
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(
        "app.services.audio.groq_transcription.httpx.AsyncClient",
        lambda *args, **kwargs: DummyClient(),
    )

    response = await client.post(
        "/expenses/transcribe-audio",
        files={"audio_file": ("note.webm", b"voice", "audio/webm")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 502
