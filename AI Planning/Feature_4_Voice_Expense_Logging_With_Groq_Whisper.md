# Feature Plan: Voice Expense Logging via Groq Whisper (`whisper-large-v3-turbo`)

## Summary
Add a secure voice-to-text path so users can record speech, transcribe it with Groq Whisper, auto-fill the existing query box, edit text if needed, then continue with current actions:
- Capture tab: `Create Drafts`
- Insights tab: `Run Insight`

This plan uses a backend proxy for Groq API calls (no frontend API key exposure), reusable frontend voice input logic, and explicit UX states for recording/transcribing/errors.

## Scope
In scope:
- Voice input for `Capture` and `Insights` query boxes
- Backend transcription endpoint
- Groq Whisper integration (`whisper-large-v3-turbo`)
- Edit-before-submit flow preserved
- Loading/error states and permission handling

Out of scope (V1):
- Voice in Quick Add modal
- Speaker diarization
- Long-form audio uploads
- Storing raw audio permanently

## Architecture Decisions
1. API key security: Groq API key stays backend-only.
2. Recording interaction: tap-to-start / tap-to-stop.
3. Language handling: auto-detect by default, with optional manual language override.
4. Transcript insertion: append to existing textarea content (newline-separated), not replace.
5. Privacy default: audio is transient in memory for request processing only.

## Public API / Interface Changes

### Backend
New endpoint:
- `POST /expenses/transcribe-audio`
- Auth: Bearer token required (same as other expense endpoints)
- Content-Type: `multipart/form-data`
- Form fields:
  - `audio_file` (required): recorded audio blob/file
  - `language` (optional): ISO language code, e.g. `en`, `hi`
- Response `200`:
  - `text: string` (transcribed text, trimmed)
  - `language: string | null` (detected or provided)
- Error responses:
  - `401` unauthorized
  - `413` file too large
  - `415` unsupported media type
  - `422` invalid/missing payload
  - `503` Groq not configured / unavailable
  - `502` upstream Groq failure

Env/config additions:
- `GROQ_API_KEY` (required in env to enable feature)
- `GROQ_WHISPER_MODEL` default: `whisper-large-v3-turbo`
- `VOICE_MAX_UPLOAD_MB` default: `10`

### Frontend
`frontend/src/api.js`:
- Add `transcribeExpenseAudio(token, formData)` helper using `fetch` (no JSON content type header for multipart).

`frontend/src/App.jsx`:
- Add reusable voice input control used by:
  - `ExpenseLogPanel` textarea
  - `AnalyticsPanel` textarea
- New UI states per panel:
  - `idle`, `recording`, `transcribing`, `error`
- Optional language selector near mic control (default auto)

## Detailed Implementation Plan

### 1. Backend: transcription service
- Create `backend/app/services/audio/groq_transcription.py` with:
  - async function/class method to call Groq transcription endpoint (OpenAI-compatible audio transcription route).
  - multipart upload via `httpx.AsyncClient`.
  - timeout + explicit upstream error mapping.
- Validate:
  - file exists and non-empty
  - allowed MIME/extensions (`audio/webm`, `audio/wav`, `audio/mpeg`, `audio/mp4`, `audio/ogg`)
  - size <= configured max
- Normalize output text (`strip`, collapse excessive whitespace).

### 2. Backend: schema + route
- Extend `backend/app/schemas/expense.py`:
  - `ExpenseAudioTranscriptionResponse`
- Add route to `backend/app/api/expenses.py`:
  - `@router.post("/transcribe-audio", response_model=...)`
  - accept multipart file + optional language
  - call transcription service
  - return normalized text/language
- Keep route under `/expenses` for feature cohesion with existing capture flow.

### 3. Backend: config wiring
- Update `backend/app/core/config.py` for new env vars.
- Ensure startup remains backward compatible if feature not used.
- If `GROQ_API_KEY` missing and endpoint called, return `503` with clear message.

### 4. Frontend: reusable voice recorder logic
- Add local reusable hook/component pattern (inside `App.jsx` or extracted file):
  - Use `navigator.mediaDevices.getUserMedia({ audio: true })`
  - Use `MediaRecorder` with browser-supported mime fallback
  - Collect chunks until stop, build `Blob`, send to backend API helper
  - Release mic tracks after stop/cancel
- State machine:
  - Start: request mic -> `recording`
  - Stop: `transcribing`
  - Success: insert transcript into textarea and return to `idle`
  - Failure: show inline error + return to `idle`

### 5. Frontend: Capture integration
- Add mic button next to Capture textarea actions.
- Add helper text:
  - recording indicator
  - transcribing indicator (`Transcribing voice note...`)
- On transcript success:
  - if textarea empty: set transcript
  - else append `\n` + transcript
- Do not auto-submit. User still clicks `Create Drafts`.

### 6. Frontend: Insights integration
- Add same mic flow to analytics question textarea.
- User reviews/edits transcript, then clicks `Run Insight`.
- Keep existing prompt pills unchanged.

### 7. UX and accessibility
- Button labels/ARIA:
  - `Start voice input`
  - `Stop recording`
- Visible status text for recording/transcribing/error.
- Disable conflicting actions during `transcribing` only (keep editing enabled when idle).
- If permission denied, show actionable inline message.

### 8. Documentation update
- Update setup docs (`backend` or root README section) with:
  - required `GROQ_API_KEY`
  - optional model/lang notes
  - browser mic permission requirement

## Test Cases and Scenarios

### Backend automated tests
Add to `backend/tests`:
1. `POST /expenses/transcribe-audio` requires auth -> `401`.
2. Missing file -> `422`.
3. Unsupported media type -> `415`.
4. Oversized file -> `413`.
5. Missing Groq key -> `503`.
6. Successful transcription path (mock httpx/Groq response) -> `200` with text.
7. Upstream non-200 from Groq -> mapped `502`.

### Frontend validation (manual QA for V1)
1. Capture: record voice, transcript appears, edit text, click `Create Drafts`.
2. Insights: record voice, transcript appears, click `Run Insight`.
3. Permission denied path shows clear error.
4. Double-click/start-stop race does not crash UI.
5. Existing typed text remains and transcript appends correctly.
6. Network failure during transcription shows recoverable error state.

## Acceptance Criteria
- User can record voice in Capture and Insights and see transcript in textarea.
- User can edit transcript before submitting.
- No Groq key exposed to client.
- Errors are user-readable and do not block subsequent retries.
- Existing typed-text flow remains unchanged.

## Assumptions and Defaults
- Frontend remains React single-page app (`frontend/src/App.jsx` pattern).
- Backend remains FastAPI with current auth dependency model.
- V1 supports short notes only (default max upload 10 MB).
- Audio is not persisted server-side.
- Quick Add voice support intentionally deferred to later phase.
