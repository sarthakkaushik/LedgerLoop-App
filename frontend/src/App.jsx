import { Component, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  askAnalysis,
  confirmExpenses,
  createRecurringExpense,
  createTaxonomyCategory,
  createTaxonomySubcategory,
  createInviteCode,
  deleteTaxonomyCategory,
  deleteTaxonomySubcategory,
  deleteExpense,
  deleteHouseholdMember,
  downloadExpenseCsv,
  fetchDashboard,
  fetchExpenseFeed,
  fetchHousehold,
  fetchTaxonomy,
  joinHousehold,
  loginUser,
  parseExpenseText,
  registerUser,
  transcribeExpenseAudio,
  updateExpenseRecurring,
  updateTaxonomyCategory,
  updateTaxonomySubcategory,
} from "./api";

const tabs = [
  { id: "capture", label: "Add Expense" },
  { id: "ledger", label: "Ledger" },
  { id: "recurring", label: "Recurring" },
  { id: "insights", label: "Insights" },
  { id: "people", label: "People & Access" },
];

function TabIcon({ tabId }) {
  if (tabId === "capture") {
    return (
      <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
        <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Zm7 1.5a1 1 0 1 0 2 0V6h2a1 1 0 1 0 0-2h-2V2a1 1 0 1 0-2 0v2H9a1 1 0 1 0 0 2h2v2Z" />
      </svg>
    );
  }
  if (tabId === "ledger") {
    return (
      <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
        <path d="M5 4a2 2 0 0 0-2 2v12.75C3 20 4 21 5.25 21H19a1 1 0 1 0 0-2H5.25a.25.25 0 0 1-.25-.25V18h12a4 4 0 0 0 4-4V6a2 2 0 0 0-2-2H5Zm3 4a1 1 0 0 0 0 2h8a1 1 0 1 0 0-2H8Zm0 4a1 1 0 0 0 0 2h5a1 1 0 1 0 0-2H8Z" />
      </svg>
    );
  }
  if (tabId === "recurring") {
    return (
      <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
        <path d="M12 3a9 9 0 0 1 8.64 6.47 1 1 0 1 1-1.93.52A7 7 0 0 0 6.1 8H8a1 1 0 1 1 0 2H3.5A1.5 1.5 0 0 1 2 8.5V4a1 1 0 1 1 2 0v2.17A9 9 0 0 1 12 3Zm8.5 11a1 1 0 0 1 1 1v4.5A1.5 1.5 0 0 1 20 21h-4.5a1 1 0 1 1 0-2h1.9A7 7 0 0 0 5.3 14.01a1 1 0 0 1-1.95-.45A9 9 0 0 1 20 11.83V15a1 1 0 0 1-1.5.87V14.5Z" />
      </svg>
    );
  }
  if (tabId === "insights") {
    return (
      <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
        <path d="M4 19a1 1 0 0 1-1-1V6a1 1 0 1 1 2 0v11h15a1 1 0 1 1 0 2H4Zm3-4.2a1 1 0 0 1-.7-1.72l2.6-2.6a1 1 0 0 1 1.4 0l1.7 1.7 3.3-3.3a1 1 0 0 1 1.41 1.41l-4 4a1 1 0 0 1-1.4 0l-1.7-1.7-1.9 1.9a1 1 0 0 1-.7.3Z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M16 11a4 4 0 1 0-3.87-5h-.26A4 4 0 1 0 8 11a4 4 0 0 0 3.87 5h.26A4 4 0 1 0 16 11Zm-8 0a2 2 0 1 1 0-4 2 2 0 0 1 0 4Zm8 8a2 2 0 1 1 0-4 2 2 0 0 1 0 4Zm0-10a2 2 0 1 1 0-4 2 2 0 0 1 0 4Zm-4 5a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z" />
    </svg>
  );
}

const initialRegister = {
  full_name: "",
  email: "",
  password: "",
  household_name: "",
};

const initialLogin = {
  email: "",
  password: "",
};

const RUPEE_SYMBOL = "\u20B9";
const EURO_SYMBOL = "\u20ac";
const POUND_SYMBOL = "\u00a3";
const YEN_SYMBOL = "\u00a5";

const initialJoin = {
  full_name: "",
  email: "",
  password: "",
  invite_code: "",
};

const GLOBAL_CURRENCY_OPTIONS = [
  { symbol: RUPEE_SYMBOL, code: "INR", name: "Indian Rupee" },
  { symbol: "$", code: "USD", name: "US Dollar" },
  { symbol: EURO_SYMBOL, code: "EUR", name: "Euro" },
  { symbol: POUND_SYMBOL, code: "GBP", name: "British Pound" },
  { symbol: YEN_SYMBOL, code: "JPY", name: "Japanese Yen" },
  { symbol: "AED", code: "AED", name: "UAE Dirham" },
];

function safeStorageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // no-op: storage can be blocked in some browser contexts
  }
}

function safeStorageRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // no-op: storage can be blocked in some browser contexts
  }
}

function safeParseStoredUser(raw) {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    safeStorageRemove("expense_auth_user");
    return null;
  }
}

function normalizeTaxonomyName(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

const RECORDER_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

const MIME_EXTENSION_MAP = {
  "audio/webm": "webm",
  "audio/mp4": "mp4",
  "audio/ogg": "ogg",
  "audio/wav": "wav",
  "audio/mpeg": "mp3",
};

function appendVoiceTranscript(existingText, transcript) {
  const current = String(existingText || "");
  const next = String(transcript || "").trim();
  if (!next) return current;
  const trimmedCurrent = current.trimEnd();
  if (!trimmedCurrent) return next;
  return `${trimmedCurrent}\n${next}`;
}

function isVoiceInputSupported() {
  try {
    if (typeof window === "undefined") return false;
    const browserNavigator = typeof window.navigator !== "undefined" ? window.navigator : null;
    if (
      !browserNavigator ||
      !browserNavigator.mediaDevices ||
      typeof browserNavigator.mediaDevices.getUserMedia !== "function"
    ) {
      return false;
    }
    return typeof window.MediaRecorder !== "undefined";
  } catch {
    return false;
  }
}

function pickRecorderMimeType() {
  try {
    if (typeof window === "undefined" || typeof window.MediaRecorder === "undefined") {
      return "";
    }
    if (typeof window.MediaRecorder.isTypeSupported !== "function") {
      return "";
    }
    return RECORDER_MIME_TYPES.find((mimeType) => window.MediaRecorder.isTypeSupported(mimeType)) || "";
  } catch {
    return "";
  }
}

function extensionFromMimeType(mimeType) {
  const normalized = String(mimeType || "").split(";")[0].trim().toLowerCase();
  return MIME_EXTENSION_MAP[normalized] || "webm";
}

function resolveVoiceErrorMessage(error) {
  if (!error) return "Voice capture failed. Please try again.";
  const name = String(error?.name || "");
  if (name === "NotAllowedError") {
    return "Microphone permission was denied. Allow microphone access and try again.";
  }
  if (name === "NotFoundError") {
    return "No microphone was found on this device.";
  }
  const message = String(error?.message || "").trim();
  return message || "Voice capture failed. Please try again.";
}

function useVoiceTranscription({ token, onTranscript }) {
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [supported, setSupported] = useState(false);
  const [supportChecked, setSupportChecked] = useState(false);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const onTranscriptRef = useRef(onTranscript);
  const mountedRef = useRef(true);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    try {
      setSupported(isVoiceInputSupported());
    } catch {
      setSupported(false);
    } finally {
      setSupportChecked(true);
    }
  }, []);

  function cleanupStream() {
    const stream = streamRef.current;
    if (!stream) return;
    stream.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function clearError() {
    setError("");
  }

  function cancelRecording() {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    chunksRef.current = [];
    try {
      if (recorder && recorder.state !== "inactive") {
        recorder.ondataavailable = null;
        recorder.onerror = null;
        recorder.onstop = null;
        recorder.stop();
      }
    } catch {
      // no-op: best-effort stop
    }
    cleanupStream();
    if (mountedRef.current) {
      setStatus("idle");
      setError("");
    }
  }

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      try {
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== "inactive") {
          recorder.stop();
        }
      } catch {
        // no-op: best-effort cleanup
      }
      cleanupStream();
    };
  }, []);

  async function startRecording() {
    if (!isVoiceInputSupported()) {
      setSupported(false);
      setError("Voice input is not supported in this browser.");
      return;
    }
    setSupported(true);
    if (status !== "idle") return;
    clearError();
    try {
      const browserNavigator = window.navigator;
      const stream = await browserNavigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mimeType = pickRecorderMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorderRef.current = recorder;
      recorder.start();
      setStatus("recording");
    } catch (err) {
      cleanupStream();
      setStatus("idle");
      setError(resolveVoiceErrorMessage(err));
    }
  }

  async function stopRecording() {
    if (status !== "recording") return;
    const recorder = recorderRef.current;
    if (!recorder) {
      setStatus("idle");
      return;
    }
    setStatus("transcribing");
    clearError();
    try {
      const stopPromise = new Promise((resolve) => {
        recorder.addEventListener("stop", resolve, { once: true });
      });
      recorder.stop();
      await stopPromise;

      const chunks = chunksRef.current;
      chunksRef.current = [];
      recorderRef.current = null;
      cleanupStream();

      const guessedMimeType = String(recorder.mimeType || chunks[0]?.type || "audio/webm");
      const audioBlob = new Blob(chunks, { type: guessedMimeType });
      if (audioBlob.size === 0) {
        throw new Error("No voice note was captured. Please record again.");
      }

      const extension = extensionFromMimeType(audioBlob.type);
      const formData = new FormData();
      formData.append("audio_file", audioBlob, `voice-note.${extension}`);
      const normalizedLanguage = "en";
      if (normalizedLanguage) {
        formData.append("language", normalizedLanguage);
      }

      const response = await transcribeExpenseAudio(token, formData);
      const transcript = String(response?.text || "").trim();
      if (!transcript) {
        throw new Error("No speech transcript was detected. Try speaking a little louder.");
      }
      if (typeof onTranscriptRef.current === "function") {
        onTranscriptRef.current(transcript);
      }
      if (mountedRef.current) {
        setStatus("idle");
      }
    } catch (err) {
      cleanupStream();
      recorderRef.current = null;
      if (mountedRef.current) {
        setStatus("idle");
        setError(resolveVoiceErrorMessage(err));
      }
    }
  }

  return {
    supported,
    supportChecked,
    status,
    error,
    startRecording,
    stopRecording,
    cancelRecording,
    clearError,
  };
}

function VoiceTranscriptionControls({ voice, disabled = false }) {
  const isRecording = voice.status === "recording";
  const isTranscribing = voice.status === "transcribing";
  const controlsDisabled = disabled || isTranscribing;
  const recordingBars = [0, 1, 2, 3, 4, 5];

  return (
    <button
      type="button"
      className={
        isRecording
          ? "voice-corner-button recording"
          : isTranscribing
            ? "voice-corner-button transcribing"
            : "voice-corner-button"
      }
      onClick={() => {
        if (isRecording) {
          void voice.stopRecording();
        } else {
          void voice.startRecording();
        }
      }}
      disabled={controlsDisabled || !voice.supportChecked || !voice.supported}
      aria-label={isRecording ? "Stop recording" : "Start voice input"}
      aria-pressed={isRecording}
    >
      {isRecording && (
        <span className="voice-live-rings" aria-hidden="true">
          <span className="voice-live-ring ring-one" />
          <span className="voice-live-ring ring-two" />
        </span>
      )}
      <span className="voice-icon" aria-hidden="true">
        {isRecording ? (
          <svg viewBox="0 0 24 24" focusable="false">
            <rect x="7" y="7" width="10" height="10" rx="2" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" focusable="false">
            <path d="M12 15a3 3 0 0 0 3-3V7a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" />
            <path d="M6 11a1 1 0 1 1 2 0 4 4 0 1 0 8 0 1 1 0 1 1 2 0 6 6 0 0 1-5 5.91V20h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-3.09A6 6 0 0 1 6 11Z" />
          </svg>
        )}
      </span>
      {isRecording && (
        <span className="voice-eq" aria-hidden="true">
          {recordingBars.map((bar) => (
            <span key={bar} style={{ "--bar-index": String(bar) }} />
          ))}
        </span>
      )}
    </button>
  );
}

function VoiceTranscriptionFeedback({ voice }) {
  const isRecording = voice.status === "recording";
  const isTranscribing = voice.status === "transcribing";
  const listeningBars = Array.from({ length: 16 }, (_, index) => index);

  return (
    <>
      {voice.supportChecked && !voice.supported && (
        <p className="hint voice-feedback">Voice input is unavailable in this browser. You can continue by typing.</p>
      )}
      {isRecording && (
        <div className="voice-listening-shell" role="status" aria-live="polite">
          <p className="hint voice-feedback">Listening...</p>
          <div className="voice-listening-wave" aria-hidden="true">
            {listeningBars.map((bar) => (
              <span key={bar} style={{ "--bar-index": String(bar) }} />
            ))}
          </div>
        </div>
      )}
      {isTranscribing && <p className="hint voice-feedback">Transcribing voice note...</p>}
      {voice.error && <p className="form-error voice-feedback">{voice.error}</p>}
    </>
  );
}

class RuntimeErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: String(error?.message || "Unexpected runtime error."),
    };
  }

  componentDidCatch(error) {
    try {
      console.error("App runtime error:", error);
    } catch {
      // no-op
    }
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }
    return (
      <main className="app-shell">
        <section className="panel">
          <h2>Something went wrong</h2>
          <p className="hint">
            The app hit a runtime error. Please reload. If this keeps happening, we will debug using
            the exact error shown below.
          </p>
          <p className="form-error">{this.state.message}</p>
          <button
            type="button"
            className="btn-main"
            onClick={() => {
              if (typeof window !== "undefined" && typeof window.location?.reload === "function") {
                window.location.reload();
              }
            }}
          >
            Reload App
          </button>
        </section>
      </main>
    );
  }
}

function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  busy = false,
  onCancel,
  onConfirm,
}) {
  if (!open) return null;

  return (
    <div className="confirm-backdrop" role="presentation">
      <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h3 id="confirm-title">{title}</h3>
        <p>{description}</p>
        <div className="confirm-actions">
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button type="button" className="btn-danger" onClick={onConfirm} disabled={busy}>
            {busy ? "Please wait..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function PanelSkeleton({ rows = 3 }) {
  return (
    <div className="panel-skeleton" aria-hidden="true">
      <div className="skeleton-line skeleton-line-title" />
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-line" />
      ))}
    </div>
  );
}

function ToastNotice({ message, placement = "bottom-right" }) {
  if (!message) return null;
  const className = placement === "top-right" ? "toast-notice top-right" : "toast-notice";
  return (
    <div className={className} role="status" aria-live="polite">
      {message}
    </div>
  );
}

function EmptyState({ title, description, actionLabel, onAction }) {
  return (
    <section className="empty-state" role="status" aria-live="polite">
      <div className="empty-state-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Zm3 2.5a1 1 0 1 0 0 2h10a1 1 0 1 0 0-2H7Zm0 4a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2H7Z" />
        </svg>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {actionLabel && typeof onAction === "function" && (
        <button type="button" className="btn-ghost" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </section>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M9 3a1 1 0 0 0-1 1v1H5a1 1 0 1 0 0 2h.62l1 11.06A2 2 0 0 0 8.61 20h6.78a2 2 0 0 0 1.99-1.94L18.38 7H19a1 1 0 1 0 0-2h-3V4a1 1 0 0 0-1-1H9Zm1 2h4v1h-4V5Zm-1.38 3h6.76l-.95 10.02h-4.86L8.62 8Zm2.38 2a1 1 0 0 0-1 1v5a1 1 0 1 0 2 0v-5a1 1 0 0 0-1-1Zm3 0a1 1 0 0 0-1 1v5a1 1 0 1 0 2 0v-5a1 1 0 0 0-1-1Z" />
    </svg>
  );
}

function RecurringSwitch({ checked, disabled = false, onToggle, label }) {
  return (
    <button
      type="button"
      className={checked ? "recurring-switch on" : "recurring-switch"}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onToggle(!checked)}
      disabled={disabled}
    >
      <span className="recurring-switch-thumb" />
    </button>
  );
}

function StatusPill({ status }) {
  const normalized = String(status || "")
    .trim()
    .toLowerCase();
  const label = normalized ? normalized[0].toUpperCase() + normalized.slice(1) : "-";
  let className = "status-pill";
  if (normalized === "confirmed") {
    className += " confirmed";
  } else if (normalized === "draft") {
    className += " draft";
  }
  return <span className={className}>{label}</span>;
}

function SessionTransition() {
  return (
    <section className="session-transition">
      <div className="session-orb" aria-hidden="true" />
      <h2>Loading your workspace...</h2>
      <p>Preparing capture, ledger, and insights.</p>
    </section>
  );
}

function ExpenseAssistantResponse({ result, compact = false, showMode = false }) {
  const assistantMessage = String(result?.assistant_message || "").trim() || "Draft entries are ready to review.";
  const clarificationQuestions = Array.isArray(result?.clarification_questions)
    ? result.clarification_questions
        .map((question) => String(question || "").trim())
        .filter(Boolean)
    : [];
  const needsClarification = Boolean(result?.needs_clarification);

  return (
    <article className={compact ? "result-card assistant-thread compact" : "result-card assistant-thread"}>
      <div className="assistant-turn">
        <span className="assistant-thread-avatar" aria-hidden="true">
          AI
        </span>
        <div className="assistant-turn-body">
          <div className="assistant-thread-header">
            <p className="assistant-thread-name">LedgerLoop Assistant</p>
            {needsClarification && <span className="assistant-clarify-pill">Clarification needed</span>}
          </div>
          <div className="assistant-bubble markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{assistantMessage}</ReactMarkdown>
            {needsClarification && (
              <div className="assistant-clarification-inline">
                <p className="assistant-clarification-title">Please confirm:</p>
                {clarificationQuestions.length > 0 ? (
                  <ul>
                    {clarificationQuestions.map((question, index) => (
                      <li key={`${question}-${index}`}>{question}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="assistant-clarification-fallback">
                    Share one more detail so I can finish the draft.
                  </p>
                )}
              </div>
            )}
          </div>
          {showMode && (
            <p className="assistant-thread-meta">
              Mode: <strong>{result?.mode === "chat" ? "Conversation" : "Smart Drafting"}</strong>
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

function QuickAddModal({
  open,
  token,
  onClose,
  onRouteToCapture,
  onNotify,
}) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmKey, setConfirmKey] = useState("");
  const [error, setError] = useState("");
  const [taxonomy, setTaxonomy] = useState({ categories: [] });
  const [taxonomyLoading, setTaxonomyLoading] = useState(false);
  const [taxonomyError, setTaxonomyError] = useState("");
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);

  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );
  const taxonomyCategoryOptions = useMemo(
    () => taxonomyCategories.map((category) => category.name),
    [taxonomyCategories]
  );
  const quickAddVoice = useVoiceTranscription({
    token,
    onTranscript: (transcript) => {
      setText((previous) => appendVoiceTranscript(previous, transcript));
      setError("");
    },
  });
  const quickAddVoiceTranscribing = quickAddVoice.status === "transcribing";
  const quickAddVoiceRecording = quickAddVoice.status === "recording";

  function getSubcategoryOptions(categoryName) {
    const normalized = normalizeTaxonomyName(categoryName);
    if (!normalized) return [];
    const match = taxonomyCategories.find(
      (category) => normalizeTaxonomyName(category.name) === normalized
    );
    return (match?.subcategories || []).map((subcategory) => subcategory.name);
  }

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    async function loadTaxonomy() {
      setTaxonomyLoading(true);
      setTaxonomyError("");
      try {
        const data = await fetchTaxonomy(token);
        if (!cancelled) {
          setTaxonomy(data);
        }
      } catch (err) {
        if (!cancelled) {
          setTaxonomyError(err.message);
        }
      } finally {
        if (!cancelled) {
          setTaxonomyLoading(false);
        }
      }
    }
    loadTaxonomy();
    return () => {
      cancelled = true;
    };
  }, [open, token]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        void handleAttemptClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, loading, confirming, quickAddVoiceTranscribing, quickAddVoiceRecording, text, drafts, result]);

  function resetModalState() {
    quickAddVoice.cancelRecording();
    quickAddVoice.clearError();
    setText("");
    setResult(null);
    setDrafts([]);
    setLoading(false);
    setConfirming(false);
    setConfirmKey("");
    setError("");
    setDiscardConfirmOpen(false);
  }

  function buildIdempotencyKey() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return `quick-add-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function updateDraft(index, field, value) {
    setDrafts((prev) =>
      prev.map((draft, currentIndex) => {
        if (currentIndex !== index) return draft;
        const next = { ...draft, [field]: value };
        if (field === "category") {
          const options = getSubcategoryOptions(value);
          if (
            next.subcategory &&
            !options.some(
              (subcategory) =>
                normalizeTaxonomyName(subcategory) === normalizeTaxonomyName(next.subcategory)
            )
          ) {
            next.subcategory = "";
          }
        }
        if (field === "subcategory" && !value) {
          next.subcategory = "";
        }
        return next;
      })
    );
  }

  async function handleParse() {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setConfirmKey("");
    try {
      const parsed = await parseExpenseText(token, text);
      setResult(parsed);
      setDrafts(parsed.expenses ?? []);
      setConfirmKey(buildIdempotencyKey());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveToLedger() {
    const confirmable = drafts.filter((draft) => draft.id);
    if (confirmable.length === 0) {
      setError("No confirmable draft entries found.");
      return;
    }

    setConfirming(true);
    setError("");
    try {
      const idempotencyKey = confirmKey || buildIdempotencyKey();
      if (!confirmKey) {
        setConfirmKey(idempotencyKey);
      }
      const data = await confirmExpenses(token, {
        idempotency_key: idempotencyKey,
        expenses: confirmable.map((draft) => ({
          draft_id: draft.id,
          amount:
            draft.amount === "" || draft.amount === null || draft.amount === undefined
              ? null
              : Number(draft.amount),
          currency: draft.currency || null,
          category: draft.category || null,
          subcategory: draft.subcategory || null,
          description: draft.description || null,
          merchant_or_item: draft.merchant_or_item || null,
          date_incurred: draft.date_incurred || null,
          is_recurring: Boolean(draft.is_recurring),
        })),
      });
      onNotify(`Quick Add saved ${data.confirmed_count} expense(s) to ledger.`);
      resetModalState();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setConfirming(false);
    }
  }

  function handleSendToCapture() {
    const captureText = text.trim();
    if (!captureText) {
      onNotify("Type your clarification first, then send to Add Expense.");
      return;
    }
    onRouteToCapture(captureText);
    onNotify("Moved to Add Expense for detailed review.");
    resetModalState();
    onClose();
  }

  async function handleAttemptClose() {
    if (loading || confirming || quickAddVoiceTranscribing) return;
    if (quickAddVoiceRecording) {
      quickAddVoice.cancelRecording();
    }
    const hasUnsavedWork = Boolean(text.trim() || drafts.length > 0 || result);
    if (hasUnsavedWork) {
      setDiscardConfirmOpen(true);
      return;
    }
    resetModalState();
    onClose();
  }

  if (!open) return null;

  return (
    <>
      <div
        className="quick-add-backdrop"
        role="presentation"
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            void handleAttemptClose();
          }
        }}
      >
        <section className="quick-add-modal" role="dialog" aria-modal="true" aria-label="Quick Add Expense">
          <div className="quick-add-header">
            <div>
              <h3>Quick Add</h3>
              <p className="hint">Log expenses instantly from any workspace tab.</p>
            </div>
            <button
              type="button"
              className="quick-add-close"
              onClick={() => void handleAttemptClose()}
              disabled={loading || confirming || quickAddVoiceTranscribing}
              aria-label="Close quick add"
            >
              &times;
            </button>
          </div>

          {taxonomyLoading && <p className="hint subtle-loader">Loading category options...</p>}
          {taxonomyError && <p className="form-error">{taxonomyError}</p>}
          {error && <p className="form-error">{error}</p>}
          <div className="stack">
            <div className="voice-textarea-wrap">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={4}
                placeholder={`Example: Paid ${RUPEE_SYMBOL}1200 for electricity yesterday and ${RUPEE_SYMBOL}300 for groceries`}
                autoFocus
              />
              <div className="voice-textarea-action">
                <VoiceTranscriptionControls voice={quickAddVoice} disabled={loading || confirming} />
              </div>
            </div>
            <VoiceTranscriptionFeedback voice={quickAddVoice} />
            <div className="quick-add-actions">
              <button
                className="btn-main"
                onClick={handleParse}
                disabled={loading || confirming || quickAddVoiceTranscribing}
              >
                {loading ? "Reading..." : "Create Drafts"}
              </button>
              {result?.needs_clarification && (
                <button
                  className="btn-ghost"
                  onClick={handleSendToCapture}
                  disabled={loading || confirming || quickAddVoiceTranscribing}
                >
                  Send to Add Expense
                </button>
              )}
            </div>
          </div>

          {loading && <p className="hint subtle-loader">Reading your expense note...</p>}

          {result && <ExpenseAssistantResponse result={result} compact />}

          {drafts.length > 0 && (
            <article className="result-card">
              <div className="row draft-header">
                <h4>Review Drafts</h4>
                  <button
                    className="btn-main"
                    onClick={handleSaveToLedger}
                    disabled={loading || confirming || quickAddVoiceTranscribing}
                  >
                    {confirming ? "Saving..." : "Save to Ledger"}
                  </button>
              </div>
              <div className="quick-add-drafts">
                {drafts.map((draft, index) => (
                  <article key={draft.id || index} className="expense-item editable">
                    <div className="row-grid">
                      <label>
                        Amount
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={draft.amount ?? ""}
                          onChange={(e) => updateDraft(index, "amount", e.target.value)}
                        />
                      </label>
                      <label>
                        Currency
                        <input
                          value={draft.currency || ""}
                          placeholder="INR"
                          onChange={(e) => updateDraft(index, "currency", e.target.value.toUpperCase())}
                        />
                      </label>
                      <label>
                        Category
                        <select
                          value={draft.category || ""}
                          onChange={(e) => updateDraft(index, "category", e.target.value)}
                        >
                          <option value="">Select category</option>
                          {draft.category &&
                            !taxonomyCategoryOptions.some(
                              (category) =>
                                normalizeTaxonomyName(category) === normalizeTaxonomyName(draft.category)
                            ) && <option value={draft.category}>{draft.category}</option>}
                          {taxonomyCategoryOptions.map((category) => (
                            <option key={category} value={category}>
                              {category}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Subcategory
                        <select
                          value={draft.subcategory || ""}
                          onChange={(e) => updateDraft(index, "subcategory", e.target.value)}
                          disabled={!draft.category}
                        >
                          <option value="">Select subcategory</option>
                          {draft.subcategory &&
                            !getSubcategoryOptions(draft.category).some(
                              (subcategory) =>
                                normalizeTaxonomyName(subcategory) ===
                                normalizeTaxonomyName(draft.subcategory)
                            ) && <option value={draft.subcategory}>{draft.subcategory}</option>}
                          {getSubcategoryOptions(draft.category).map((subcategory) => (
                            <option key={`${draft.category}-${subcategory}`} value={subcategory}>
                              {subcategory}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Date
                        <input
                          type="date"
                          value={draft.date_incurred || ""}
                          onChange={(e) => updateDraft(index, "date_incurred", e.target.value)}
                        />
                      </label>
                      <label>
                        Description
                        <input
                          value={draft.description || ""}
                          onChange={(e) => updateDraft(index, "description", e.target.value)}
                        />
                      </label>
                      <label>
                        Merchant / Item
                        <input
                          value={draft.merchant_or_item || ""}
                          onChange={(e) => updateDraft(index, "merchant_or_item", e.target.value)}
                        />
                      </label>
                    </div>
                    <label className="inline-toggle">
                      <input
                        type="checkbox"
                        checked={Boolean(draft.is_recurring)}
                        onChange={(e) => updateDraft(index, "is_recurring", e.target.checked)}
                      />
                      Recurring expense
                    </label>
                  </article>
                ))}
              </div>
            </article>
          )}
        </section>
      </div>

      <ConfirmModal
        open={discardConfirmOpen}
        title="Discard quick add draft?"
        description="You have unsaved quick-add changes. Do you want to discard them?"
        confirmLabel="Discard"
        onCancel={() => setDiscardConfirmOpen(false)}
        onConfirm={() => {
          setDiscardConfirmOpen(false);
          resetModalState();
          onClose();
        }}
      />
    </>
  );
}

function AuthCard({ onAuthSuccess }) {
  const [mode, setMode] = useState("register");
  const [registerForm, setRegisterForm] = useState(initialRegister);
  const [loginForm, setLoginForm] = useState(initialLogin);
  const [joinForm, setJoinForm] = useState(initialJoin);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data =
        mode === "register"
          ? await registerUser(registerForm)
          : mode === "login"
            ? await loginUser(loginForm)
            : await joinHousehold(joinForm);
      onAuthSuccess({
        token: data.token.access_token,
        user: data.user,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="auth-card">
      <div className="brand-slab">
        <p className="kicker">Household Finance</p>
        <h1>LedgerLoop</h1>
        <p className="sub">
          Describe spend in natural language, review smart drafts, then save clean expense
          records for your household.
        </p>
        <div className="hero-visual" aria-hidden="true">
          <article className="mini-invoice">
            <p className="tiny">Household Balance</p>
            <strong>{`${RUPEE_SYMBOL}18,765.40`}</strong>
            <small>Updated today</small>
            <div className="invoice-row">
              <span>Auto categories</span>
              <span>Enabled</span>
            </div>
          </article>
          <article className="credit-panel">
            <p className="tiny">Global Currencies</p>
            <div className="currency-chip-row">
              {GLOBAL_CURRENCY_OPTIONS.map((currency) => (
                <span className="currency-chip" key={currency.code} title={`${currency.name} (${currency.code})`}>
                  <span>{currency.symbol}</span>
                  <code>{currency.code}</code>
                </span>
              ))}
            </div>
          </article>
        </div>
        <div className="logo-strip" aria-hidden="true">
          <span>Smart capture</span>
          <span>Household ledger</span>
          <span>Cross-currency</span>
        </div>
      </div>
      <div className="auth-panel">
        <div className="mode-switch">
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
            type="button"
          >
            Register
          </button>
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
            type="button"
          >
            Login
          </button>
          <button
            className={mode === "join" ? "active" : ""}
            onClick={() => setMode("join")}
            type="button"
          >
            Join
          </button>
        </div>
        <form onSubmit={handleSubmit} className="stack">
          {mode === "register" && (
            <>
              <label>
                Full Name
                <input
                  required
                  value={registerForm.full_name}
                  onChange={(e) =>
                    setRegisterForm((prev) => ({ ...prev, full_name: e.target.value }))
                  }
                />
              </label>
              <label>
                Household Name
                <input
                  required
                  value={registerForm.household_name}
                  onChange={(e) =>
                    setRegisterForm((prev) => ({
                      ...prev,
                      household_name: e.target.value,
                    }))
                  }
                />
              </label>
              <label>
                Email
                <input
                  required
                  type="email"
                  value={registerForm.email}
                  onChange={(e) =>
                    setRegisterForm((prev) => ({ ...prev, email: e.target.value }))
                  }
                />
              </label>
              <label>
                Password
                <input
                  required
                  minLength={8}
                  type="password"
                  value={registerForm.password}
                  onChange={(e) =>
                    setRegisterForm((prev) => ({ ...prev, password: e.target.value }))
                  }
                />
              </label>
            </>
          )}

          {mode === "login" && (
            <>
              <label>
                Email
                <input
                  required
                  type="email"
                  value={loginForm.email}
                  onChange={(e) =>
                    setLoginForm((prev) => ({ ...prev, email: e.target.value }))
                  }
                />
              </label>
              <label>
                Password
                <input
                  required
                  minLength={8}
                  type="password"
                  value={loginForm.password}
                  onChange={(e) =>
                    setLoginForm((prev) => ({ ...prev, password: e.target.value }))
                  }
                />
              </label>
            </>
          )}
          {mode === "join" && (
            <>
              <label>
                Full Name
                <input
                  required
                  value={joinForm.full_name}
                  onChange={(e) =>
                    setJoinForm((prev) => ({ ...prev, full_name: e.target.value }))
                  }
                />
              </label>
              <label>
                Invite Code
                <input
                  required
                  value={joinForm.invite_code}
                  onChange={(e) =>
                    setJoinForm((prev) => ({
                      ...prev,
                      invite_code: e.target.value.toUpperCase(),
                    }))
                  }
                />
              </label>
              <label>
                Email
                <input
                  required
                  type="email"
                  value={joinForm.email}
                  onChange={(e) =>
                    setJoinForm((prev) => ({ ...prev, email: e.target.value }))
                  }
                />
              </label>
              <label>
                Password
                <input
                  required
                  minLength={8}
                  type="password"
                  value={joinForm.password}
                  onChange={(e) =>
                    setJoinForm((prev) => ({ ...prev, password: e.target.value }))
                  }
                />
              </label>
            </>
          )}
          <button className="btn-main" disabled={loading} type="submit">
            {loading
              ? "Please wait..."
              : mode === "register"
                ? "Create Account"
                : mode === "login"
                  ? "Sign In"
                  : "Join Household"}
          </button>
          {error && <p className="form-error">{error}</p>}
        </form>
      </div>
    </section>
  );
}

function ExpenseLogPanel({ token, prefilledText, onPrefilledTextConsumed }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmResult, setConfirmResult] = useState(null);
  const [confirmKey, setConfirmKey] = useState("");
  const [error, setError] = useState("");
  const [taxonomy, setTaxonomy] = useState({ categories: [] });
  const [taxonomyLoading, setTaxonomyLoading] = useState(false);
  const [taxonomyError, setTaxonomyError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function loadTaxonomy() {
      setTaxonomyLoading(true);
      setTaxonomyError("");
      try {
        const data = await fetchTaxonomy(token);
        if (!cancelled) {
          setTaxonomy(data);
        }
      } catch (err) {
        if (!cancelled) {
          setTaxonomyError(err.message);
        }
      } finally {
        if (!cancelled) {
          setTaxonomyLoading(false);
        }
      }
    }
    loadTaxonomy();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    const incoming = String(prefilledText || "").trim();
    if (!incoming) return;
    setText(incoming);
    setResult(null);
    setDrafts([]);
    setConfirmResult(null);
    setConfirmKey("");
    setError("");
    if (typeof onPrefilledTextConsumed === "function") {
      onPrefilledTextConsumed();
    }
  }, [prefilledText]);

  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );
  const taxonomyCategoryOptions = useMemo(
    () => taxonomyCategories.map((category) => category.name),
    [taxonomyCategories]
  );
  const captureVoice = useVoiceTranscription({
    token,
    onTranscript: (transcript) => {
      setText((previous) => appendVoiceTranscript(previous, transcript));
      setError("");
    },
  });
  const captureVoiceTranscribing = captureVoice.status === "transcribing";

  function getSubcategoryOptions(categoryName) {
    const normalized = normalizeTaxonomyName(categoryName);
    if (!normalized) return [];
    const match = taxonomyCategories.find(
      (category) => normalizeTaxonomyName(category.name) === normalized
    );
    return (match?.subcategories || []).map((subcategory) => subcategory.name);
  }

  async function handleParse() {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setConfirmResult(null);
    setConfirmKey("");
    try {
      const parsed = await parseExpenseText(token, text);
      setResult(parsed);
      setDrafts(parsed.expenses ?? []);
      setConfirmKey(buildIdempotencyKey());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function updateDraft(index, field, value) {
    setDrafts((prev) => {
      return prev.map((draft, currentIndex) => {
        if (currentIndex !== index) return draft;
        const next = { ...draft, [field]: value };

        if (field === "category") {
          const options = getSubcategoryOptions(value);
          if (
            next.subcategory &&
            !options.some(
              (subcategory) =>
                normalizeTaxonomyName(subcategory) === normalizeTaxonomyName(next.subcategory)
            )
          ) {
            next.subcategory = "";
          }
        }

        if (field === "subcategory" && !value) {
          next.subcategory = "";
        }

        return next;
      });
    });
  }

  function buildIdempotencyKey() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return `confirm-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function handleConfirm() {
    const confirmable = drafts.filter((draft) => draft.id);
    if (confirmable.length === 0) return;

    setConfirming(true);
    setError("");
    setConfirmResult(null);
    try {
      const idempotencyKey = confirmKey || buildIdempotencyKey();
      if (!confirmKey) {
        setConfirmKey(idempotencyKey);
      }
      const data = await confirmExpenses(token, {
        idempotency_key: idempotencyKey,
        expenses: confirmable.map((draft) => ({
          draft_id: draft.id,
          amount:
            draft.amount === "" || draft.amount === null || draft.amount === undefined
              ? null
              : Number(draft.amount),
          currency: draft.currency || null,
          category: draft.category || null,
          subcategory: draft.subcategory || null,
          description: draft.description || null,
          merchant_or_item: draft.merchant_or_item || null,
          date_incurred: draft.date_incurred || null,
          is_recurring: Boolean(draft.is_recurring),
        })),
      });
      setConfirmResult(data);
      setDrafts(data.expenses ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setConfirming(false);
    }
  }

  return (
    <section className="panel">
      <p className="hint">
        Describe spending naturally and we'll turn it into expense drafts you can edit before saving.
      </p>
      {taxonomyLoading && <p className="hint">Loading household taxonomy...</p>}
      {taxonomyError && <p className="form-error">{taxonomyError}</p>}
      <div className="stack">
        <div className="voice-textarea-wrap">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder={`Example: Bought groceries for ${RUPEE_SYMBOL}500 and paid ${RUPEE_SYMBOL}1200 for electricity yesterday`}
          />
          <div className="voice-textarea-action">
            <VoiceTranscriptionControls voice={captureVoice} disabled={loading || confirming} />
          </div>
        </div>
        <VoiceTranscriptionFeedback voice={captureVoice} />
        <button className="btn-main" onClick={handleParse} disabled={loading || captureVoiceTranscribing}>
          {loading ? "Preparing..." : "Create Drafts"}
        </button>
      </div>
      {loading && <p className="hint subtle-loader">Preparing your expense draft...</p>}
      {error && <p className="form-error">{error}</p>}

      {result && <ExpenseAssistantResponse result={result} showMode />}

      {drafts.length > 0 && (
        <div className="result-card draft-editor">
          <div className="row draft-header">
            <h3>Review Drafts</h3>
            <button className="btn-main" onClick={handleConfirm} disabled={confirming}>
              {confirming ? "Saving..." : "Save to Ledger"}
            </button>
          </div>
          {drafts.map((draft, idx) => (
            <article key={draft.id || idx} className="expense-item editable">
              <div className="row-grid">
                <label>
                  Amount
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={draft.amount ?? ""}
                    onChange={(e) => updateDraft(idx, "amount", e.target.value)}
                  />
                </label>
                <label>
                  Currency
                  <input
                    value={draft.currency || ""}
                    placeholder="INR"
                    onChange={(e) => updateDraft(idx, "currency", e.target.value.toUpperCase())}
                  />
                </label>
                <label>
                  Category
                  <select
                    value={draft.category || ""}
                    onChange={(e) => updateDraft(idx, "category", e.target.value)}
                  >
                    <option value="">Select category</option>
                    {draft.category &&
                      !taxonomyCategoryOptions.some(
                        (category) =>
                          normalizeTaxonomyName(category) ===
                          normalizeTaxonomyName(draft.category)
                      ) && <option value={draft.category}>{draft.category}</option>}
                    {taxonomyCategoryOptions.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Subcategory
                  <select
                    value={draft.subcategory || ""}
                    onChange={(e) => updateDraft(idx, "subcategory", e.target.value)}
                    disabled={!draft.category}
                  >
                    <option value="">Select subcategory</option>
                    {draft.subcategory &&
                      !getSubcategoryOptions(draft.category).some(
                        (subcategory) =>
                          normalizeTaxonomyName(subcategory) ===
                          normalizeTaxonomyName(draft.subcategory)
                      ) && <option value={draft.subcategory}>{draft.subcategory}</option>}
                    {getSubcategoryOptions(draft.category).map((subcategory) => (
                      <option key={`${draft.category}-${subcategory}`} value={subcategory}>
                        {subcategory}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Date
                  <input
                    type="date"
                    value={draft.date_incurred || ""}
                    onChange={(e) => updateDraft(idx, "date_incurred", e.target.value)}
                  />
                </label>
                <label>
                  Description
                  <input
                    value={draft.description || ""}
                    onChange={(e) => updateDraft(idx, "description", e.target.value)}
                  />
                </label>
                <label>
                  Merchant / Item
                  <input
                    value={draft.merchant_or_item || ""}
                    onChange={(e) => updateDraft(idx, "merchant_or_item", e.target.value)}
                  />
                </label>
              </div>
              <label className="inline-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(draft.is_recurring)}
                  onChange={(e) => updateDraft(idx, "is_recurring", e.target.checked)}
                />
                Recurring expense
              </label>
            </article>
          ))}
          {confirmResult && (
            <>
              <p className="form-ok">
                Saved {confirmResult.confirmed_count} expense(s) to ledger
                {confirmResult.idempotent_replay ? " (idempotent replay)." : "."}
              </p>
              {Array.isArray(confirmResult.warnings) && confirmResult.warnings.length > 0 && (
                <ul className="taxonomy-warnings">
                  {confirmResult.warnings.map((warning, index) => (
                    <li key={`${warning}-${index}`}>{warning}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

function HouseholdPanel({ token, user }) {
  const [household, setHousehold] = useState(null);
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [deletingMemberId, setDeletingMemberId] = useState(null);
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadPeopleData() {
    setLoading(true);
    setError("");
    try {
      const [householdData, feedData] = await Promise.all([
        fetchHousehold(token),
        fetchExpenseFeed(token, { status: "confirmed", limit: 100 }),
      ]);
      setHousehold(householdData);
      setFeed(feedData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPeopleData();
  }, [token]);

  const userBoard = useMemo(() => {
    if (!feed?.items?.length) return [];
    const map = new Map();
    for (const item of feed.items) {
      const current = map.get(item.logged_by_name) || { count: 0, total: 0 };
      current.count += 1;
      current.total += Number(item.amount || 0);
      map.set(item.logged_by_name, current);
    }
    return Array.from(map.entries())
      .map(([name, value]) => ({
        name,
        count: value.count,
        total: value.total,
      }))
      .sort((a, b) => b.total - a.total);
  }, [feed]);

  async function handleGenerateInvite() {
    setInviteBusy(true);
    setError("");
    setMessage("");
    try {
      const data = await createInviteCode(token);
      setMessage(`New invite code: ${data.invite_code}`);
      await loadPeopleData();
    } catch (err) {
      setError(err.message);
    } finally {
      setInviteBusy(false);
    }
  }

  async function handleConfirmMemberRemoval() {
    if (!memberToRemove) return;

    setDeletingMemberId(memberToRemove.id);
    setError("");
    setMessage("");
    try {
      const data = await deleteHouseholdMember(token, memberToRemove.id);
      setMessage(data.message);
      setMemberToRemove(null);
      await loadPeopleData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingMemberId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-action-row">
        <button className="btn-ghost" type="button" onClick={loadPeopleData} disabled={loading}>
          Refresh
        </button>
      </div>
      <p className="hint">
        Invite members and manage access. Everyone in this household can see who logged each expense.
      </p>

      {loading && <PanelSkeleton rows={6} />}
      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-ok">{message}</p>}

      {household && !loading && (
        <>
          <div className="stats-grid">
            <article className="stat-card">
              <p className="kicker">Household</p>
              <h3>{household.household_name}</h3>
              <p className="metric-sub">{household.members.length} member(s)</p>
            </article>
            <article className="stat-card">
              <p className="kicker">Your Role</p>
              <h3>{user?.role || "member"}</h3>
              <p className="metric-sub">Logged in as {user?.full_name}</p>
            </article>
            <article className="stat-card">
              <p className="kicker">Confirmed Entries</p>
              <h3>{feed?.items?.length || 0}</h3>
              <p className="metric-sub">of {feed?.total_count || 0} visible</p>
            </article>
          </div>

          <div className="result-grid dashboard-grid">
            <article className="result-card">
              <div className="row draft-header">
                <h3>Invite</h3>
                {user?.role === "admin" && (
                  <button
                    className="btn-main"
                    type="button"
                    onClick={handleGenerateInvite}
                    disabled={inviteBusy}
                  >
                    {inviteBusy ? "Generating..." : "Generate New Code"}
                  </button>
                )}
              </div>
              {user?.role === "admin" ? (
                <>
                  <p className="hint">Share this code with a member to join this household.</p>
                  <p className="invite-code">{household.invite_code || "No code yet"}</p>
                </>
              ) : (
                <p className="hint">Only admin can generate invite code.</p>
              )}
            </article>

            <article className="result-card">
              <h3>Members</h3>
              <div className="member-list">
                {household.members.map((member) => (
                  <div className="member-row" key={member.id}>
                    <div>
                      <strong>{member.full_name}</strong>
                      <p className="hint">{member.email}</p>
                    </div>
                    <div className="member-actions">
                      <span className="tool-chip">{member.role}</span>
                      {user?.role === "admin" && member.role !== "admin" && (
                        <button
                          className="btn-danger"
                          type="button"
                          onClick={() => setMemberToRemove(member)}
                          disabled={deletingMemberId === member.id}
                        >
                          {deletingMemberId === member.id ? "Removing..." : "Remove Access"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="result-card">
              <h3>Spend by Person</h3>
              {userBoard.length === 0 ? (
                <p>No confirmed entries yet.</p>
              ) : (
                <div className="bar-list">
                  {userBoard.map((item) => (
                    <div className="bar-row" key={item.name}>
                      <span>{item.name}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill dark"
                          style={{
                            width: `${Math.max((item.total / Math.max(userBoard[0].total, 1)) * 100, 2)}%`,
                          }}
                        />
                      </div>
                      <strong>{formatCurrencyValue(item.total)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </>
      )}

      <ConfirmModal
        open={Boolean(memberToRemove)}
        title="Remove member access?"
        description={
          memberToRemove
            ? `Remove ${memberToRemove.full_name} (${memberToRemove.email}) from this household? Their past expenses will remain in the ledger.`
            : ""
        }
        confirmLabel="Remove Access"
        busy={Boolean(memberToRemove && deletingMemberId === memberToRemove.id)}
        onCancel={() => setMemberToRemove(null)}
        onConfirm={handleConfirmMemberRemoval}
      />
    </section>
  );
}

function RecurringPanel({ token, user }) {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingExpenseId, setDeletingExpenseId] = useState(null);
  const [expenseToDelete, setExpenseToDelete] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState([]);
  const [form, setForm] = useState({
    amount: "",
    currency: "INR",
    category: "",
    subcategory: "",
    description: "",
    merchant_or_item: "",
    date_incurred: todayIsoDate(),
  });

  async function loadRecurringData() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchExpenseFeed(token, {
        status: "confirmed",
        limit: 300,
        recurringOnly: true,
      });
      setFeed(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRecurringData();
  }, [token]);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => {
      setMessage("");
    }, 2800);
    return () => clearTimeout(timer);
  }, [message]);

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleAddRecurringExpense() {
    const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Please enter a valid amount greater than zero.");
      return;
    }

    setSaving(true);
    setError("");
    setMessage("");
    setWarnings([]);
    try {
      const data = await createRecurringExpense(token, {
        amount,
        currency: String(form.currency || "").trim().toUpperCase() || "INR",
        category: form.category || null,
        subcategory: form.subcategory || null,
        description: form.description || null,
        merchant_or_item: form.merchant_or_item || null,
        date_incurred: form.date_incurred || null,
      });
      setMessage(data.message || "Recurring expense added.");
      setWarnings(Array.isArray(data.warnings) ? data.warnings : []);
      setForm((prev) => ({
        ...prev,
        amount: "",
        description: "",
        merchant_or_item: "",
        date_incurred: todayIsoDate(),
      }));
      await loadRecurringData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteExpense() {
    if (!expenseToDelete) return;
    setDeletingExpenseId(expenseToDelete.id);
    setError("");
    setMessage("");
    try {
      const data = await deleteExpense(token, expenseToDelete.id);
      setMessage(data.message || "Expense deleted.");
      setExpenseToDelete(null);
      await loadRecurringData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingExpenseId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-action-row">
        <button className="btn-ghost" type="button" onClick={loadRecurringData} disabled={loading}>
          Refresh
        </button>
      </div>
      <p className="hint">Track monthly bills like rent, school fees, subscriptions, and other repeat spends.</p>
      {error && <p className="form-error">{error}</p>}
      {warnings.length > 0 && (
        <ul className="taxonomy-warnings">
          {warnings.map((warning, index) => (
            <li key={`${warning}-${index}`}>{warning}</li>
          ))}
        </ul>
      )}

      <article className="result-card recurring-entry-card">
        <div className="row draft-header">
          <h3>Add Recurring Expense</h3>
          <button className="btn-main" type="button" onClick={handleAddRecurringExpense} disabled={saving}>
            {saving ? "Adding..." : "Add Recurring"}
          </button>
        </div>
        <div className="row-grid recurring-form-grid">
          <label>
            Amount
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.amount}
              onChange={(e) => updateForm("amount", e.target.value)}
              placeholder="0.00"
            />
          </label>
          <label>
            Currency
            <input
              value={form.currency}
              onChange={(e) => updateForm("currency", e.target.value.toUpperCase())}
              placeholder="INR"
            />
          </label>
          <label>
            Date
            <input
              type="date"
              value={form.date_incurred}
              onChange={(e) => updateForm("date_incurred", e.target.value)}
            />
          </label>
          <label>
            Category
            <input
              value={form.category}
              onChange={(e) => updateForm("category", e.target.value)}
              placeholder="Rent, School Fees, Utilities"
            />
          </label>
          <label>
            Subcategory
            <input
              value={form.subcategory}
              onChange={(e) => updateForm("subcategory", e.target.value)}
              placeholder="Optional"
            />
          </label>
          <label>
            Description
            <input
              value={form.description}
              onChange={(e) => updateForm("description", e.target.value)}
              placeholder="Monthly rent"
            />
          </label>
          <label>
            Merchant / Item
            <input
              value={form.merchant_or_item}
              onChange={(e) => updateForm("merchant_or_item", e.target.value)}
              placeholder="Landlord / School"
            />
          </label>
        </div>
        <label className="inline-toggle">
          <input type="checkbox" checked readOnly disabled />
          Recurring expense
        </label>
      </article>

      {loading ? (
        <PanelSkeleton rows={7} />
      ) : (
        <article className="result-card household-ledger">
          <div className="row draft-header">
            <h3>Marked Recurring</h3>
            <p className="hint">Total: {feed?.total_count ?? 0}</p>
          </div>
          {!feed?.items?.length ? (
            <EmptyState
              title="No recurring expenses yet"
              description="Mark recurring bills in Ledger to keep this list up to date."
              actionLabel="Refresh"
              onAction={loadRecurringData}
            />
          ) : (
            <>
              <div className="table-wrap desktop-table-only">
                <table className="analytics-table recurring-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Logged By</th>
                      <th>Category</th>
                      <th>Description</th>
                      <th>Amount</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feed.items.map((item) => {
                      const canDelete = user?.role === "admin" || item.logged_by_user_id === user?.id;
                      return (
                        <tr key={item.id}>
                          <td>{formatDateValue(item.date_incurred)}</td>
                          <td>{item.logged_by_name}</td>
                          <td>{item.category || "Other"}</td>
                          <td>{item.description || item.merchant_or_item || "-"}</td>
                          <td>{formatCurrencyValue(item.amount, item.currency)}</td>
                          <td>
                            {canDelete && (
                              <button
                                type="button"
                                className="icon-delete-button"
                                onClick={() => setExpenseToDelete(item)}
                                aria-label={`Delete recurring expense on ${formatDateValue(item.date_incurred)}`}
                                title="Delete recurring expense"
                                disabled={deletingExpenseId === item.id}
                              >
                                <TrashIcon />
                                <span className="sr-only">Delete recurring expense</span>
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mobile-data-list mobile-cards-only">
                {feed.items.map((item) => {
                  const canDelete = user?.role === "admin" || item.logged_by_user_id === user?.id;
                  return (
                    <article className="mobile-data-card" key={`recurring-mobile-${item.id}`}>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Date</span>
                        <strong className="mobile-data-value">{formatDateValue(item.date_incurred)}</strong>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Logged By</span>
                        <span className="mobile-data-value">{item.logged_by_name}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Category</span>
                        <span className="mobile-data-value">{item.category || "Other"}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Description</span>
                        <span className="mobile-data-value">{item.description || item.merchant_or_item || "-"}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Amount</span>
                        <strong className="mobile-data-value">
                          {formatCurrencyValue(item.amount, item.currency)}
                        </strong>
                      </div>
                      {canDelete && (
                        <div className="mobile-data-actions">
                          <button
                            type="button"
                            className="icon-delete-button"
                            onClick={() => setExpenseToDelete(item)}
                            aria-label={`Delete recurring expense on ${formatDateValue(item.date_incurred)}`}
                            title="Delete recurring expense"
                            disabled={deletingExpenseId === item.id}
                          >
                            <TrashIcon />
                            <span className="sr-only">Delete recurring expense</span>
                          </button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </article>
      )}

      <ConfirmModal
        open={Boolean(expenseToDelete)}
        title="Delete this recurring expense?"
        description={
          expenseToDelete
            ? `Delete recurring expense on ${formatDateValue(expenseToDelete.date_incurred)} for ${formatCurrencyValue(
                expenseToDelete.amount,
                expenseToDelete.currency
              )}?`
            : ""
        }
        confirmLabel="Delete Expense"
        busy={Boolean(expenseToDelete && deletingExpenseId === expenseToDelete.id)}
        onCancel={() => setExpenseToDelete(null)}
        onConfirm={handleDeleteExpense}
      />
      <ToastNotice message={message} />
    </section>
  );
}

function LedgerPanel({ token, user }) {
  const [feed, setFeed] = useState(null);
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [loading, setLoading] = useState(false);
  const [deletingExpenseId, setDeletingExpenseId] = useState(null);
  const [updatingRecurringId, setUpdatingRecurringId] = useState(null);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [expenseToDelete, setExpenseToDelete] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadLedgerData() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchExpenseFeed(token, { status: statusFilter, limit: 200 });
      setFeed(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLedgerData();
  }, [statusFilter, token]);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => {
      setMessage("");
    }, 2800);
    return () => clearTimeout(timer);
  }, [message]);

  async function handleDownloadCsv() {
    setDownloadingCsv(true);
    setError("");
    setMessage("");
    try {
      await downloadExpenseCsv(token, { status: statusFilter });
      setMessage("CSV download started.");
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloadingCsv(false);
    }
  }

  async function handleDeleteExpense() {
    if (!expenseToDelete) return;
    setDeletingExpenseId(expenseToDelete.id);
    setError("");
    setMessage("");
    try {
      const data = await deleteExpense(token, expenseToDelete.id);
      setMessage(data.message || "Expense deleted.");
      setExpenseToDelete(null);
      await loadLedgerData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingExpenseId(null);
    }
  }

  async function handleToggleRecurring(item, nextValue) {
    setUpdatingRecurringId(item.id);
    setError("");
    setMessage("");
    try {
      const data = await updateExpenseRecurring(token, item.id, nextValue);
      setMessage(data.message || "Recurring status updated.");
      await loadLedgerData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingRecurringId(null);
    }
  }

  return (
    <section className="panel">
      <p className="hint">Manage and review your recent household expenses.</p>
      {error && <p className="form-error">{error}</p>}

      {loading ? (
        <PanelSkeleton rows={7} />
      ) : (
        <article className="result-card household-ledger">
          <div className="ledger-toolbar">
            <div className="ledger-toolbar-left">
              <label className="ledger-toolbar-label">
                Status
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="confirmed">Confirmed</option>
                  <option value="draft">Draft</option>
                  <option value="all">All</option>
                </select>
              </label>
            </div>
            <div className="ledger-toolbar-right">
              <button className="btn-ghost" type="button" onClick={loadLedgerData} disabled={loading}>
                Refresh
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={handleDownloadCsv}
                disabled={downloadingCsv}
              >
                {downloadingCsv ? "Downloading..." : "Download CSV"}
              </button>
            </div>
          </div>
          {!feed?.items?.length ? (
            <EmptyState
              title="No expenses in this view"
              description={
                statusFilter === "all"
                  ? "Capture a new expense from Add Expense, then come back to review it here."
                  : `No ${statusFilter} expenses yet.`
              }
              actionLabel={statusFilter === "all" ? "Refresh" : "Show all expenses"}
              onAction={statusFilter === "all" ? loadLedgerData : () => setStatusFilter("all")}
            />
          ) : (
            <>
              <div className="table-wrap desktop-table-only">
                <table className="analytics-table ledger-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Logged By</th>
                      <th>Category</th>
                      <th>Subcategory</th>
                      <th>Description</th>
                      <th>Amount</th>
                      <th>Recurring</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feed.items.map((item) => {
                      const canDelete = user?.role === "admin" || item.logged_by_user_id === user?.id;
                      return (
                        <tr key={item.id}>
                          <td>{formatDateValue(item.date_incurred)}</td>
                          <td>{item.logged_by_name}</td>
                          <td>{item.category || "Other"}</td>
                          <td>
                            {item.subcategory ? item.subcategory : <span className="empty-value">-</span>}
                          </td>
                          <td>{item.description || item.merchant_or_item || "-"}</td>
                          <td>{formatCurrencyValue(item.amount, item.currency)}</td>
                          <td>
                            <RecurringSwitch
                              checked={Boolean(item.is_recurring)}
                              disabled={updatingRecurringId === item.id}
                              onToggle={(nextValue) => handleToggleRecurring(item, nextValue)}
                              label={`Toggle recurring for expense on ${formatDateValue(item.date_incurred)}`}
                            />
                          </td>
                          <td>
                            <StatusPill status={item.status} />
                          </td>
                          <td>
                            {canDelete && (
                              <button
                                type="button"
                                className="icon-delete-button"
                                onClick={() => setExpenseToDelete(item)}
                                aria-label={`Delete expense on ${formatDateValue(item.date_incurred)}`}
                                title="Delete expense"
                                disabled={deletingExpenseId === item.id}
                              >
                                <TrashIcon />
                                <span className="sr-only">Delete expense</span>
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mobile-data-list mobile-cards-only">
                {feed.items.map((item) => {
                  const canDelete = user?.role === "admin" || item.logged_by_user_id === user?.id;
                  return (
                    <article className="mobile-data-card" key={`mobile-${item.id}`}>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Date</span>
                        <strong className="mobile-data-value">{formatDateValue(item.date_incurred)}</strong>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Logged By</span>
                        <span className="mobile-data-value">{item.logged_by_name}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Category</span>
                        <span className="mobile-data-value">{item.category || "Other"}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Subcategory</span>
                        <span className="mobile-data-value">
                          {item.subcategory ? item.subcategory : <span className="empty-value">-</span>}
                        </span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Description</span>
                        <span className="mobile-data-value">{item.description || item.merchant_or_item || "-"}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Amount</span>
                        <strong className="mobile-data-value">
                          {formatCurrencyValue(item.amount, item.currency)}
                        </strong>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Recurring</span>
                        <span className="mobile-data-value">
                          <RecurringSwitch
                            checked={Boolean(item.is_recurring)}
                            disabled={updatingRecurringId === item.id}
                            onToggle={(nextValue) => handleToggleRecurring(item, nextValue)}
                            label={`Toggle recurring for expense on ${formatDateValue(item.date_incurred)}`}
                          />
                        </span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Status</span>
                        <span className="mobile-data-value">
                          <StatusPill status={item.status} />
                        </span>
                      </div>
                      {canDelete && (
                        <div className="mobile-data-actions">
                          <button
                            type="button"
                            className="icon-delete-button"
                            onClick={() => setExpenseToDelete(item)}
                            aria-label={`Delete expense on ${formatDateValue(item.date_incurred)}`}
                            title="Delete expense"
                            disabled={deletingExpenseId === item.id}
                          >
                            <TrashIcon />
                            <span className="sr-only">Delete expense</span>
                          </button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </article>
      )}

      <ConfirmModal
        open={Boolean(expenseToDelete)}
        title="Delete this expense?"
        description={
          expenseToDelete
            ? `Delete expense on ${formatDateValue(expenseToDelete.date_incurred)} for ${formatCurrencyValue(
                expenseToDelete.amount,
                expenseToDelete.currency
              )}?`
            : ""
        }
        confirmLabel="Delete Expense"
        busy={Boolean(expenseToDelete && deletingExpenseId === expenseToDelete.id)}
        onCancel={() => setExpenseToDelete(null)}
        onConfirm={handleDeleteExpense}
      />
      <ToastNotice message={message} />
    </section>
  );
}

function SettingsPanel({ token, user }) {
  const [taxonomy, setTaxonomy] = useState({ categories: [] });
  const [loading, setLoading] = useState(false);
  const [taxonomyBusy, setTaxonomyBusy] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newSubcategoryByCategory, setNewSubcategoryByCategory] = useState({});
  const [editingCategoryId, setEditingCategoryId] = useState(null);
  const [editingCategoryName, setEditingCategoryName] = useState("");
  const [editingSubcategoryId, setEditingSubcategoryId] = useState(null);
  const [editingSubcategoryName, setEditingSubcategoryName] = useState("");
  const [deactivateTarget, setDeactivateTarget] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const isAdmin = user?.role === "admin";

  async function loadTaxonomyData() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchTaxonomy(token);
      setTaxonomy(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTaxonomyData();
  }, [token]);

  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );

  function updateSubcategoryInput(categoryId, value) {
    setNewSubcategoryByCategory((prev) => ({ ...prev, [categoryId]: value }));
  }

  async function handleCreateCategory() {
    const name = newCategoryName.trim();
    if (!name || !isAdmin) return;
    setTaxonomyBusy(true);
    setError("");
    setMessage("");
    try {
      const data = await createTaxonomyCategory(token, { name });
      setTaxonomy(data);
      setNewCategoryName("");
      setMessage(`Added category "${name}".`);
    } catch (err) {
      setError(err.message);
    } finally {
      setTaxonomyBusy(false);
    }
  }

  function startCategoryRename(category) {
    if (!isAdmin || taxonomyBusy) return;
    setEditingSubcategoryId(null);
    setEditingSubcategoryName("");
    setEditingCategoryId(category.id);
    setEditingCategoryName(category.name);
  }

  function cancelCategoryRename() {
    setEditingCategoryId(null);
    setEditingCategoryName("");
  }

  async function saveCategoryRename(category) {
    if (!isAdmin || taxonomyBusy || editingCategoryId !== category.id) return;
    const nextName = editingCategoryName.trim();
    if (!nextName) {
      setError("Category name cannot be empty.");
      return;
    }
    if (nextName === category.name) {
      cancelCategoryRename();
      return;
    }
    setTaxonomyBusy(true);
    setError("");
    setMessage("");
    try {
      const data = await updateTaxonomyCategory(token, category.id, { name: nextName });
      setTaxonomy(data);
      cancelCategoryRename();
      setMessage(`Renamed category to "${nextName.trim()}".`);
    } catch (err) {
      setError(err.message);
    } finally {
      setTaxonomyBusy(false);
    }
  }

  async function handleCreateSubcategory(category) {
    if (!isAdmin) return;
    const name = String(newSubcategoryByCategory[category.id] || "").trim();
    if (!name) return;
    setTaxonomyBusy(true);
    setError("");
    setMessage("");
    try {
      const data = await createTaxonomySubcategory(token, category.id, { name });
      setTaxonomy(data);
      updateSubcategoryInput(category.id, "");
      setMessage(`Added subcategory "${name}" under "${category.name}".`);
    } catch (err) {
      setError(err.message);
    } finally {
      setTaxonomyBusy(false);
    }
  }

  function startSubcategoryRename(category, subcategory) {
    if (!isAdmin || taxonomyBusy) return;
    setEditingCategoryId(null);
    setEditingCategoryName("");
    setEditingSubcategoryId(subcategory.id);
    setEditingSubcategoryName(subcategory.name);
  }

  function cancelSubcategoryRename() {
    setEditingSubcategoryId(null);
    setEditingSubcategoryName("");
  }

  async function saveSubcategoryRename(category, subcategory) {
    if (!isAdmin || taxonomyBusy || editingSubcategoryId !== subcategory.id) return;
    const nextName = editingSubcategoryName.trim();
    if (!nextName) {
      setError("Subcategory name cannot be empty.");
      return;
    }
    if (nextName === subcategory.name) {
      cancelSubcategoryRename();
      return;
    }
    setTaxonomyBusy(true);
    setError("");
    setMessage("");
    try {
      const data = await updateTaxonomySubcategory(token, subcategory.id, { name: nextName });
      setTaxonomy(data);
      cancelSubcategoryRename();
      setMessage(`Renamed subcategory to "${nextName.trim()}" under "${category.name}".`);
    } catch (err) {
      setError(err.message);
    } finally {
      setTaxonomyBusy(false);
    }
  }

  async function handleConfirmDeactivate() {
    if (!deactivateTarget || !isAdmin) return;
    setTaxonomyBusy(true);
    setError("");
    setMessage("");
    try {
      let data;
      if (deactivateTarget.type === "category") {
        data = await deleteTaxonomyCategory(token, deactivateTarget.category.id);
        setMessage(`Deactivated category "${deactivateTarget.category.name}".`);
      } else {
        data = await deleteTaxonomySubcategory(token, deactivateTarget.subcategory.id);
        setMessage(`Deactivated subcategory "${deactivateTarget.subcategory.name}".`);
      }
      setTaxonomy(data);
      setDeactivateTarget(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setTaxonomyBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="dashboard-header">
        <h2>Settings</h2>
        <button
          className="btn-ghost"
          type="button"
          onClick={loadTaxonomyData}
          disabled={loading || taxonomyBusy}
        >
          Refresh
        </button>
      </div>
      <p className="hint">Configure categories used during AI expense capture and review.</p>
      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-ok">{message}</p>}

      {loading ? (
        <PanelSkeleton rows={6} />
      ) : !isAdmin ? (
        <article className="result-card">
          <h3>Categories & Subcategories</h3>
          <p className="hint">Only admin can manage taxonomy settings.</p>
          <p>{taxonomyCategories.length} categories are configured for this household.</p>
        </article>
      ) : (
        <article className="result-card taxonomy-manager">
          <div className="row draft-header">
            <h3>Categories & Subcategories</h3>
            <span className="tool-chip">{taxonomyCategories.length} categories</span>
          </div>

          <div className="taxonomy-create-row">
            <input
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="Add category (e.g. Pets)"
              disabled={taxonomyBusy}
            />
            <button
              type="button"
              className="btn-main"
              onClick={handleCreateCategory}
              disabled={taxonomyBusy || !newCategoryName.trim()}
            >
              Add Category
            </button>
          </div>

          {taxonomyCategories.length === 0 ? (
            <p className="hint">No categories configured yet.</p>
          ) : (
            <div className="taxonomy-list">
              {taxonomyCategories.map((category) => (
                <article key={category.id} className="taxonomy-category">
                  <div className="taxonomy-category-row">
                    {editingCategoryId === category.id ? (
                      <div className="taxonomy-inline-edit">
                        <input
                          value={editingCategoryName}
                          onChange={(e) => setEditingCategoryName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              void saveCategoryRename(category);
                            }
                            if (e.key === "Escape") {
                              e.preventDefault();
                              cancelCategoryRename();
                            }
                          }}
                          disabled={taxonomyBusy}
                          autoFocus
                        />
                        <button
                          type="button"
                          className="btn-main"
                          onClick={() => void saveCategoryRename(category)}
                          disabled={taxonomyBusy || !editingCategoryName.trim()}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={cancelCategoryRename}
                          disabled={taxonomyBusy}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <>
                        <strong>{category.name}</strong>
                        <div className="member-actions">
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => startCategoryRename(category)}
                            disabled={taxonomyBusy}
                          >
                            Rename
                          </button>
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={() => setDeactivateTarget({ type: "category", category })}
                            disabled={taxonomyBusy}
                          >
                            Deactivate
                          </button>
                        </div>
                      </>
                    )}
                  </div>

                  <div className="taxonomy-sub-list">
                    {category.subcategories.length === 0 ? (
                      <small>No subcategories.</small>
                    ) : (
                      category.subcategories.map((subcategory) => (
                        <div key={subcategory.id} className="taxonomy-sub-row">
                          {editingSubcategoryId === subcategory.id ? (
                            <div className="taxonomy-inline-edit">
                              <input
                                value={editingSubcategoryName}
                                onChange={(e) => setEditingSubcategoryName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    e.preventDefault();
                                    void saveSubcategoryRename(category, subcategory);
                                  }
                                  if (e.key === "Escape") {
                                    e.preventDefault();
                                    cancelSubcategoryRename();
                                  }
                                }}
                                disabled={taxonomyBusy}
                                autoFocus
                              />
                              <button
                                type="button"
                                className="btn-main"
                                onClick={() => void saveSubcategoryRename(category, subcategory)}
                                disabled={taxonomyBusy || !editingSubcategoryName.trim()}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="btn-ghost"
                                onClick={cancelSubcategoryRename}
                                disabled={taxonomyBusy}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <>
                              <span>{subcategory.name}</span>
                              <div className="member-actions">
                                <button
                                  type="button"
                                  className="btn-ghost"
                                  onClick={() => startSubcategoryRename(category, subcategory)}
                                  disabled={taxonomyBusy}
                                >
                                  Rename
                                </button>
                                <button
                                  type="button"
                                  className="btn-danger"
                                  onClick={() =>
                                    setDeactivateTarget({ type: "subcategory", category, subcategory })
                                  }
                                  disabled={taxonomyBusy}
                                >
                                  Deactivate
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      ))
                    )}
                  </div>

                  <div className="taxonomy-create-row">
                    <input
                      value={newSubcategoryByCategory[category.id] || ""}
                      onChange={(e) => updateSubcategoryInput(category.id, e.target.value)}
                      placeholder={`Add subcategory for ${category.name}`}
                      disabled={taxonomyBusy}
                    />
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => handleCreateSubcategory(category)}
                      disabled={taxonomyBusy || !String(newSubcategoryByCategory[category.id] || "").trim()}
                    >
                      Add Subcategory
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>
      )}

      <ConfirmModal
        open={Boolean(deactivateTarget)}
        title={
          deactivateTarget?.type === "category"
            ? "Deactivate this category?"
            : "Deactivate this subcategory?"
        }
        description={
          deactivateTarget?.type === "category"
            ? `Deactivate "${deactivateTarget.category.name}" and all its subcategories?`
            : deactivateTarget
              ? `Deactivate "${deactivateTarget.subcategory.name}" under "${deactivateTarget.category.name}"?`
              : ""
        }
        confirmLabel="Deactivate"
        busy={taxonomyBusy}
        onCancel={() => setDeactivateTarget(null)}
        onConfirm={handleConfirmDeactivate}
      />
    </section>
  );
}

function DashboardPanel({ token, embedded = false }) {
  const [monthsBack, setMonthsBack] = useState(6);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchDashboard(token, monthsBack);
        if (!cancelled) {
          setDashboard(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [monthsBack, token]);

  const maxMonthlyTotal = useMemo(() => {
    if (!dashboard?.monthly_trend?.length) return 1;
    return Math.max(...dashboard.monthly_trend.map((item) => item.total), 1);
  }, [dashboard]);

  const maxCategoryTotal = useMemo(() => {
    if (!dashboard?.category_split?.length) return 1;
    return Math.max(...dashboard.category_split.map((item) => item.total), 1);
  }, [dashboard]);

  const maxUserTotal = useMemo(() => {
    if (!dashboard?.user_split?.length) return 1;
    return Math.max(...dashboard.user_split.map((item) => item.total), 1);
  }, [dashboard]);

  return (
    <section className={embedded ? "embedded-panel" : "panel"}>
      <div className="dashboard-header">
        {embedded ? <h3>Spending Overview</h3> : <h2>Spending Overview</h2>}
        <label>
          Trend Window
          <select
            value={monthsBack}
            onChange={(e) => setMonthsBack(Number(e.target.value))}
          >
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
            <option value={12}>Last 12 months</option>
          </select>
        </label>
      </div>

      {loading && <PanelSkeleton rows={5} />}
      {error && <p className="form-error">{error}</p>}

      {dashboard && !loading && (
        <>
          <div className="stats-grid">
            <article className="stat-card">
              <p className="kicker">Current Month</p>
              <h3>{formatMonthYearValue(dashboard.period_month, { monthStyle: "long", separator: " " })}</h3>
              <p className="metric-value">{formatCurrencyValue(dashboard.total_spend)}</p>
            </article>
            <article className="stat-card">
              <p className="kicker">Confirmed Expenses</p>
              <h3>{dashboard.expense_count}</h3>
              <p className="metric-sub">entries this month</p>
            </article>
            <article className="stat-card">
              <p className="kicker">Daily Burn Points</p>
              <h3>{dashboard.daily_burn.length}</h3>
              <p className="metric-sub">days with expenses</p>
            </article>
          </div>

          <div className="result-grid dashboard-grid">
            <article className="result-card">
              <h3>Monthly Trend</h3>
              {dashboard.monthly_trend.length === 0 ? (
                <p>No trend data yet.</p>
              ) : (
                <div className="bar-list">
                  {dashboard.monthly_trend.map((item) => (
                    <div className="bar-row" key={item.month}>
                      <span>{formatMonthYearValue(item.month, { monthStyle: "short", separator: "-" })}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${Math.max((item.total / maxMonthlyTotal) * 100, 2)}%`,
                          }}
                        />
                      </div>
                      <strong>{formatCurrencyValue(item.total)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="result-card">
              <h3>Category Split</h3>
              {dashboard.category_split.length === 0 ? (
                <p>No confirmed expenses this month.</p>
              ) : (
                <div className="bar-list">
                  {dashboard.category_split.map((item) => (
                    <div className="bar-row" key={item.category}>
                      <span>{item.category}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill accent"
                          style={{
                            width: `${Math.max((item.total / maxCategoryTotal) * 100, 2)}%`,
                          }}
                        />
                      </div>
                      <strong>{formatCurrencyValue(item.total)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="result-card">
              <h3>User Split</h3>
              {dashboard.user_split.length === 0 ? (
                <p>No user data yet.</p>
              ) : (
                <div className="bar-list">
                  {dashboard.user_split.map((item) => (
                    <div className="bar-row" key={item.user_id}>
                      <span>{item.user_name}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill dark"
                          style={{
                            width: `${Math.max((item.total / maxUserTotal) * 100, 2)}%`,
                          }}
                        />
                      </div>
                      <strong>{formatCurrencyValue(item.total)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </>
      )}
    </section>
  );
}

const analyticsPrompts = [
  "How much did we spend this month?",
  "Show category breakdown for this month",
  "Who spent the most this month?",
  "Show monthly trend for last 6 months",
  "Show top 5 expenses in last 3 months",
];

function isInternalIdColumn(column) {
  return /_id$/i.test(column || "") || /^id$/i.test(column || "");
}

function toColumnLabel(column) {
  return String(column || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function parseNumeric(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatCurrencyValue(value, currencyCode = "INR") {
  const numeric = parseNumeric(value);
  if (numeric === null) return value;
  const normalized = String(currencyCode || "INR").toUpperCase();
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: normalized,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${numeric.toFixed(2)} ${normalized}`;
  }
}

function formatDateValue(value) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function parseYearMonthValue(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const match = raw.match(/^(\d{4})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return null;
  }
  return new Date(year, month - 1, 1);
}

function formatMonthYearValue(value, { monthStyle = "long", separator = " " } = {}) {
  if (value === null || value === undefined) return "";
  let parsed = null;
  if (value instanceof Date) {
    parsed = Number.isNaN(value.getTime()) ? null : value;
  } else {
    parsed = parseYearMonthValue(value);
    if (!parsed) {
      const trimmed = String(value).trim();
      if (!trimmed) return "";
      const fallbackDate = new Date(trimmed);
      if (Number.isNaN(fallbackDate.getTime())) return value;
      parsed = fallbackDate;
    }
  }

  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      month: monthStyle,
      year: "numeric",
    }).formatToParts(parsed);
    const monthPart = parts.find((part) => part.type === "month")?.value;
    const yearPart = parts.find((part) => part.type === "year")?.value;
    if (!monthPart || !yearPart) return value;
    return `${monthPart}${separator}${yearPart}`;
  } catch {
    return value;
  }
}

function getRowCurrency(row, columns) {
  const currencyIndex = columns.findIndex((column) => String(column).toLowerCase() === "currency");
  if (currencyIndex < 0) return "INR";
  const raw = row?.[currencyIndex];
  if (typeof raw !== "string") return "INR";
  const code = raw.trim().toUpperCase();
  return code || "INR";
}

function isAmountColumn(column) {
  return /(amount|total|spend|value|sum)/i.test(column || "");
}

function isDateColumn(column) {
  return /(date|day|month|year)/i.test(column || "");
}

function formatCell(value, column, row, columns) {
  const columnName = String(column || "");
  if (isDateColumn(columnName)) {
    return formatDateValue(value);
  }
  if (isAmountColumn(columnName)) {
    return formatCurrencyValue(value, getRowCurrency(row, columns));
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value : value.toFixed(2);
  }
  return value;
}

function AnalyticsPanel({ token, embedded = false }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showDebug, setShowDebug] = useState(false);
  const analyticsVoice = useVoiceTranscription({
    token,
    onTranscript: (transcript) => {
      setText((previous) => appendVoiceTranscript(previous, transcript));
      setError("");
    },
  });
  const analyticsVoiceTranscribing = analyticsVoice.status === "transcribing";

  const maxPointValue = useMemo(() => {
    if (!result?.chart?.points?.length) return 1;
    return Math.max(...result.chart.points.map((point) => point.value), 1);
  }, [result]);

  const visibleTable = useMemo(() => {
    if (!result?.table) return null;
    const columns = Array.isArray(result.table.columns) ? result.table.columns : [];
    const rows = Array.isArray(result.table.rows) ? result.table.rows : [];
    const visibleIndexes = columns
      .map((column, index) => ({ column, index }))
      .filter((item) => !isInternalIdColumn(String(item.column)))
      .map((item) => item.index);
    if (visibleIndexes.length === 0) {
      return { columns: [], rows: [] };
    }
    return {
      columns: visibleIndexes.map((index) => columns[index]),
      rows: rows.map((row) =>
        visibleIndexes.map((index) => (Array.isArray(row) ? row[index] : ""))
      ),
    };
  }, [result]);

  async function runQuery(customText) {
    const query = String(customText ?? text).trim();
    if (!query) return;
    setText(query);
    setLoading(true);
    setError("");
    setShowDebug(false);
    try {
      const data = await askAnalysis(token, query);
      setResult(data);
      setText("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={embedded ? "embedded-panel" : "panel"}>
      {embedded ? <h3>Ask AI</h3> : <h2>Ask AI</h2>}
      <p className="hint">
        Ask household spending questions and get chart/table-backed answers.
      </p>
      <div className="prompt-pills">
        {analyticsPrompts.map((prompt) => (
          <button
            type="button"
            key={prompt}
            className="btn-ghost prompt-pill"
            onClick={() => void runQuery(prompt)}
            disabled={loading || analyticsVoiceTranscribing}
          >
            {prompt}
          </button>
        ))}
      </div>
      <div className="stack">
        <div className="voice-textarea-wrap">
          <textarea
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask anything about household spending..."
          />
          <div className="voice-textarea-action">
            <VoiceTranscriptionControls voice={analyticsVoice} disabled={loading} />
          </div>
        </div>
        <VoiceTranscriptionFeedback voice={analyticsVoice} />
        <button
          className="btn-main"
          onClick={() => void runQuery()}
          disabled={loading || analyticsVoiceTranscribing}
        >
          {loading ? "Analyzing..." : "Run Insight"}
        </button>
      </div>
      {loading && <p className="hint subtle-loader">Analyzing ledger data...</p>}
      {error && <p className="form-error">{error}</p>}

      {result && (
        <div className="analytics-results">
          <article className="result-card">
            <div className="row draft-header">
              <h3>Assistant</h3>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setShowDebug((prev) => !prev)}
              >
                {showDebug ? "Hide technical details" : "Show technical details"}
              </button>
            </div>
            <article className="assistant-bubble markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {result.answer ?? ""}
              </ReactMarkdown>
            </article>
            {showDebug && (
              <>
                <div className="analysis-meta">
                  <span className={`route-chip ${result.route}`}>{result.route.toUpperCase()}</span>
                  <span className="tool-chip">{result.tool}</span>
                  <span className="hint">
                    Confidence {Number(result.confidence ?? 0).toFixed(2)}
                  </span>
                </div>
                {Array.isArray(result.tool_trace) && result.tool_trace.length > 0 && (
                  <p className="hint">
                    Trace: <code>{result.tool_trace.join(" -> ")}</code>
                  </p>
                )}
                {result.sql && (
                  <p className="hint">
                    SQL: <code>{result.sql}</code>
                  </p>
                )}
              </>
            )}
          </article>

          {result.chart?.points?.length > 0 && (
            <article className="result-card">
              <h3>{result.chart.title}</h3>
              <div className="bar-list">
                {result.chart.points.map((point) => (
                  <div className="bar-row" key={`${point.label}-${point.value}`}>
                    <span>{point.label}</span>
                    <div className="bar-track">
                      <div
                        className="bar-fill accent"
                        style={{
                          width: `${Math.max((point.value / maxPointValue) * 100, 2)}%`,
                        }}
                      />
                    </div>
                    <strong>{formatCurrencyValue(point.value)}</strong>
                  </div>
                ))}
              </div>
            </article>
          )}

          {visibleTable && (
            <article className="result-card">
              <h3>Result Table</h3>
              {visibleTable.columns.length === 0 ? (
                <p>No display-friendly columns returned.</p>
              ) : visibleTable.rows.length === 0 ? (
                <p>No rows returned.</p>
              ) : (
                <>
                  <div className="table-wrap desktop-table-only">
                    <table className="analytics-table">
                      <thead>
                        <tr>
                          {visibleTable.columns.map((column) => (
                            <th key={column}>{toColumnLabel(column)}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {visibleTable.rows.map((row, index) => (
                          <tr key={index}>
                            {row.map((cell, cellIndex) => (
                              <td key={`${index}-${cellIndex}`}>
                                {formatCell(cell, visibleTable.columns[cellIndex], row, visibleTable.columns)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="mobile-data-list mobile-cards-only">
                    {visibleTable.rows.map((row, index) => (
                      <article className="mobile-data-card" key={`analytics-mobile-${index}`}>
                        <p className="mobile-data-card-title">Row {index + 1}</p>
                        {visibleTable.columns.map((column, cellIndex) => (
                          <div className="mobile-data-row" key={`analytics-mobile-${index}-${column}`}>
                            <span className="mobile-data-label">{toColumnLabel(column)}</span>
                            <span className="mobile-data-value">
                              {formatCell(row[cellIndex], column, row, visibleTable.columns)}
                            </span>
                          </div>
                        ))}
                      </article>
                    ))}
                  </div>
                </>
              )}
            </article>
          )}
        </div>
      )}
    </section>
  );
}

function InsightsPanel({ token }) {
  const [activeView, setActiveView] = useState("overview");

  return (
    <section className="panel">
      <div className="panel-action-row">
        <div className="insights-switch" role="tablist" aria-label="Insights Sections">
          <button
            type="button"
            className={activeView === "overview" ? "insights-tab active" : "insights-tab"}
            onClick={() => setActiveView("overview")}
          >
            Overview
          </button>
          <button
            type="button"
            className={activeView === "ai" ? "insights-tab active" : "insights-tab"}
            onClick={() => setActiveView("ai")}
          >
            Ask AI
          </button>
        </div>
      </div>

      {activeView === "overview" ? (
        <DashboardPanel token={token} embedded />
      ) : (
        <AnalyticsPanel token={token} embedded />
      )}
    </section>
  );
}

export default function App() {
  const [auth, setAuth] = useState(() => {
    const token = safeStorageGet("expense_auth_token");
    const userRaw = safeStorageGet("expense_auth_user");
    return {
      token,
      user: safeParseStoredUser(userRaw),
    };
  });
  const [activeTab, setActiveTab] = useState("capture");
  const [sessionTransitionVisible, setSessionTransitionVisible] = useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [capturePrefillText, setCapturePrefillText] = useState("");
  const [globalNotice, setGlobalNotice] = useState("");

  useEffect(() => {
    if (auth?.token) {
      safeStorageSet("expense_auth_token", auth.token);
    } else {
      safeStorageRemove("expense_auth_token");
    }
    if (auth?.user) {
      safeStorageSet("expense_auth_user", JSON.stringify(auth.user));
    } else {
      safeStorageRemove("expense_auth_user");
    }
  }, [auth]);

  useEffect(() => {
    if (!auth?.token) {
      setSessionTransitionVisible(false);
      return;
    }
    setSessionTransitionVisible(true);
    const timer = setTimeout(() => {
      setSessionTransitionVisible(false);
    }, 650);
    return () => clearTimeout(timer);
  }, [auth?.token]);

  useEffect(() => {
    if (!auth?.token) return;
    function onKeyDown(event) {
      if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === "k") {
        event.preventDefault();
        setQuickAddOpen(true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [auth?.token]);

  useEffect(() => {
    if (!globalNotice) return;
    const timer = setTimeout(() => {
      setGlobalNotice("");
    }, 2800);
    return () => clearTimeout(timer);
  }, [globalNotice]);

  const tabLabel = useMemo(() => {
    if (activeTab === "settings") return "Settings";
    return tabs.find((tab) => tab.id === activeTab)?.label ?? "Add Expense";
  }, [activeTab]);

  if (!auth?.token) {
    return (
      <RuntimeErrorBoundary>
        <main className="app-shell">
          <Header user={null} onLogout={() => {}} />
          <AuthCard onAuthSuccess={setAuth} />
        </main>
      </RuntimeErrorBoundary>
    );
  }

  if (sessionTransitionVisible) {
    return (
      <RuntimeErrorBoundary>
        <main className="app-shell">
          <SessionTransition />
        </main>
      </RuntimeErrorBoundary>
    );
  }

  return (
    <RuntimeErrorBoundary>
      <main className="app-shell">
        <ToastNotice message={globalNotice} placement="top-right" />
        <Header
          user={auth.user}
          onQuickAdd={() => setQuickAddOpen(true)}
          onOpenSettings={() => setActiveTab("settings")}
          settingsActive={activeTab === "settings"}
          onLogout={() => {
            setAuth({ token: null, user: null });
            setActiveTab("capture");
            setQuickAddOpen(false);
            setCapturePrefillText("");
            setGlobalNotice("");
          }}
        />
        <section className="workspace">
          <aside className="side-tabs">
            <p className="kicker">Workspace</p>
            {tabs.map((tab) => (
              <button
                type="button"
                key={tab.id}
                className={activeTab === tab.id ? "tab active" : "tab"}
                onClick={() => setActiveTab(tab.id)}
              >
                <span className="tab-icon" aria-hidden="true">
                  <TabIcon tabId={tab.id} />
                </span>
                <span className="tab-label">{tab.label}</span>
              </button>
            ))}
          </aside>
          <div className="content">
            <div className="content-header">
              <h1>{tabLabel}</h1>
            </div>
            {activeTab === "capture" && (
              <ExpenseLogPanel
                token={auth.token}
                prefilledText={capturePrefillText}
                onPrefilledTextConsumed={() => setCapturePrefillText("")}
              />
            )}
            {activeTab === "ledger" && <LedgerPanel token={auth.token} user={auth.user} />}
            {activeTab === "recurring" && <RecurringPanel token={auth.token} user={auth.user} />}
            {activeTab === "insights" && <InsightsPanel token={auth.token} />}
            {activeTab === "people" && <HouseholdPanel token={auth.token} user={auth.user} />}
            {activeTab === "settings" && <SettingsPanel token={auth.token} user={auth.user} />}
          </div>
        </section>
        <button
          type="button"
          className="quick-add-fab"
          onClick={() => setQuickAddOpen(true)}
          aria-label="Quick add expense"
        >
          +
        </button>
        <QuickAddModal
          open={quickAddOpen}
          token={auth.token}
          onClose={() => setQuickAddOpen(false)}
          onRouteToCapture={(text) => {
            setCapturePrefillText(text);
            setActiveTab("capture");
            setQuickAddOpen(false);
          }}
          onNotify={(text) => setGlobalNotice(text)}
        />
      </main>
    </RuntimeErrorBoundary>
  );
}

function Header({ user, onQuickAdd, onOpenSettings, settingsActive = false, onLogout }) {
  return (
    <header className="topbar">
      <div>
        <p className="kicker">LedgerLoop</p>
        <h2>Household Finance</h2>
      </div>
      <div className="topbar-actions">
        {user && (
          <button
            className={settingsActive ? "settings-trigger active" : "settings-trigger"}
            onClick={onOpenSettings}
            type="button"
            aria-label="Open settings"
          >
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="M19.43 12.98a7.96 7.96 0 0 0 .05-.98 7.96 7.96 0 0 0-.05-.98l2.11-1.65a.5.5 0 0 0 .12-.64l-2-3.46a.5.5 0 0 0-.6-.22l-2.49 1a7.2 7.2 0 0 0-1.7-.98l-.38-2.65A.5.5 0 0 0 14.1 2h-4a.5.5 0 0 0-.49.42l-.38 2.65a7.2 7.2 0 0 0-1.7.98l-2.49-1a.5.5 0 0 0-.6.22l-2 3.46a.5.5 0 0 0 .12.64l2.11 1.65a7.96 7.96 0 0 0-.05.98c0 .33.02.66.05.98l-2.11 1.65a.5.5 0 0 0-.12.64l2 3.46a.5.5 0 0 0 .6.22l2.49-1c.53.4 1.1.73 1.7.98l.38 2.65a.5.5 0 0 0 .49.42h4a.5.5 0 0 0 .49-.42l.38-2.65c.6-.25 1.17-.58 1.7-.98l2.49 1a.5.5 0 0 0 .6-.22l2-3.46a.5.5 0 0 0-.12-.64l-2.11-1.65ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z" />
            </svg>
          </button>
        )}
        {user && (
          <button className="btn-main quick-add-trigger" onClick={onQuickAdd} type="button">
            Quick Add
            <span>Ctrl/Cmd+K</span>
          </button>
        )}
        {user && <span className="user-chip">{user.full_name} ({user.role})</span>}
        {user && (
          <button className="btn-ghost" onClick={onLogout} type="button">
            Logout
          </button>
        )}
      </div>
    </header>
  );
}
