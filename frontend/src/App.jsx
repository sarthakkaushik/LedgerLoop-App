import { Component, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  askAnalysis,
  confirmExpenses,
  createRecurringExpense,
  createFamilyMember,
  createTaxonomyCategory,
  createTaxonomySubcategory,
  createInviteCode,
  deleteTaxonomyCategory,
  deleteTaxonomySubcategory,
  deleteExpense,
  deleteFamilyMemberProfile,
  updateExpense,
  deleteHouseholdMember,
  downloadExpenseCsv,
  fetchDashboard,
  fetchExpenseFeed,
  fetchFamilyMembers,
  fetchHousehold,
  fetchTaxonomy,
  joinHousehold,
  loginUser,
  parseExpenseText,
  registerUser,
  transcribeExpenseAudio,
  updateHouseholdBudget,
  updateHouseholdName,
  updateFamilyMember,
  updateExpenseRecurring,
  updateTaxonomyCategory,
  updateTaxonomySubcategory,
} from "./api";

const tabs = [
  { id: "insights", label: "Dashboard" },
  { id: "capture", label: "Add Expense" },
  { id: "ledger", label: "Ledger" },
  { id: "recurring", label: "Recurring" },
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
const DEFAULT_MONTHLY_BUDGET = 50000;

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

function normalizeMemberType(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (normalized === "adult" || normalized === "child" || normalized === "other") {
    return normalized;
  }
  return "other";
}

function getDefaultFamilyMemberId(familyMembers, user) {
  if (!Array.isArray(familyMembers) || familyMembers.length === 0) return "";
  const currentUserId = String(user?.id || "").trim();
  if (currentUserId) {
    const linked = familyMembers.find((member) => String(member?.linked_user_id || "") === currentUserId);
    if (linked?.id) return String(linked.id);
  }
  const firstAdult = familyMembers.find((member) => normalizeMemberType(member?.member_type) === "adult");
  if (firstAdult?.id) return String(firstAdult.id);
  return String(familyMembers[0]?.id || "");
}

function resolveFamilyMemberNameById(familyMembers, memberId) {
  const target = String(memberId || "").trim();
  if (!target) return "";
  const match = (Array.isArray(familyMembers) ? familyMembers : []).find(
    (member) => String(member?.id || "") === target
  );
  return String(match?.full_name || "").trim();
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
      <main className="app-shell app-shell-unified">
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

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M16.79 3.21a3 3 0 0 1 4.24 4.24L9.58 18.9a1 1 0 0 1-.46.27l-4 1a1 1 0 0 1-1.22-1.22l1-4a1 1 0 0 1 .27-.46L16.79 3.21Zm2.83 1.41a1 1 0 0 0-1.42 0l-1.24 1.24 1.42 1.42 1.24-1.24a1 1 0 0 0 0-1.42Zm-2.66 4.07-1.42-1.42-8.73 8.73-.57 2.27 2.27-.57 8.45-8.45Z" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M11 4a1 1 0 1 1 2 0v7h7a1 1 0 1 1 0 2h-7v7a1 1 0 1 1-2 0v-7H4a1 1 0 1 1 0-2h7V4Z" />
    </svg>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M11.35 3.53a1 1 0 0 1 1.3 0l8 6.75a1 1 0 0 1-1.3 1.53L19 11.53V19a2 2 0 0 1-2 2h-3.5a1 1 0 0 1-1-1v-4h-1v4a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2v-7.47l-.35.28a1 1 0 1 1-1.3-1.53l8-6.75ZM7 9.84V19h2.5v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v4H17V9.84l-5-4.22-5 4.22Z" />
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

function StatusPill({ status, compact = false }) {
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
  if (compact) {
    return (
      <span
        className={`${className} compact`}
        role="img"
        aria-label={label}
        title={label}
      />
    );
  }
  return <span className={className}>{label}</span>;
}

function BudgetOverviewCard({
  totalBudget = DEFAULT_MONTHLY_BUDGET,
  currentSpent = 0,
  currency = "INR",
  periodMonth = null,
  onEditBudget,
}) {
  const parsedBudget = parseNumeric(totalBudget);
  const normalizedBudget = parsedBudget !== null && parsedBudget > 0 ? parsedBudget : DEFAULT_MONTHLY_BUDGET;
  const parsedSpent = parseNumeric(currentSpent);
  const spentValue = parsedSpent !== null && parsedSpent > 0 ? parsedSpent : 0;
  const usagePercentRaw = normalizedBudget > 0 ? (spentValue / normalizedBudget) * 100 : 0;
  const usagePercentVisual = Math.min(Math.max(usagePercentRaw, 0), 100);
  const usagePercentRounded = Math.round(Math.max(usagePercentRaw, 0));
  const overrunPercent = Math.max(usagePercentRaw - 100, 0);
  const overrunPercentVisual = Math.min(overrunPercent, 100);
  const isBreached = usagePercentRaw > 100;
  const isWarning = usagePercentRaw > 80 && usagePercentRaw <= 100;
  const remainingValue = normalizedBudget - spentValue;
  const monthLabel =
    formatMonthYearValue(periodMonth || new Date(), {
      monthStyle: "long",
      separator: " ",
    }) || "This month";

  const stateKey = isBreached ? "breached" : isWarning ? "warning" : "safe";
  const stateLabel = isBreached ? "Limit exceeded" : isWarning ? "Watch spending" : "On track";
  const paletteByState = {
    safe: {
      liquid: "#1199ab",
      surface: "#dff4f7",
      text: "#0d3f56",
      glow: "rgba(17, 153, 171, 0.35)",
    },
    warning: {
      liquid: "#f59e0b",
      surface: "#fff1d9",
      text: "#70380a",
      glow: "rgba(245, 158, 11, 0.33)",
    },
    breached: {
      liquid: "#ef4444",
      surface: "#ffe5e8",
      text: "#7f1d1d",
      glow: "rgba(239, 68, 68, 0.34)",
    },
  };
  const palette = paletteByState[stateKey];

  return (
    <article
      className={isBreached ? "result-card budget-overview-card is-breached" : "result-card budget-overview-card"}
      style={{
        "--budget-progress": palette.liquid,
        "--budget-progress-glow": palette.glow,
      }}
    >
      <div className="budget-overview-content">
        <div className="budget-overview-title-row">
          <p className="budget-overview-heading">Monthly Budget</p>
          <span className="budget-overview-month">{monthLabel}</span>
        </div>
        <p className="budget-overview-status">
          <span className="budget-overview-status-primary">{formatCurrencyValue(spentValue, currency)}</span>
          <span className="budget-overview-status-divider">/</span>
          <span className="budget-overview-status-secondary">{formatCurrencyValue(normalizedBudget, currency)}</span>
        </p>
        <div className="budget-overview-progress-wrap">
          <div
            className={isBreached ? "budget-overview-progress over" : "budget-overview-progress"}
            role="progressbar"
            aria-label={`Budget used ${usagePercentRounded} percent`}
            aria-valuemin={0}
            aria-valuemax={Math.max(usagePercentRounded, 100)}
            aria-valuenow={usagePercentRounded}
          >
            <span
              className="budget-overview-progress-fill"
              style={{ width: `${usagePercentVisual}%` }}
              aria-hidden="true"
            />
            {isBreached && (
              <span
                className="budget-overview-progress-overrun"
                style={{ width: `${overrunPercentVisual}%` }}
                aria-hidden="true"
              />
            )}
          </div>
          <div className="budget-overview-progress-meta">
            <span>0%</span>
            <strong>{usagePercentRounded}% used</strong>
            <span>{isBreached ? `+${Math.round(overrunPercent)}% over` : "100%"}</span>
          </div>
        </div>
        <p className={isBreached ? "budget-overview-remaining over" : "budget-overview-remaining"}>
          {isBreached
            ? `Limit exceeded by ${formatCurrencyValue(Math.abs(remainingValue), currency)}`
            : `${formatCurrencyValue(Math.max(remainingValue, 0), currency)} remaining`}
        </p>
        <div className="budget-overview-meta">
          <span className={`budget-overview-state ${stateKey}`}>{stateLabel}</span>
          {typeof onEditBudget === "function" && (
            <button type="button" className="budget-overview-link" onClick={onEditBudget}>
              Edit budget
            </button>
          )}
        </div>
      </div>

      <div
        className="budget-orb-shell"
        style={{
          "--budget-liquid": palette.liquid,
          "--budget-surface": palette.surface,
          "--budget-ink": palette.text,
          "--budget-glow": palette.glow,
        }}
      >
        <div className="budget-orb-inner" aria-label={`Budget usage ${usagePercentRounded} percent`}>
          <div className="budget-orb-liquid" style={{ height: `${usagePercentVisual}%` }} aria-hidden="true">
            <span className="budget-orb-wave wave-a" />
            <span className="budget-orb-wave wave-b" />
          </div>
          <div className="budget-orb-center">
            <div className="budget-orb-center-badge">
              <p className="budget-orb-value">{isBreached ? "OVER" : `${usagePercentRounded}%`}</p>
              {!isBreached && <p className="budget-orb-caption">used</p>}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
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
  user,
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
  const [familyMembers, setFamilyMembers] = useState([]);
  const [familyLoading, setFamilyLoading] = useState(false);
  const [familyError, setFamilyError] = useState("");
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);

  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );
  const taxonomyCategoryOptions = useMemo(
    () => taxonomyCategories.map((category) => category.name),
    [taxonomyCategories]
  );
  const activeFamilyMembers = useMemo(
    () => (Array.isArray(familyMembers) ? familyMembers.filter((member) => member?.is_active !== false) : []),
    [familyMembers]
  );
  const defaultFamilyMemberId = useMemo(
    () => getDefaultFamilyMemberId(activeFamilyMembers, user),
    [activeFamilyMembers, user]
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
    async function loadModalData() {
      setTaxonomyLoading(true);
      setTaxonomyError("");
      setFamilyLoading(true);
      setFamilyError("");
      try {
        const [taxonomyData, familyData] = await Promise.all([
          fetchTaxonomy(token),
          fetchFamilyMembers(token),
        ]);
        if (!cancelled) {
          setTaxonomy(taxonomyData);
          setFamilyMembers(Array.isArray(familyData?.items) ? familyData.items : []);
        }
      } catch (err) {
        if (!cancelled) {
          const message = String(err?.message || "Could not load family profile options.");
          setTaxonomyError(message);
          setFamilyError(message);
        }
      } finally {
        if (!cancelled) {
          setTaxonomyLoading(false);
          setFamilyLoading(false);
        }
      }
    }
    loadModalData();
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

  useEffect(() => {
    if (!open || !defaultFamilyMemberId) return;
    setDrafts((previous) =>
      previous.map((draft) => ({
        ...draft,
        attributed_family_member_id:
          String(draft?.attributed_family_member_id || "").trim() || defaultFamilyMemberId,
      }))
    );
  }, [defaultFamilyMemberId, open]);

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
      setDrafts(
        (parsed.expenses ?? []).map((draft) => ({
          ...draft,
          attributed_family_member_id:
            String(draft?.attributed_family_member_id || "").trim() || defaultFamilyMemberId,
        }))
      );
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
          attributed_family_member_id:
            String(draft.attributed_family_member_id || "").trim() || defaultFamilyMemberId || null,
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
          {familyLoading && <p className="hint subtle-loader">Loading family profiles...</p>}
          {taxonomyError && <p className="form-error">{taxonomyError}</p>}
          {familyError && !taxonomyError && <p className="form-error">{familyError}</p>}
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
                        Belongs To
                        <select
                          value={draft.attributed_family_member_id || defaultFamilyMemberId || ""}
                          onChange={(e) =>
                            updateDraft(index, "attributed_family_member_id", e.target.value)
                          }
                          disabled={activeFamilyMembers.length === 0}
                        >
                          <option value="">
                            {activeFamilyMembers.length === 0
                              ? "No active profile"
                              : "Select family member"}
                          </option>
                          {activeFamilyMembers.map((member) => (
                            <option key={`quick-add-member-${member.id}`} value={member.id}>
                              {member.full_name} ({normalizeMemberType(member.member_type)})
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

function ExpenseLogPanel({ token, user, prefilledText, onPrefilledTextConsumed }) {
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
  const [familyMembers, setFamilyMembers] = useState([]);
  const [familyLoading, setFamilyLoading] = useState(false);
  const [familyError, setFamilyError] = useState("");
  const activeFamilyMembers = useMemo(
    () => (Array.isArray(familyMembers) ? familyMembers.filter((member) => member?.is_active !== false) : []),
    [familyMembers]
  );
  const defaultFamilyMemberId = useMemo(
    () => getDefaultFamilyMemberId(activeFamilyMembers, user),
    [activeFamilyMembers, user]
  );

  useEffect(() => {
    let cancelled = false;
    async function loadCaptureContext() {
      setTaxonomyLoading(true);
      setTaxonomyError("");
      setFamilyLoading(true);
      setFamilyError("");
      try {
        const [taxonomyData, familyData] = await Promise.all([
          fetchTaxonomy(token),
          fetchFamilyMembers(token),
        ]);
        if (!cancelled) {
          setTaxonomy(taxonomyData);
          setFamilyMembers(Array.isArray(familyData?.items) ? familyData.items : []);
        }
      } catch (err) {
        if (!cancelled) {
          const message = String(err?.message || "Could not load family profile options.");
          setTaxonomyError(message);
          setFamilyError(message);
        }
      } finally {
        if (!cancelled) {
          setTaxonomyLoading(false);
          setFamilyLoading(false);
        }
      }
    }
    loadCaptureContext();
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

  useEffect(() => {
    if (!defaultFamilyMemberId) return;
    setDrafts((previous) =>
      previous.map((draft) => ({
        ...draft,
        attributed_family_member_id:
          String(draft?.attributed_family_member_id || "").trim() || defaultFamilyMemberId,
      }))
    );
  }, [defaultFamilyMemberId]);

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
      setDrafts(
        (parsed.expenses ?? []).map((draft) => ({
          ...draft,
          attributed_family_member_id:
            String(draft?.attributed_family_member_id || "").trim() || defaultFamilyMemberId,
        }))
      );
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
          attributed_family_member_id:
            String(draft.attributed_family_member_id || "").trim() || defaultFamilyMemberId || null,
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
      {familyLoading && <p className="hint">Loading family profiles...</p>}
      {taxonomyError && <p className="form-error">{taxonomyError}</p>}
      {familyError && !taxonomyError && <p className="form-error">{familyError}</p>}
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
                  Belongs To
                  <select
                    value={draft.attributed_family_member_id || defaultFamilyMemberId || ""}
                    onChange={(e) => updateDraft(idx, "attributed_family_member_id", e.target.value)}
                    disabled={activeFamilyMembers.length === 0}
                  >
                    <option value="">
                      {activeFamilyMembers.length === 0 ? "No active profile" : "Select family member"}
                    </option>
                    {activeFamilyMembers.map((member) => (
                      <option key={`capture-member-${member.id}`} value={member.id}>
                        {member.full_name} ({normalizeMemberType(member.member_type)})
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
  const [familyMembers, setFamilyMembers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [deletingMemberId, setDeletingMemberId] = useState(null);
  const [savingFamily, setSavingFamily] = useState(false);
  const [editingFamilyId, setEditingFamilyId] = useState("");
  const [editingFamilyDraft, setEditingFamilyDraft] = useState({ full_name: "", member_type: "other" });
  const [deactivatingFamilyId, setDeactivatingFamilyId] = useState(null);
  const [newFamilyProfile, setNewFamilyProfile] = useState({ full_name: "", member_type: "child" });
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadPeopleData() {
    setLoading(true);
    setError("");
    try {
      const [householdData, feedData, familyData] = await Promise.all([
        fetchHousehold(token),
        fetchExpenseFeed(token, { status: "confirmed", limit: 100 }),
        fetchFamilyMembers(token),
      ]);
      setHousehold(householdData);
      setFeed(feedData);
      setFamilyMembers(Array.isArray(familyData?.items) ? familyData.items : []);
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
      const ownerName = String(item.attributed_family_member_name || item.logged_by_name || "Unknown").trim();
      const current = map.get(ownerName) || { count: 0, total: 0 };
      current.count += 1;
      current.total += Number(item.amount || 0);
      map.set(ownerName, current);
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

  function handleStartFamilyEdit(member) {
    setEditingFamilyId(member.id);
    setEditingFamilyDraft({
      full_name: String(member?.full_name || ""),
      member_type: normalizeMemberType(member?.member_type),
    });
  }

  function handleCancelFamilyEdit() {
    if (savingFamily) return;
    setEditingFamilyId("");
    setEditingFamilyDraft({ full_name: "", member_type: "other" });
  }

  async function handleCreateFamilyProfile() {
    const name = String(newFamilyProfile.full_name || "").trim();
    if (!name) {
      setError("Enter a family member name.");
      return;
    }
    setSavingFamily(true);
    setError("");
    setMessage("");
    try {
      const created = await createFamilyMember(token, {
        full_name: name,
        member_type: normalizeMemberType(newFamilyProfile.member_type),
      });
      setMessage(`Family profile added for ${created.full_name}.`);
      setNewFamilyProfile({ full_name: "", member_type: "child" });
      await loadPeopleData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingFamily(false);
    }
  }

  async function handleSaveFamilyProfileEdit(memberId) {
    const name = String(editingFamilyDraft.full_name || "").trim();
    if (!name) {
      setError("Enter a valid family profile name.");
      return;
    }
    setSavingFamily(true);
    setError("");
    setMessage("");
    try {
      const updated = await updateFamilyMember(token, memberId, {
        full_name: name,
        member_type: normalizeMemberType(editingFamilyDraft.member_type),
      });
      setMessage(`Family profile updated for ${updated.full_name}.`);
      handleCancelFamilyEdit();
      await loadPeopleData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingFamily(false);
    }
  }

  async function handleDeactivateFamilyProfile(member) {
    if (!member?.id) return;
    setDeactivatingFamilyId(member.id);
    setError("");
    setMessage("");
    try {
      const data = await deleteFamilyMemberProfile(token, member.id);
      setMessage(data.message || "Family profile removed.");
      if (editingFamilyId === member.id) {
        handleCancelFamilyEdit();
      }
      await loadPeopleData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeactivatingFamilyId(null);
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
        Invite household users, create family profiles, and attribute spending to the right person.
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
              <h3>Family Profiles</h3>
              <p className="hint">
                Use profiles to tag who each expense belongs to (for example: husband, wife, child).
              </p>
              <div className="family-profile-create">
                <label>
                  Name
                  <input
                    value={newFamilyProfile.full_name}
                    onChange={(e) =>
                      setNewFamilyProfile((previous) => ({ ...previous, full_name: e.target.value }))
                    }
                    placeholder="e.g. Aarav"
                    disabled={savingFamily}
                  />
                </label>
                <label>
                  Type
                  <select
                    value={newFamilyProfile.member_type}
                    onChange={(e) =>
                      setNewFamilyProfile((previous) => ({ ...previous, member_type: e.target.value }))
                    }
                    disabled={savingFamily}
                  >
                    <option value="adult">Adult</option>
                    <option value="child">Child</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <button
                  className="btn-main"
                  type="button"
                  onClick={handleCreateFamilyProfile}
                  disabled={savingFamily}
                >
                  {savingFamily ? "Saving..." : "Add Profile"}
                </button>
              </div>
              <div className="member-list">
                {familyMembers.length === 0 ? (
                  <p className="hint">No family profiles yet.</p>
                ) : (
                  familyMembers.map((member) => {
                    const isEditing = editingFamilyId === member.id;
                    const isLinkedToCurrentUser = String(member.linked_user_id || "") === String(user?.id || "");
                    return (
                      <div className="member-row" key={`family-${member.id}`}>
                        <div>
                          {isEditing ? (
                            <>
                              <input
                                value={editingFamilyDraft.full_name}
                                onChange={(e) =>
                                  setEditingFamilyDraft((previous) => ({
                                    ...previous,
                                    full_name: e.target.value,
                                  }))
                                }
                                disabled={savingFamily}
                              />
                              <label className="member-inline-select">
                                Type
                                <select
                                  value={editingFamilyDraft.member_type}
                                  onChange={(e) =>
                                    setEditingFamilyDraft((previous) => ({
                                      ...previous,
                                      member_type: e.target.value,
                                    }))
                                  }
                                  disabled={savingFamily}
                                >
                                  <option value="adult">Adult</option>
                                  <option value="child">Child</option>
                                  <option value="other">Other</option>
                                </select>
                              </label>
                            </>
                          ) : (
                            <>
                              <strong>{member.full_name}</strong>
                              <p className="hint">
                                {normalizeMemberType(member.member_type)}
                                {member.linked_user_name ? ` | linked to ${member.linked_user_name}` : ""}
                              </p>
                            </>
                          )}
                        </div>
                        <div className="member-actions">
                          {!isEditing ? (
                            <>
                              <span className="tool-chip">{normalizeMemberType(member.member_type)}</span>
                              <button
                                className="btn-ghost"
                                type="button"
                                onClick={() => handleStartFamilyEdit(member)}
                                disabled={savingFamily}
                              >
                                Edit
                              </button>
                              <button
                                className="btn-danger"
                                type="button"
                                onClick={() => void handleDeactivateFamilyProfile(member)}
                                disabled={
                                  deactivatingFamilyId === member.id ||
                                  savingFamily ||
                                  isLinkedToCurrentUser
                                }
                                title={
                                  isLinkedToCurrentUser
                                    ? "You cannot deactivate your own linked profile."
                                    : "Deactivate family profile"
                                }
                              >
                                {deactivatingFamilyId === member.id ? "Removing..." : "Deactivate"}
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                className="btn-main"
                                type="button"
                                onClick={() => void handleSaveFamilyProfileEdit(member.id)}
                                disabled={savingFamily}
                              >
                                {savingFamily ? "Saving..." : "Save"}
                              </button>
                              <button
                                className="btn-ghost"
                                type="button"
                                onClick={handleCancelFamilyEdit}
                                disabled={savingFamily}
                              >
                                Cancel
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </article>

            <article className="result-card">
              <h3>Spend by Family Profile</h3>
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
  const [taxonomy, setTaxonomy] = useState({ categories: [] });
  const [taxonomyError, setTaxonomyError] = useState("");
  const [familyMembers, setFamilyMembers] = useState([]);
  const [familyError, setFamilyError] = useState("");
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
    attributed_family_member_id: "",
    category: "",
    subcategory: "",
    description: "",
    merchant_or_item: "",
    date_incurred: todayIsoDate(),
  });
  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );
  const taxonomyCategoryOptions = useMemo(
    () => taxonomyCategories.map((category) => category.name),
    [taxonomyCategories]
  );
  const activeFamilyMembers = useMemo(
    () => (Array.isArray(familyMembers) ? familyMembers.filter((member) => member?.is_active !== false) : []),
    [familyMembers]
  );
  const defaultFamilyMemberId = useMemo(
    () => getDefaultFamilyMemberId(activeFamilyMembers, user),
    [activeFamilyMembers, user]
  );

  function getSubcategoryOptions(categoryName) {
    const normalized = normalizeTaxonomyName(categoryName);
    if (!normalized) return [];
    const match = taxonomyCategories.find(
      (category) => normalizeTaxonomyName(category.name) === normalized
    );
    return (match?.subcategories || []).map((subcategory) => subcategory.name);
  }

  async function loadRecurringData() {
    setLoading(true);
    setError("");
    try {
      const taxonomyPromise = fetchTaxonomy(token)
        .then((data) => ({ data, error: "" }))
        .catch((err) => ({
          data: { categories: [] },
            error: String(err?.message || "Could not load taxonomy options."),
        }));
      const familyPromise = fetchFamilyMembers(token)
        .then((data) => ({ data, error: "" }))
        .catch((err) => ({
          data: { items: [] },
          error: String(err?.message || "Could not load family profile options."),
        }));
      const [data, taxonomyResult, familyResult] = await Promise.all([
        fetchExpenseFeed(token, {
          status: "confirmed",
          limit: 300,
          recurringOnly: true,
        }),
        taxonomyPromise,
        familyPromise,
      ]);
      setFeed(data);
      setTaxonomy(taxonomyResult.data);
      setTaxonomyError(taxonomyResult.error);
      setFamilyMembers(Array.isArray(familyResult?.data?.items) ? familyResult.data.items : []);
      setFamilyError(familyResult.error || "");
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

  useEffect(() => {
    if (!defaultFamilyMemberId) return;
    setForm((previous) => ({
      ...previous,
      attributed_family_member_id:
        String(previous?.attributed_family_member_id || "").trim() || defaultFamilyMemberId,
    }));
  }, [defaultFamilyMemberId]);

  function updateForm(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "category") {
        const options = getSubcategoryOptions(value);
        if (
          next.subcategory &&
          !options.some((subcategory) => normalizeTaxonomyName(subcategory) === normalizeTaxonomyName(next.subcategory))
        ) {
          next.subcategory = "";
        }
      }
      if (field === "subcategory" && !value) {
        next.subcategory = "";
      }
      return next;
    });
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
        attributed_family_member_id:
          String(form.attributed_family_member_id || "").trim() || defaultFamilyMemberId || null,
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
        attributed_family_member_id: defaultFamilyMemberId || "",
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
      {taxonomyError && <p className="hint">{taxonomyError}</p>}
      {familyError && <p className="hint">{familyError}</p>}
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
            Belongs To
            <select
              value={form.attributed_family_member_id || defaultFamilyMemberId || ""}
              onChange={(e) => updateForm("attributed_family_member_id", e.target.value)}
              disabled={activeFamilyMembers.length === 0}
            >
              <option value="">
                {activeFamilyMembers.length === 0 ? "No active profile" : "Select family member"}
              </option>
              {activeFamilyMembers.map((member) => (
                <option key={`recurring-member-${member.id}`} value={member.id}>
                  {member.full_name} ({normalizeMemberType(member.member_type)})
                </option>
              ))}
            </select>
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
            <select
              value={form.category || ""}
              onChange={(e) => updateForm("category", e.target.value)}
            >
              <option value="">Select category</option>
              {form.category &&
                !taxonomyCategoryOptions.some(
                  (category) => normalizeTaxonomyName(category) === normalizeTaxonomyName(form.category)
                ) && <option value={form.category}>{form.category}</option>}
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
              value={form.subcategory || ""}
              onChange={(e) => updateForm("subcategory", e.target.value)}
              disabled={!form.category}
            >
              <option value="">Select subcategory</option>
              {form.subcategory &&
                !getSubcategoryOptions(form.category).some(
                  (subcategory) =>
                    normalizeTaxonomyName(subcategory) === normalizeTaxonomyName(form.subcategory)
                ) && <option value={form.subcategory}>{form.subcategory}</option>}
              {getSubcategoryOptions(form.category).map((subcategory) => (
                <option key={`${form.category}-${subcategory}`} value={subcategory}>
                  {subcategory}
                </option>
              ))}
            </select>
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
                      <th>Belongs To</th>
                      <th>Category</th>
                      <th>Description</th>
                      <th>Amount</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feed.items.map((item) => {
                      const canEdit = user?.role === "admin" || item.logged_by_user_id === user?.id;
                      const canDelete = canEdit;
                      return (
                        <tr key={item.id}>
                          <td>{formatDateValue(item.date_incurred)}</td>
                          <td>{item.logged_by_name}</td>
                          <td>{item.attributed_family_member_name || item.logged_by_name}</td>
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
                        <span className="mobile-data-label">Belongs To</span>
                        <span className="mobile-data-value">
                          {item.attributed_family_member_name || item.logged_by_name}
                        </span>
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

function LedgerPanel({ token, user, onOpenSettings }) {
  const [feed, setFeed] = useState(null);
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [budgetSnapshot, setBudgetSnapshot] = useState(null);
  const [totalBudget, setTotalBudget] = useState(DEFAULT_MONTHLY_BUDGET);
  const [taxonomy, setTaxonomy] = useState({ categories: [] });
  const [taxonomyError, setTaxonomyError] = useState("");
  const [familyMembers, setFamilyMembers] = useState([]);
  const [familyError, setFamilyError] = useState("");
  const [loading, setLoading] = useState(false);
  const [deletingExpenseId, setDeletingExpenseId] = useState(null);
  const [updatingRecurringId, setUpdatingRecurringId] = useState(null);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [expenseToDelete, setExpenseToDelete] = useState(null);
  const [expenseToEdit, setExpenseToEdit] = useState(null);
  const [expenseEditDraft, setExpenseEditDraft] = useState({
    date_incurred: "",
    amount: "",
    currency: "INR",
    attributed_family_member_id: "",
    category: "",
    subcategory: "",
    description: "",
  });
  const [updatingExpenseId, setUpdatingExpenseId] = useState(null);
  const [editError, setEditError] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );
  const taxonomyCategoryOptions = useMemo(
    () => taxonomyCategories.map((category) => category.name),
    [taxonomyCategories]
  );
  const activeFamilyMembers = useMemo(
    () => (Array.isArray(familyMembers) ? familyMembers.filter((member) => member?.is_active !== false) : []),
    [familyMembers]
  );
  const defaultFamilyMemberId = useMemo(
    () => getDefaultFamilyMemberId(activeFamilyMembers, user),
    [activeFamilyMembers, user]
  );
  const budgetCurrency = useMemo(() => {
    const item = Array.isArray(feed?.items) ? feed.items.find((entry) => String(entry?.currency || "").trim()) : null;
    return String(item?.currency || "INR").toUpperCase();
  }, [feed?.items]);
  const currentSpent = useMemo(() => {
    const dashboardSpend = parseNumeric(budgetSnapshot?.total_spend);
    if (dashboardSpend !== null && dashboardSpend >= 0) {
      return dashboardSpend;
    }
    const items = Array.isArray(feed?.items) ? feed.items : [];
    return items.reduce((sum, item) => {
      if (String(item?.status || "").trim().toLowerCase() !== "confirmed") {
        return sum;
      }
      const amount = parseNumeric(item?.amount);
      return sum + (amount !== null ? amount : 0);
    }, 0);
  }, [budgetSnapshot?.total_spend, feed?.items]);

  function getSubcategoryOptions(categoryName) {
    const normalized = normalizeTaxonomyName(categoryName);
    if (!normalized) return [];
    const match = taxonomyCategories.find(
      (category) => normalizeTaxonomyName(category.name) === normalized
    );
    return (match?.subcategories || []).map((subcategory) => subcategory.name);
  }

  async function loadLedgerData() {
    setLoading(true);
    setError("");
    try {
      const taxonomyPromise = fetchTaxonomy(token)
        .then((data) => ({ data, error: "" }))
        .catch((err) => ({
          data: { categories: [] },
            error: String(err?.message || "Could not load taxonomy options."),
        }));
      const familyPromise = fetchFamilyMembers(token)
        .then((data) => ({ data, error: "" }))
        .catch((err) => ({
          data: { items: [] },
          error: String(err?.message || "Could not load family profile options."),
        }));

      const [feedData, dashboardData, householdData, taxonomyResult, familyResult] = await Promise.all([
        fetchExpenseFeed(token, { status: statusFilter, limit: 200 }),
        fetchDashboard(token, 6).catch(() => null),
        fetchHousehold(token).catch(() => null),
        taxonomyPromise,
        familyPromise,
      ]);
      setFeed(feedData);
      setTaxonomy(taxonomyResult.data);
      setTaxonomyError(taxonomyResult.error);
      setFamilyMembers(Array.isArray(familyResult?.data?.items) ? familyResult.data.items : []);
      setFamilyError(familyResult.error || "");
      const budgetNumeric = parseNumeric(householdData?.monthly_budget);
      setTotalBudget(budgetNumeric !== null && budgetNumeric > 0 ? Number(budgetNumeric.toFixed(2)) : DEFAULT_MONTHLY_BUDGET);
      if (dashboardData) {
        setBudgetSnapshot(dashboardData);
      }
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

  function openExpenseEdit(item) {
    setExpenseToEdit(item);
    setExpenseEditDraft({
      date_incurred: String(item?.date_incurred || todayIsoDate()),
      amount: item?.amount === null || item?.amount === undefined ? "" : String(item.amount),
      currency: String(item?.currency || "INR").toUpperCase(),
      attributed_family_member_id:
        String(item?.attributed_family_member_id || "").trim() || defaultFamilyMemberId,
      category: String(item?.category || ""),
      subcategory: String(item?.subcategory || ""),
      description: String(item?.description || item?.merchant_or_item || ""),
    });
    setEditError("");
  }

  function closeExpenseEdit() {
    if (updatingExpenseId) return;
    setExpenseToEdit(null);
    setEditError("");
  }

  function updateExpenseEditField(field, value) {
    setExpenseEditDraft((previous) => {
      const next = { ...previous, [field]: value };
      if (field === "currency") {
        next.currency = String(value || "").toUpperCase();
      }
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
    setEditError("");
  }

  async function handleSaveExpenseEdit() {
    if (!expenseToEdit) return;
    const amountNumeric = parseNumeric(expenseEditDraft.amount);
    if (amountNumeric === null || amountNumeric <= 0) {
      setEditError("Enter a valid amount greater than 0.");
      return;
    }
    const dateIncurred = String(expenseEditDraft.date_incurred || "").trim();
    if (!dateIncurred) {
      setEditError("Select a valid date.");
      return;
    }
    const currency = String(expenseEditDraft.currency || "").trim().toUpperCase();
    if (!currency) {
      setEditError("Currency is required.");
      return;
    }

    setUpdatingExpenseId(expenseToEdit.id);
    setError("");
    setMessage("");
    setEditError("");
    try {
      const payload = {
        amount: Number(amountNumeric.toFixed(2)),
        currency,
        attributed_family_member_id:
          String(expenseEditDraft.attributed_family_member_id || "").trim() || defaultFamilyMemberId || null,
        category: String(expenseEditDraft.category || "").trim(),
        subcategory: String(expenseEditDraft.subcategory || "").trim(),
        description: String(expenseEditDraft.description || "").trim(),
        date_incurred: dateIncurred,
      };
      const data = await updateExpense(token, expenseToEdit.id, payload);
      const warnings = Array.isArray(data?.warnings)
        ? data.warnings.map((warning) => String(warning || "").trim()).filter(Boolean)
        : [];
      const warningSuffix =
        warnings.length > 0
          ? ` (${warnings[0]}${warnings.length > 1 ? ` +${warnings.length - 1} more` : ""})`
          : "";
      setMessage(`${data?.message || "Expense updated successfully."}${warningSuffix}`);
      setExpenseToEdit(null);
      await loadLedgerData();
    } catch (err) {
      setEditError(err.message);
    } finally {
      setUpdatingExpenseId(null);
    }
  }

  return (
    <section className="panel">
      <p className="hint">Manage and review your recent household expenses.</p>
      <BudgetOverviewCard
        totalBudget={totalBudget}
        currentSpent={currentSpent}
        currency={budgetCurrency}
        periodMonth={budgetSnapshot?.period_month}
        onEditBudget={onOpenSettings}
      />
      {error && <p className="form-error">{error}</p>}
      {familyError && <p className="hint">{familyError}</p>}

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
                      <th>Belongs To</th>
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
                      const canEdit = user?.role === "admin" || item.logged_by_user_id === user?.id;
                      const canDelete = canEdit;
                      const isEditing = expenseToEdit?.id === item.id;
                      const savingThisRow = updatingExpenseId === item.id;
                      const rowBusy = savingThisRow || deletingExpenseId === item.id;
                      const subcategoryOptions = getSubcategoryOptions(expenseEditDraft.category);
                      return (
                        <tr key={item.id}>
                          <td>
                            {isEditing ? (
                              <input
                                className="ledger-inline-input"
                                type="date"
                                value={expenseEditDraft.date_incurred}
                                onChange={(e) => updateExpenseEditField("date_incurred", e.target.value)}
                                disabled={rowBusy}
                              />
                            ) : (
                              formatDateValue(item.date_incurred)
                            )}
                          </td>
                          <td>
                            <span className={isEditing ? "ledger-inline-loggedby" : ""}>{item.logged_by_name}</span>
                          </td>
                          <td>
                            {isEditing ? (
                              <select
                                className="ledger-inline-select"
                                value={expenseEditDraft.attributed_family_member_id || defaultFamilyMemberId || ""}
                                onChange={(e) =>
                                  updateExpenseEditField("attributed_family_member_id", e.target.value)
                                }
                                disabled={rowBusy || activeFamilyMembers.length === 0}
                              >
                                <option value="">
                                  {activeFamilyMembers.length === 0
                                    ? "No active profile"
                                    : "Select family member"}
                                </option>
                                {activeFamilyMembers.map((member) => (
                                  <option key={`ledger-member-${member.id}`} value={member.id}>
                                    {member.full_name} ({normalizeMemberType(member.member_type)})
                                  </option>
                                ))}
                              </select>
                            ) : (
                              item.attributed_family_member_name || item.logged_by_name
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <select
                                className="ledger-inline-select"
                                value={expenseEditDraft.category || ""}
                                onChange={(e) => updateExpenseEditField("category", e.target.value)}
                                disabled={rowBusy}
                              >
                                <option value="">Select category</option>
                                {expenseEditDraft.category &&
                                  !taxonomyCategoryOptions.some(
                                    (category) =>
                                      normalizeTaxonomyName(category) ===
                                      normalizeTaxonomyName(expenseEditDraft.category)
                                  ) && (
                                    <option value={expenseEditDraft.category}>
                                      {expenseEditDraft.category}
                                    </option>
                                  )}
                                {taxonomyCategoryOptions.map((category) => (
                                  <option key={category} value={category}>
                                    {category}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              item.category || "Other"
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <select
                                className="ledger-inline-select"
                                value={expenseEditDraft.subcategory || ""}
                                onChange={(e) => updateExpenseEditField("subcategory", e.target.value)}
                                disabled={rowBusy || !expenseEditDraft.category}
                              >
                                <option value="">Select subcategory</option>
                                {expenseEditDraft.subcategory &&
                                  !subcategoryOptions.some(
                                    (subcategory) =>
                                      normalizeTaxonomyName(subcategory) ===
                                      normalizeTaxonomyName(expenseEditDraft.subcategory)
                                  ) && (
                                    <option value={expenseEditDraft.subcategory}>
                                      {expenseEditDraft.subcategory}
                                    </option>
                                  )}
                                {subcategoryOptions.map((subcategory) => (
                                  <option key={`${expenseEditDraft.category}-${subcategory}`} value={subcategory}>
                                    {subcategory}
                                  </option>
                                ))}
                              </select>
                            ) : item.subcategory ? (
                              item.subcategory
                            ) : (
                              <span className="empty-value">-</span>
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="ledger-inline-input"
                                maxLength={255}
                                value={expenseEditDraft.description}
                                onChange={(e) => updateExpenseEditField("description", e.target.value)}
                                disabled={rowBusy}
                              />
                            ) : (
                              item.description || item.merchant_or_item || "-"
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <div className="ledger-inline-amount">
                                <input
                                  className="ledger-inline-input"
                                  type="number"
                                  min="0.01"
                                  step="0.01"
                                  value={expenseEditDraft.amount}
                                  onChange={(e) => updateExpenseEditField("amount", e.target.value)}
                                  disabled={rowBusy}
                                />
                                <input
                                  className="ledger-inline-input ledger-inline-currency"
                                  maxLength={8}
                                  value={expenseEditDraft.currency}
                                  onChange={(e) => updateExpenseEditField("currency", e.target.value)}
                                  disabled={rowBusy}
                                />
                              </div>
                            ) : (
                              formatCurrencyValue(item.amount, item.currency)
                            )}
                          </td>
                          <td>
                            <RecurringSwitch
                              checked={Boolean(item.is_recurring)}
                              disabled={isEditing || updatingRecurringId === item.id || updatingExpenseId === item.id}
                              onToggle={(nextValue) => handleToggleRecurring(item, nextValue)}
                              label={`Toggle recurring for expense on ${formatDateValue(item.date_incurred)}`}
                            />
                          </td>
                          <td>
                            <StatusPill status={item.status} compact />
                          </td>
                          <td>
                            {isEditing ? (
                              <div className="ledger-inline-actions">
                                <button
                                  type="button"
                                  className="btn-main"
                                  onClick={handleSaveExpenseEdit}
                                  disabled={rowBusy}
                                >
                                  {savingThisRow ? "Saving..." : "Save"}
                                </button>
                                <button
                                  type="button"
                                  className="btn-ghost"
                                  onClick={closeExpenseEdit}
                                  disabled={rowBusy}
                                >
                                  Cancel
                                </button>
                                {editError && <p className="form-error ledger-inline-error">{editError}</p>}
                                {taxonomyError && <p className="hint ledger-inline-hint">{taxonomyError}</p>}
                                {familyError && !taxonomyError && (
                                  <p className="hint ledger-inline-hint">{familyError}</p>
                                )}
                              </div>
                            ) : (
                              <div className="table-row-actions">
                                {canEdit && (
                                  <button
                                    type="button"
                                    className="icon-edit-button"
                                    onClick={() => openExpenseEdit(item)}
                                    aria-label={`Edit expense on ${formatDateValue(item.date_incurred)}`}
                                    title="Edit expense"
                                    disabled={deletingExpenseId === item.id || updatingExpenseId === item.id}
                                  >
                                    <EditIcon />
                                    <span className="sr-only">Edit expense</span>
                                  </button>
                                )}
                                {canDelete && (
                                  <button
                                    type="button"
                                    className="icon-delete-button"
                                    onClick={() => setExpenseToDelete(item)}
                                    aria-label={`Delete expense on ${formatDateValue(item.date_incurred)}`}
                                    title="Delete expense"
                                    disabled={deletingExpenseId === item.id || updatingExpenseId === item.id}
                                  >
                                    <TrashIcon />
                                    <span className="sr-only">Delete expense</span>
                                  </button>
                                )}
                              </div>
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
                  const canEdit = user?.role === "admin" || item.logged_by_user_id === user?.id;
                  const canDelete = canEdit;
                  const isEditing = expenseToEdit?.id === item.id;
                  const savingThisRow = updatingExpenseId === item.id;
                  const rowBusy = savingThisRow || deletingExpenseId === item.id;
                  const subcategoryOptions = getSubcategoryOptions(expenseEditDraft.category);
                  if (isEditing) {
                    return (
                      <article className="mobile-data-card" key={`mobile-${item.id}`}>
                        <p className="mobile-data-card-title">Edit Expense</p>
                        <div className="ledger-inline-mobile-editor">
                          <div className="mobile-data-row">
                            <span className="mobile-data-label">Logged By</span>
                            <span className="mobile-data-value ledger-inline-loggedby">{item.logged_by_name}</span>
                          </div>
                          <label className="ledger-inline-mobile-field">
                            Belongs To
                            <select
                              value={expenseEditDraft.attributed_family_member_id || defaultFamilyMemberId || ""}
                              onChange={(e) =>
                                updateExpenseEditField("attributed_family_member_id", e.target.value)
                              }
                              disabled={rowBusy || activeFamilyMembers.length === 0}
                            >
                              <option value="">
                                {activeFamilyMembers.length === 0
                                  ? "No active profile"
                                  : "Select family member"}
                              </option>
                              {activeFamilyMembers.map((member) => (
                                <option key={`mobile-ledger-member-${member.id}`} value={member.id}>
                                  {member.full_name} ({normalizeMemberType(member.member_type)})
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="ledger-inline-mobile-field">
                            Date
                            <input
                              type="date"
                              value={expenseEditDraft.date_incurred}
                              onChange={(e) => updateExpenseEditField("date_incurred", e.target.value)}
                              disabled={rowBusy}
                            />
                          </label>
                          <label className="ledger-inline-mobile-field">
                            Amount
                            <input
                              type="number"
                              min="0.01"
                              step="0.01"
                              value={expenseEditDraft.amount}
                              onChange={(e) => updateExpenseEditField("amount", e.target.value)}
                              disabled={rowBusy}
                            />
                          </label>
                          <label className="ledger-inline-mobile-field">
                            Currency
                            <input
                              maxLength={8}
                              value={expenseEditDraft.currency}
                              onChange={(e) => updateExpenseEditField("currency", e.target.value)}
                              disabled={rowBusy}
                            />
                          </label>
                          <label className="ledger-inline-mobile-field">
                            Category
                            <select
                              value={expenseEditDraft.category || ""}
                              onChange={(e) => updateExpenseEditField("category", e.target.value)}
                              disabled={rowBusy}
                            >
                              <option value="">Select category</option>
                              {expenseEditDraft.category &&
                                !taxonomyCategoryOptions.some(
                                  (category) =>
                                    normalizeTaxonomyName(category) ===
                                    normalizeTaxonomyName(expenseEditDraft.category)
                                ) && (
                                  <option value={expenseEditDraft.category}>{expenseEditDraft.category}</option>
                                )}
                              {taxonomyCategoryOptions.map((category) => (
                                <option key={`mobile-edit-${item.id}-${category}`} value={category}>
                                  {category}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="ledger-inline-mobile-field">
                            Subcategory
                            <select
                              value={expenseEditDraft.subcategory || ""}
                              onChange={(e) => updateExpenseEditField("subcategory", e.target.value)}
                              disabled={rowBusy || !expenseEditDraft.category}
                            >
                              <option value="">Select subcategory</option>
                              {expenseEditDraft.subcategory &&
                                !subcategoryOptions.some(
                                  (subcategory) =>
                                    normalizeTaxonomyName(subcategory) ===
                                    normalizeTaxonomyName(expenseEditDraft.subcategory)
                                ) && (
                                  <option value={expenseEditDraft.subcategory}>
                                    {expenseEditDraft.subcategory}
                                  </option>
                                )}
                              {subcategoryOptions.map((subcategory) => (
                                <option
                                  key={`mobile-edit-${item.id}-${expenseEditDraft.category}-${subcategory}`}
                                  value={subcategory}
                                >
                                  {subcategory}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="ledger-inline-mobile-field">
                            Description
                            <textarea
                              rows={3}
                              maxLength={255}
                              value={expenseEditDraft.description}
                              onChange={(e) => updateExpenseEditField("description", e.target.value)}
                              disabled={rowBusy}
                            />
                          </label>
                          <div className="mobile-data-actions ledger-inline-mobile-actions">
                            <button
                              type="button"
                              className="btn-ghost"
                              onClick={closeExpenseEdit}
                              disabled={rowBusy}
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              className="btn-main"
                              onClick={handleSaveExpenseEdit}
                              disabled={rowBusy}
                            >
                              {savingThisRow ? "Saving..." : "Save Changes"}
                            </button>
                          </div>
                          {editError && <p className="form-error ledger-inline-error">{editError}</p>}
                          {taxonomyError && <p className="hint ledger-inline-hint">{taxonomyError}</p>}
                          {familyError && !taxonomyError && (
                            <p className="hint ledger-inline-hint">{familyError}</p>
                          )}
                        </div>
                      </article>
                    );
                  }
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
                        <span className="mobile-data-label">Belongs To</span>
                        <span className="mobile-data-value">
                          {item.attributed_family_member_name || item.logged_by_name}
                        </span>
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
                            disabled={updatingRecurringId === item.id || updatingExpenseId === item.id}
                            onToggle={(nextValue) => handleToggleRecurring(item, nextValue)}
                            label={`Toggle recurring for expense on ${formatDateValue(item.date_incurred)}`}
                          />
                        </span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Status</span>
                        <span className="mobile-data-value">
                          <StatusPill status={item.status} compact />
                        </span>
                      </div>
                      {(canEdit || canDelete) && (
                        <div className="mobile-data-actions">
                          {canEdit && (
                            <button
                              type="button"
                              className="icon-edit-button"
                              onClick={() => openExpenseEdit(item)}
                              aria-label={`Edit expense on ${formatDateValue(item.date_incurred)}`}
                              title="Edit expense"
                              disabled={deletingExpenseId === item.id || updatingExpenseId === item.id}
                            >
                              <EditIcon />
                              <span className="sr-only">Edit expense</span>
                            </button>
                          )}
                          {canDelete && (
                            <button
                              type="button"
                              className="icon-delete-button"
                              onClick={() => setExpenseToDelete(item)}
                              aria-label={`Delete expense on ${formatDateValue(item.date_incurred)}`}
                              title="Delete expense"
                              disabled={deletingExpenseId === item.id || updatingExpenseId === item.id}
                            >
                              <TrashIcon />
                              <span className="sr-only">Delete expense</span>
                            </button>
                          )}
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

function SettingsPanel({ token, user, onUserUpdated }) {
  const [taxonomy, setTaxonomy] = useState({ categories: [] });
  const [loading, setLoading] = useState(false);
  const [taxonomyBusy, setTaxonomyBusy] = useState(false);
  const [householdNameInput, setHouseholdNameInput] = useState("");
  const [householdNameBusy, setHouseholdNameBusy] = useState(false);
  const [householdNameError, setHouseholdNameError] = useState("");
  const [householdNameMessage, setHouseholdNameMessage] = useState("");
  const [budgetInput, setBudgetInput] = useState(String(DEFAULT_MONTHLY_BUDGET));
  const [budgetBusy, setBudgetBusy] = useState(false);
  const [budgetError, setBudgetError] = useState("");
  const [budgetMessage, setBudgetMessage] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newSubcategoryByCategory, setNewSubcategoryByCategory] = useState({});
  const [editingCategoryId, setEditingCategoryId] = useState(null);
  const [editingCategoryName, setEditingCategoryName] = useState("");
  const [editingSubcategoryId, setEditingSubcategoryId] = useState(null);
  const [editingSubcategoryName, setEditingSubcategoryName] = useState("");
  const [expandedCategoryId, setExpandedCategoryId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const isAdmin = user?.role === "admin";
  const currentHouseholdName = String(user?.household_name || "").trim();

  async function loadTaxonomyData() {
    setLoading(true);
    setError("");
    try {
      const [taxonomyData, householdData] = await Promise.all([
        fetchTaxonomy(token),
        fetchHousehold(token).catch(() => null),
      ]);
      setTaxonomy(taxonomyData);
      const budgetNumeric = parseNumeric(householdData?.monthly_budget);
      setBudgetInput(
        String(
          budgetNumeric !== null && budgetNumeric > 0
            ? Number(budgetNumeric.toFixed(2))
            : DEFAULT_MONTHLY_BUDGET
        )
      );
      setBudgetError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTaxonomyData();
  }, [token]);

  useEffect(() => {
    setHouseholdNameInput(currentHouseholdName);
  }, [currentHouseholdName]);

  const taxonomyCategories = useMemo(
    () => (Array.isArray(taxonomy?.categories) ? taxonomy.categories : []),
    [taxonomy]
  );

  useEffect(() => {
    if (expandedCategoryId === null) return;
    if (!taxonomyCategories.some((category) => category.id === expandedCategoryId)) {
      setExpandedCategoryId(null);
    }
  }, [expandedCategoryId, taxonomyCategories]);

  const budgetPreviewValue = useMemo(() => {
    const numeric = parseNumeric(budgetInput);
    if (numeric === null || numeric <= 0) return DEFAULT_MONTHLY_BUDGET;
    return Number(numeric.toFixed(2));
  }, [budgetInput]);

  function toggleCategoryExpanded(categoryId) {
    setExpandedCategoryId((previous) => (previous === categoryId ? null : categoryId));
  }

  function updateSubcategoryInput(categoryId, value) {
    setNewSubcategoryByCategory((prev) => ({ ...prev, [categoryId]: value }));
  }

  async function handleSaveHouseholdName() {
    if (!isAdmin) {
      setHouseholdNameError("Only admin can rename household.");
      setHouseholdNameMessage("");
      return;
    }
    const nextName = householdNameInput.trim();
    if (nextName.length < 2) {
      setHouseholdNameError("Household name must be at least 2 characters.");
      setHouseholdNameMessage("");
      return;
    }
    setHouseholdNameBusy(true);
    setHouseholdNameError("");
    setHouseholdNameMessage("");
    try {
      const updatedUser = await updateHouseholdName(token, nextName);
      if (typeof onUserUpdated === "function") {
        onUserUpdated(updatedUser);
      }
      setHouseholdNameInput(String(updatedUser?.household_name || nextName));
      setHouseholdNameMessage(`Household name updated to "${String(updatedUser?.household_name || nextName)}".`);
    } catch (err) {
      setHouseholdNameError(err.message);
    } finally {
      setHouseholdNameBusy(false);
    }
  }

  async function handleSaveMonthlyBudget() {
    if (!isAdmin) {
      setBudgetError("Only admin can update monthly budget.");
      setBudgetMessage("");
      return;
    }
    const numeric = parseNumeric(budgetInput);
    if (numeric === null || numeric <= 0) {
      setBudgetError("Enter a valid monthly budget greater than 0.");
      setBudgetMessage("");
      return;
    }
    setBudgetBusy(true);
    setBudgetError("");
    setBudgetMessage("");
    try {
      const normalized = Number(numeric.toFixed(2));
      const household = await updateHouseholdBudget(token, normalized);
      const savedBudget = parseNumeric(household?.monthly_budget);
      const nextBudget =
        savedBudget !== null && savedBudget > 0 ? Number(savedBudget.toFixed(2)) : normalized;
      setBudgetInput(String(nextBudget));
      setBudgetMessage(`Monthly budget saved: ${formatCurrencyValue(nextBudget, "INR")}.`);
    } catch (err) {
      setBudgetError(err.message);
    } finally {
      setBudgetBusy(false);
    }
  }

  async function handleResetMonthlyBudget() {
    if (!isAdmin) {
      setBudgetError("Only admin can reset monthly budget.");
      setBudgetMessage("");
      return;
    }
    setBudgetBusy(true);
    setBudgetError("");
    setBudgetMessage("");
    try {
      const household = await updateHouseholdBudget(token, DEFAULT_MONTHLY_BUDGET);
      const savedBudget = parseNumeric(household?.monthly_budget);
      const nextBudget =
        savedBudget !== null && savedBudget > 0 ? Number(savedBudget.toFixed(2)) : DEFAULT_MONTHLY_BUDGET;
      setBudgetInput(String(nextBudget));
      setBudgetMessage(`Monthly budget reset to ${formatCurrencyValue(nextBudget, "INR")}.`);
    } catch (err) {
      setBudgetError(err.message);
    } finally {
      setBudgetBusy(false);
    }
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
    setExpandedCategoryId(category.id);
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

  async function handleConfirmDelete() {
    if (!deleteTarget || !isAdmin) return;
    setTaxonomyBusy(true);
    setError("");
    setMessage("");
    try {
      let data;
      if (deleteTarget.type === "category") {
        data = await deleteTaxonomyCategory(token, deleteTarget.category.id);
        setMessage(`Deleted category "${deleteTarget.category.name}".`);
      } else {
        data = await deleteTaxonomySubcategory(token, deleteTarget.subcategory.id);
        setMessage(`Deleted subcategory "${deleteTarget.subcategory.name}".`);
      }
      setTaxonomy(data);
      setDeleteTarget(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setTaxonomyBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-action-row">
        <button
          className="btn-ghost"
          type="button"
          onClick={loadTaxonomyData}
          disabled={loading || taxonomyBusy || householdNameBusy || budgetBusy}
        >
          Refresh
        </button>
      </div>
      <p className="hint">Configure monthly budget and categories used during AI expense capture and review.</p>
      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-ok">{message}</p>}
      <article className="result-card household-name-card">
        <div className="row draft-header">
          <h3>Household Name</h3>
          <span className="tool-chip">{isAdmin ? "Admin" : "Read only"}</span>
        </div>
        <div className="household-name-row">
          <label className="household-name-field">
            Name
            <input
              value={householdNameInput}
              onChange={(e) => {
                setHouseholdNameInput(e.target.value);
                setHouseholdNameError("");
                setHouseholdNameMessage("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void handleSaveHouseholdName();
                }
              }}
              maxLength={120}
              disabled={!isAdmin || householdNameBusy}
            />
          </label>
          {isAdmin && (
            <div className="household-name-actions">
              <button type="button" className="btn-main" onClick={() => void handleSaveHouseholdName()}>
                {householdNameBusy ? "Saving..." : "Save Name"}
              </button>
            </div>
          )}
        </div>
        <p className="household-name-preview">
          <HomeIcon />
          <span>{String(householdNameInput || currentHouseholdName || "My Home").trim()}</span>
        </p>
        {householdNameError && <p className="form-error">{householdNameError}</p>}
        {householdNameMessage && <p className="form-ok">{householdNameMessage}</p>}
      </article>
      <article className="result-card budget-settings-card">
        <div className="row draft-header">
          <h3>Monthly Budget</h3>
          <span className="tool-chip">Shared household</span>
        </div>
        <p className="hint">
          Set the monthly cap used in the Ledger budget overview. This is shared across all members in this household.
        </p>
        <div className="budget-settings-row">
          <label className="budget-settings-field">
            Budget Amount (INR)
            <input
              type="number"
              min="1"
              step="100"
              value={budgetInput}
              onChange={(e) => {
                setBudgetInput(e.target.value);
                setBudgetError("");
                setBudgetMessage("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void handleSaveMonthlyBudget();
                }
              }}
              disabled={!isAdmin || budgetBusy}
            />
          </label>
          <div className="budget-settings-actions">
            <button
              type="button"
              className="btn-main"
              onClick={() => void handleSaveMonthlyBudget()}
              disabled={!isAdmin || budgetBusy}
            >
              {budgetBusy ? "Saving..." : "Save Budget"}
            </button>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => void handleResetMonthlyBudget()}
              disabled={!isAdmin || budgetBusy}
            >
              Reset Default
            </button>
          </div>
        </div>
        <p className="budget-settings-preview">Preview: {formatCurrencyValue(budgetPreviewValue, "INR")}</p>
        {budgetError && <p className="form-error">{budgetError}</p>}
        {budgetMessage && <p className="form-ok">{budgetMessage}</p>}
      </article>

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
              {taxonomyCategories.map((category) => {
                const subcategoryCount = Array.isArray(category.subcategories) ? category.subcategories.length : 0;
                const isExpanded = expandedCategoryId === category.id;
                const isEditingCategory = editingCategoryId === category.id;

                return (
                  <article key={category.id} className="taxonomy-category">
                    <div
                      className={isExpanded ? "taxonomy-category-row expanded" : "taxonomy-category-row"}
                      role={isEditingCategory ? undefined : "button"}
                      tabIndex={isEditingCategory ? undefined : 0}
                      aria-expanded={isEditingCategory ? undefined : isExpanded}
                      onClick={isEditingCategory ? undefined : () => toggleCategoryExpanded(category.id)}
                      onKeyDown={
                        isEditingCategory
                          ? undefined
                          : (event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                toggleCategoryExpanded(category.id);
                              }
                            }
                      }
                    >
                      {isEditingCategory ? (
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
                          <div className="taxonomy-category-main">
                            <strong>{category.name}</strong>
                            {!isExpanded && (
                              <span className="taxonomy-subcount-badge">
                                {subcategoryCount} {subcategoryCount === 1 ? "subcategory" : "subcategories"}
                              </span>
                            )}
                          </div>
                          <div className="taxonomy-category-actions">
                            <div
                              className="member-actions"
                              onClick={(event) => event.stopPropagation()}
                              onKeyDown={(event) => event.stopPropagation()}
                            >
                              <button
                                type="button"
                                className="btn-ghost"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  startCategoryRename(category);
                                }}
                                disabled={taxonomyBusy}
                              >
                                Rename
                              </button>
                              <button
                                type="button"
                                className="icon-delete-button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setDeleteTarget({ type: "category", category });
                                }}
                                aria-label={`Delete category ${category.name}`}
                                title="Delete category"
                                disabled={taxonomyBusy}
                              >
                                <TrashIcon />
                                <span className="sr-only">Delete category</span>
                              </button>
                            </div>
                            <span
                              className={
                                isExpanded
                                  ? "taxonomy-category-chevron expanded"
                                  : "taxonomy-category-chevron"
                              }
                              aria-hidden="true"
                            >
                              v
                            </span>
                          </div>
                        </>
                      )}
                    </div>

                    <div
                      className={isExpanded ? "taxonomy-category-content expanded" : "taxonomy-category-content"}
                      aria-hidden={!isExpanded}
                    >
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
                                      className="icon-delete-button"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setDeleteTarget({ type: "subcategory", category, subcategory })
                                      }}
                                      aria-label={`Delete subcategory ${subcategory.name}`}
                                      title="Delete subcategory"
                                      disabled={taxonomyBusy}
                                    >
                                      <TrashIcon />
                                      <span className="sr-only">Delete subcategory</span>
                                    </button>
                                  </div>
                                </>
                              )}
                            </div>
                          ))
                        )}
                      </div>

                      <div className="taxonomy-create-row taxonomy-sub-create-row">
                        <input
                          value={newSubcategoryByCategory[category.id] || ""}
                          onChange={(e) => updateSubcategoryInput(category.id, e.target.value)}
                          placeholder={`Add subcategory for ${category.name}`}
                          disabled={taxonomyBusy}
                        />
                        <button
                          type="button"
                          className="icon-plus-button"
                          onClick={() => handleCreateSubcategory(category)}
                          aria-label={`Add subcategory under ${category.name}`}
                          title={`Add subcategory under ${category.name}`}
                          disabled={taxonomyBusy || !String(newSubcategoryByCategory[category.id] || "").trim()}
                        >
                          <PlusIcon />
                          <span className="sr-only">Add subcategory</span>
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </article>
      )}

      <ConfirmModal
        open={Boolean(deleteTarget)}
        title={
          deleteTarget?.type === "category"
            ? "Delete this category?"
            : "Delete this subcategory?"
        }
        description={
          deleteTarget?.type === "category"
            ? `Delete "${deleteTarget.category.name}" and all its subcategories?`
            : deleteTarget
              ? `Delete "${deleteTarget.subcategory.name}" under "${deleteTarget.category.name}"?`
              : ""
        }
        confirmLabel="Delete"
        busy={taxonomyBusy}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
      />
    </section>
  );
}

const INSIGHTS_CATEGORY_COLORS = [
  "#ff6b35",
  "#4ecdc4",
  "#a78bfa",
  "#f7c59f",
  "#ffd166",
  "#56cfe1",
  "#72efdd",
  "#c77dff",
];

const INSIGHTS_PERSON_COLORS = ["#ff6b35", "#4ecdc4", "#a78bfa", "#f7c59f"];

function clampValue(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function buildSmoothSvgPath(points, smoothing = 0.16) {
  if (!Array.isArray(points) || points.length === 0) return "";
  if (points.length === 1) {
    const point = points[0];
    return `M ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  }

  let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const previous = points[index - 1] || points[index];
    const current = points[index];
    const next = points[index + 1];
    const nextNext = points[index + 2] || next;
    const segmentMinY = Math.min(current.y, next.y);
    const segmentMaxY = Math.max(current.y, next.y);
    const controlOneX = current.x + (next.x - previous.x) * smoothing;
    const controlOneY = clampValue(
      current.y + (next.y - previous.y) * smoothing,
      segmentMinY,
      segmentMaxY
    );
    const controlTwoX = next.x - (nextNext.x - current.x) * smoothing;
    const controlTwoY = clampValue(
      next.y - (nextNext.y - current.y) * smoothing,
      segmentMinY,
      segmentMaxY
    );
    path += ` C ${controlOneX.toFixed(2)} ${controlOneY.toFixed(2)} ${controlTwoX.toFixed(2)} ${controlTwoY.toFixed(2)} ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
  }
  return path;
}

function describePieSlicePath(centerX, centerY, radius, startAngle, endAngle) {
  const angleDistance = endAngle - startAngle;
  if (angleDistance >= Math.PI * 2 - 0.001) {
    return `M ${centerX.toFixed(2)} ${centerY.toFixed(2)} m 0 ${(-radius).toFixed(2)} a ${radius.toFixed(2)} ${radius.toFixed(2)} 0 1 1 0 ${(radius * 2).toFixed(2)} a ${radius.toFixed(2)} ${radius.toFixed(2)} 0 1 1 0 ${(-radius * 2).toFixed(2)} Z`;
  }

  const startX = centerX + radius * Math.cos(startAngle);
  const startY = centerY + radius * Math.sin(startAngle);
  const endX = centerX + radius * Math.cos(endAngle);
  const endY = centerY + radius * Math.sin(endAngle);
  const largeArc = angleDistance > Math.PI ? 1 : 0;
  return `M ${centerX.toFixed(2)} ${centerY.toFixed(2)} L ${startX.toFixed(2)} ${startY.toFixed(2)} A ${radius.toFixed(2)} ${radius.toFixed(2)} 0 ${largeArc} 1 ${endX.toFixed(2)} ${endY.toFixed(2)} Z`;
}

function buildMonthRange(monthKey) {
  const normalized = String(monthKey || "").trim();
  const match = normalized.match(/^(\d{4})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return null;
  }
  const monthStart = `${match[1]}-${match[2]}-01`;
  const monthEndDate = new Date(year, month, 0);
  const monthEnd = `${match[1]}-${match[2]}-${String(monthEndDate.getDate()).padStart(2, "0")}`;
  return { start: monthStart, end: monthEnd };
}

function shiftMonthKey(monthKey, deltaMonths) {
  const normalized = String(monthKey || "").trim();
  const match = normalized.match(/^(\d{4})-(\d{2})$/);
  if (!match) return "";
  const year = Number(match[1]);
  const month = Number(match[2]);
  const delta = Number(deltaMonths || 0);
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12 ||
    !Number.isFinite(delta)
  ) {
    return "";
  }
  const shifted = new Date(year, month - 1 + delta, 1);
  if (Number.isNaN(shifted.getTime())) return "";
  return `${shifted.getFullYear()}-${String(shifted.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthOverMonthDelta(
  currentValue,
  previousValue,
  currencyCode = "INR",
  comparisonLabel = "vs previous month"
) {
  const current = parseNumeric(currentValue) ?? 0;
  const previous = parseNumeric(previousValue) ?? 0;
  const diff = current - previous;
  if (Math.abs(diff) < 0.01) return `No change ${comparisonLabel}`;
  if (previous <= 0) {
    if (current <= 0) return `No change ${comparisonLabel}`;
    return `+${formatCurrencyValue(Math.abs(diff), currencyCode)} ${comparisonLabel}`;
  }
  const percent = (diff / previous) * 100;
  const diffPrefix = diff > 0 ? "+" : "-";
  const percentPrefix = percent > 0 ? "+" : "-";
  return `${diffPrefix}${formatCurrencyValue(Math.abs(diff), currencyCode)} (${percentPrefix}${Math.abs(percent).toFixed(1)}%) ${comparisonLabel}`;
}

function DashboardPanel({
  token,
  embedded = false,
  onGoToLedger,
  onGoToRecurring,
  onOpenSettings,
}) {
  const [monthsBack, setMonthsBack] = useState(6);
  const [dashboard, setDashboard] = useState(null);
  const [totalBudget, setTotalBudget] = useState(DEFAULT_MONTHLY_BUDGET);
  const [categoryFeed, setCategoryFeed] = useState({ items: [], total_count: 0 });
  const [categoryFeedLoading, setCategoryFeedLoading] = useState(false);
  const [categoryFeedError, setCategoryFeedError] = useState("");
  const [expandedCategoryKey, setExpandedCategoryKey] = useState("");
  const [expandedPersonKey, setExpandedPersonKey] = useState("");
  const [activePieSliceKey, setActivePieSliceKey] = useState("");
  const [hoveredPieSliceKey, setHoveredPieSliceKey] = useState("");
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

  useEffect(() => {
    let cancelled = false;
    async function loadHouseholdBudget() {
      try {
        const householdData = await fetchHousehold(token);
        const budgetNumeric = parseNumeric(householdData?.monthly_budget);
        if (!cancelled && budgetNumeric !== null && budgetNumeric > 0) {
          setTotalBudget(Number(budgetNumeric.toFixed(2)));
        }
      } catch {
        // non-blocking: budget card can fall back to default budget
      }
    }
    loadHouseholdBudget();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    async function loadCategoryFeed() {
      setCategoryFeedLoading(true);
      setCategoryFeedError("");
      try {
        const data = await fetchExpenseFeed(token, {
          status: "confirmed",
          limit: 500,
        });
        if (!cancelled) {
          setCategoryFeed(data);
        }
      } catch (err) {
        if (!cancelled) {
          setCategoryFeed({ items: [], total_count: 0 });
          setCategoryFeedError(err.message);
        }
      } finally {
        if (!cancelled) {
          setCategoryFeedLoading(false);
        }
      }
    }
    loadCategoryFeed();
    return () => {
      cancelled = true;
    };
  }, [monthsBack, token]);

  useEffect(() => {
    setExpandedCategoryKey("");
    setExpandedPersonKey("");
    setActivePieSliceKey("");
    setHoveredPieSliceKey("");
  }, [monthsBack, dashboard?.period_month]);

  const dashboardPeriodMonth = String(dashboard?.period_month || "").trim();
  const periodStart = String(dashboard?.period_start || "").trim();
  const periodEnd = String(dashboard?.period_end || "").trim();

  const monthlyTrendSeries = useMemo(() => {
    const trend = Array.isArray(dashboard?.monthly_trend) ? dashboard.monthly_trend : [];
    return trend
      .map((entry) => ({
        month: String(entry?.month || "").trim(),
        total: Number(entry?.total || 0),
      }))
      .filter((entry) => Boolean(entry.month));
  }, [dashboard?.monthly_trend]);

  const trendWindowStartMonth =
    monthlyTrendSeries[0]?.month || dashboardPeriodMonth;
  const trendWindowEndMonth =
    monthlyTrendSeries[monthlyTrendSeries.length - 1]?.month || dashboardPeriodMonth;

  const trendWindowStart = useMemo(() => {
    return buildMonthRange(trendWindowStartMonth);
  }, [trendWindowStartMonth]);

  const trendWindowEnd = useMemo(() => {
    return buildMonthRange(trendWindowEndMonth);
  }, [trendWindowEndMonth]);

  const effectivePeriodStart = String(trendWindowStart?.start || periodStart).trim();
  const effectivePeriodEnd = String(trendWindowEnd?.end || periodEnd).trim();

  const periodFeedItems = useMemo(() => {
    if (!effectivePeriodStart || !effectivePeriodEnd) return [];
    const items = Array.isArray(categoryFeed?.items) ? categoryFeed.items : [];
    return items.filter((expense) => {
      const dateIncurred = String(expense?.date_incurred || "").trim();
      return Boolean(
        dateIncurred &&
          dateIncurred >= effectivePeriodStart &&
          dateIncurred <= effectivePeriodEnd
      );
    });
  }, [categoryFeed?.items, effectivePeriodEnd, effectivePeriodStart]);

  const categorySplit = useMemo(() => {
    const totals = new Map();
    const counts = new Map();
    for (const expense of periodFeedItems) {
      const amount = parseNumeric(expense?.amount);
      if (amount === null) continue;
      const category = String(expense?.category || "Other").trim() || "Other";
      totals.set(category, (totals.get(category) || 0) + amount);
      counts.set(category, (counts.get(category) || 0) + 1);
    }
    return Array.from(totals.entries())
      .map(([category, total]) => ({
        category,
        total: Number(total.toFixed(2)),
        count: counts.get(category) || 0,
      }))
      .sort((left, right) => right.total - left.total);
  }, [periodFeedItems]);

  const personSplit = useMemo(() => {
    const totals = new Map();
    for (const expense of periodFeedItems) {
      const amount = parseNumeric(expense?.amount);
      if (amount === null) continue;
      const memberId = String(expense?.attributed_family_member_id || "").trim();
      const memberName =
        String(expense?.attributed_family_member_name || expense?.logged_by_name || "Unknown").trim() ||
        "Unknown";
      const key = memberId || normalizeTaxonomyName(memberName) || "unknown";
      const existing = totals.get(key);
      if (existing) {
        existing.total += amount;
        existing.count += 1;
      } else {
        totals.set(key, {
          id: memberId || key,
          name: memberName,
          total: amount,
          count: 1,
        });
      }
    }
    return Array.from(totals.values())
      .map((item) => ({ ...item, total: Number(item.total.toFixed(2)) }))
      .sort((left, right) => right.total - left.total);
  }, [periodFeedItems]);

  const maxCategoryTotal = useMemo(() => {
    if (!categorySplit.length) return 1;
    return Math.max(...categorySplit.map((item) => Number(item?.total || 0)), 1);
  }, [categorySplit]);

  const maxUserTotal = useMemo(() => {
    if (!personSplit.length) return 1;
    return Math.max(...personSplit.map((item) => item.total), 1);
  }, [personSplit]);

  const dashboardCurrency = useMemo(() => {
    const inWindowCurrency = periodFeedItems.find((item) => String(item?.currency || "").trim());
    if (inWindowCurrency?.currency) return String(inWindowCurrency.currency).toUpperCase();
    const fallbackCurrency = Array.isArray(categoryFeed?.items)
      ? categoryFeed.items.find((item) => String(item?.currency || "").trim())
      : null;
    return String(fallbackCurrency?.currency || "INR").toUpperCase();
  }, [categoryFeed?.items, periodFeedItems]);

  const periodDayCount = useMemo(() => {
    if (!effectivePeriodStart || !effectivePeriodEnd) return 0;
    const startDate = new Date(`${effectivePeriodStart}T00:00:00`);
    const endDate = new Date(`${effectivePeriodEnd}T00:00:00`);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return 0;
    const diffMs = Math.max(endDate.getTime() - startDate.getTime(), 0);
    return Math.floor(diffMs / 86400000) + 1;
  }, [effectivePeriodEnd, effectivePeriodStart]);

  const periodTotalSpend = useMemo(() => {
    return Number(
      periodFeedItems
        .reduce((sum, expense) => {
          const amount = parseNumeric(expense?.amount);
          if (amount === null) return sum;
          return sum + amount;
        }, 0)
        .toFixed(2)
    );
  }, [periodFeedItems]);

  const periodExpenseCount = useMemo(() => {
    return periodFeedItems.reduce((count, expense) => {
      return parseNumeric(expense?.amount) === null ? count : count + 1;
    }, 0);
  }, [periodFeedItems]);

  const averagePerDay = useMemo(() => {
    if (periodDayCount <= 0) return 0;
    return periodTotalSpend / periodDayCount;
  }, [periodDayCount, periodTotalSpend]);

  const topCategory = useMemo(() => {
    if (!categorySplit.length) {
      return { category: "No category", total: 0 };
    }
    return categorySplit[0];
  }, [categorySplit]);

  const recurringSpend = useMemo(
    () =>
      periodFeedItems.reduce((sum, expense) => {
        const amount = parseNumeric(expense?.amount);
        if (!expense?.is_recurring || amount === null) return sum;
        return sum + amount;
      }, 0),
    [periodFeedItems]
  );

  const recurringShare = useMemo(() => {
    if (periodTotalSpend <= 0) return 0;
    return (recurringSpend / periodTotalSpend) * 100;
  }, [periodTotalSpend, recurringSpend]);

  const previousPeriodStartMonth = useMemo(() => {
    return shiftMonthKey(trendWindowStartMonth, -monthsBack);
  }, [monthsBack, trendWindowStartMonth]);

  const previousPeriodEndMonth = useMemo(() => {
    return shiftMonthKey(trendWindowEndMonth, -monthsBack);
  }, [monthsBack, trendWindowEndMonth]);

  const previousPeriodRangeStart = useMemo(() => {
    return buildMonthRange(previousPeriodStartMonth);
  }, [previousPeriodStartMonth]);

  const previousPeriodRangeEnd = useMemo(() => {
    return buildMonthRange(previousPeriodEndMonth);
  }, [previousPeriodEndMonth]);

  const previousPeriodStart = String(previousPeriodRangeStart?.start || "").trim();
  const previousPeriodEnd = String(previousPeriodRangeEnd?.end || "").trim();

  const previousPeriodFeedItems = useMemo(() => {
    if (!previousPeriodStart || !previousPeriodEnd) return [];
    const items = Array.isArray(categoryFeed?.items) ? categoryFeed.items : [];
    return items.filter((expense) => {
      const dateIncurred = String(expense?.date_incurred || "").trim();
      return Boolean(
        dateIncurred &&
          dateIncurred >= previousPeriodStart &&
          dateIncurred <= previousPeriodEnd
      );
    });
  }, [categoryFeed?.items, previousPeriodEnd, previousPeriodStart]);

  const previousPeriodTotalSpend = useMemo(() => {
    return Number(
      previousPeriodFeedItems
        .reduce((sum, expense) => {
          const amount = parseNumeric(expense?.amount);
          if (amount === null) return sum;
          return sum + amount;
        }, 0)
        .toFixed(2)
    );
  }, [previousPeriodFeedItems]);

  const previousRecurringSpend = useMemo(() => {
    return previousPeriodFeedItems.reduce((sum, expense) => {
      const amount = parseNumeric(expense?.amount);
      if (!expense?.is_recurring || amount === null) return sum;
      return sum + amount;
    }, 0);
  }, [previousPeriodFeedItems]);

  const previousTopCategorySpend = useMemo(() => {
    const categoryLabel = String(topCategory?.category || "").trim();
    if (!categoryLabel || categoryLabel === "No category") return 0;
    const normalizedCategory = normalizeTaxonomyName(categoryLabel);
    return previousPeriodFeedItems.reduce((sum, expense) => {
      const amount = parseNumeric(expense?.amount);
      if (amount === null) return sum;
      const expenseCategory = normalizeTaxonomyName(
        String(expense?.category || "Other").trim() || "Other"
      );
      if (expenseCategory !== normalizedCategory) return sum;
      return sum + amount;
    }, 0);
  }, [previousPeriodFeedItems, topCategory?.category]);

  const comparisonLabel =
    monthsBack === 1 ? "vs previous month" : `vs previous ${monthsBack} months`;

  const totalSpendDeltaLabel = useMemo(() => {
    return formatMonthOverMonthDelta(
      periodTotalSpend,
      previousPeriodTotalSpend,
      dashboardCurrency,
      comparisonLabel
    );
  }, [comparisonLabel, dashboardCurrency, periodTotalSpend, previousPeriodTotalSpend]);

  const recurringDeltaLabel = useMemo(() => {
    return formatMonthOverMonthDelta(
      recurringSpend,
      previousRecurringSpend,
      dashboardCurrency,
      comparisonLabel
    );
  }, [comparisonLabel, dashboardCurrency, previousRecurringSpend, recurringSpend]);

  const topCategoryDeltaLabel = useMemo(() => {
    if (!topCategory || String(topCategory.category || "").trim() === "No category") {
      return `No category data ${comparisonLabel}`;
    }
    return formatMonthOverMonthDelta(
      topCategory.total || 0,
      previousTopCategorySpend,
      dashboardCurrency,
      comparisonLabel
    );
  }, [comparisonLabel, dashboardCurrency, previousTopCategorySpend, topCategory]);

  const maxMonthlyTrendTotal = useMemo(() => {
    if (!monthlyTrendSeries.length) return 1;
    return Math.max(...monthlyTrendSeries.map((item) => item.total), 1);
  }, [monthlyTrendSeries]);

  const monthlyPatternBars = useMemo(() => {
    return monthlyTrendSeries.map((item) => {
      const rawHeight =
        maxMonthlyTrendTotal > 0 ? (Number(item.total || 0) / maxMonthlyTrendTotal) * 100 : 0;
      const height = Number(item.total || 0) <= 0 ? 0 : Math.max(rawHeight, 8);
      return {
        ...item,
        height,
        label: formatMonthYearValue(item.month, { monthStyle: "short", separator: " " }),
      };
    });
  }, [maxMonthlyTrendTotal, monthlyTrendSeries]);

  const categoryPie = useMemo(() => {
    const split = Array.isArray(categorySplit) ? categorySplit : [];
    const total = split.reduce((sum, item) => sum + Number(item?.total || 0), 0);
    const centerX = 120;
    const centerY = 120;
    const radius = 105;
    if (!split.length || total <= 0) {
      return {
        total: 0,
        centerX,
        centerY,
        radius,
        viewBox: "0 0 240 240",
        segments: [],
      };
    }

    let cursor = 0;
    const segments = split.map((item, index) => {
      const value = Number(item?.total || 0);
      const share = total > 0 ? value / total : 0;
      const startRatio = cursor;
      cursor += share;
      const endRatio = index === split.length - 1 ? 1 : cursor;
      const startAngle = startRatio * Math.PI * 2 - Math.PI / 2;
      const endAngle = endRatio * Math.PI * 2 - Math.PI / 2;
      const midAngle = startAngle + (endAngle - startAngle) / 2;
      const category = String(item?.category || "Other").trim() || "Other";
      const key = `${index}-${normalizeTaxonomyName(category) || "other"}`;
      return {
        key,
        category,
        total: value,
        percentage: share * 100,
        color: INSIGHTS_CATEGORY_COLORS[index % INSIGHTS_CATEGORY_COLORS.length],
        path: describePieSlicePath(centerX, centerY, radius, startAngle, endAngle),
        pullX: Math.cos(midAngle),
        pullY: Math.sin(midAngle),
      };
    });

    return {
      total,
      centerX,
      centerY,
      radius,
      viewBox: "0 0 240 240",
      segments,
    };
  }, [categorySplit]);

  const activePieSegment = useMemo(() => {
    const selectedKey = hoveredPieSliceKey || activePieSliceKey;
    if (!selectedKey) return null;
    return categoryPie.segments.find((segment) => segment.key === selectedKey) || null;
  }, [activePieSliceKey, categoryPie.segments, hoveredPieSliceKey]);

  const periodSubtitle = useMemo(() => {
    if (!effectivePeriodStart || !effectivePeriodEnd) return "Current month overview";
    return `${formatDateValue(effectivePeriodStart)} - ${formatDateValue(effectivePeriodEnd)}`;
  }, [effectivePeriodEnd, effectivePeriodStart]);

  const categoryEntriesByKey = useMemo(() => {
    const grouped = new Map();
    for (const expense of periodFeedItems) {
      const categoryLabel = String(expense?.category || "Other").trim() || "Other";
      const key = normalizeTaxonomyName(categoryLabel);
      if (!key) continue;
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key).push(expense);
    }

    return grouped;
  }, [periodFeedItems]);

  const personEntriesByKey = useMemo(() => {
    const grouped = new Map();
    for (const expense of periodFeedItems) {
      const memberId = String(expense?.attributed_family_member_id || "").trim();
      const memberLabel = String(
        expense?.attributed_family_member_name || expense?.logged_by_name || "Unknown"
      ).trim();
      const normalizedMemberKey = normalizeTaxonomyName(memberLabel) || "";

      const keys = [];
      if (memberId) {
        keys.push(memberId);
      }
      if (normalizedMemberKey) {
        keys.push(normalizedMemberKey);
      }
      if (!keys.length) {
        keys.push("unknown");
      }

      for (const key of keys) {
        if (!grouped.has(key)) {
          grouped.set(key, []);
        }
        grouped.get(key).push(expense);
      }
    }
    for (const entries of grouped.values()) {
      entries.sort((left, right) => {
        const leftDate = String(left?.date_incurred || "");
        const rightDate = String(right?.date_incurred || "");
        const dateComparison = rightDate.localeCompare(leftDate);
        if (dateComparison !== 0) return dateComparison;
        return Number(right?.amount || 0) - Number(left?.amount || 0);
      });
    }
    return grouped;
  }, [periodFeedItems]);

  function handleToggleCategory(categoryName) {
    const key = normalizeTaxonomyName(categoryName || "Other");
    if (!key) return;
    setExpandedCategoryKey((previous) => (previous === key ? "" : key));
  }

  function handleTogglePerson(person) {
    const key =
      String(person?.id || "").trim() ||
      normalizeTaxonomyName(String(person?.name || "").trim()) ||
      "";
    if (!key) return;
    setExpandedPersonKey((previous) => (previous === key ? "" : key));
  }

  const canGoToLedger = typeof onGoToLedger === "function";
  const canGoToRecurring = typeof onGoToRecurring === "function";
  const canOpenSettings = typeof onOpenSettings === "function";

  return (
    <section className={embedded ? "embedded-panel insights-overview-panel" : "panel"}>
      <div className="dashboard-header insights-dashboard-header">
        <div className="insights-heading-stack">
          {embedded ? <h3>Expense Dashboard</h3> : <h2>Expense Dashboard</h2>}
          <p className="insights-period-line">
            {periodSubtitle} | All amounts in {dashboardCurrency}
          </p>
        </div>
        <label className="insights-window-label">
          Trend Window
          <select
            value={monthsBack}
            onChange={(e) => setMonthsBack(Number(e.target.value))}
          >
            <option value={1}>This month</option>
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
          <BudgetOverviewCard
            totalBudget={totalBudget}
            currentSpent={Number(dashboard?.total_spend || 0)}
            currency={dashboardCurrency}
            periodMonth={dashboardPeriodMonth}
            onEditBudget={canOpenSettings ? onOpenSettings : undefined}
          />
          <div className="stats-grid insights-stats-row">
            <article className="stat-card insights-stat-card">
              <p className="insights-stat-label">Total Spent</p>
              <p className="insights-stat-value">
                {formatCurrencyValue(periodTotalSpend, dashboardCurrency)}
              </p>
              <p className="insights-stat-sub">{periodExpenseCount} transactions</p>
              <p className="insights-stat-sub insights-stat-delta">{totalSpendDeltaLabel}</p>
            </article>
            <article className="stat-card insights-stat-card">
              <p className="insights-stat-label">Avg / Day</p>
              <p className="insights-stat-value">{formatCurrencyValue(averagePerDay, dashboardCurrency)}</p>
              <p className="insights-stat-sub">over {periodDayCount || 0} days</p>
            </article>
            <article className="stat-card insights-stat-card">
              <p className="insights-stat-label">Top Category</p>
              <p className="insights-stat-value is-title">{topCategory.category || "No category"}</p>
              <p className="insights-stat-sub">
                {formatCurrencyValue(topCategory.total || 0, dashboardCurrency)}
              </p>
              <p className="insights-stat-sub insights-stat-delta">{topCategoryDeltaLabel}</p>
            </article>
            <article className="stat-card insights-stat-card">
              <p className="insights-stat-label">Recurring</p>
              <p className="insights-stat-value">{formatCurrencyValue(recurringSpend, dashboardCurrency)}</p>
              <p className="insights-stat-sub">{recurringShare.toFixed(0)}% of total</p>
              <p className="insights-stat-sub insights-stat-delta">{recurringDeltaLabel}</p>
            </article>
          </div>

          <div className="result-grid dashboard-grid insights-dashboard-grid">
            <div className="insights-layout-main">
              <article className="result-card insights-result-card insights-card-daily">
                <h3>Month-on-Month Spending Pattern</h3>
                {monthlyPatternBars.length === 0 ? (
                  <p>No monthly spend data for this window.</p>
                ) : (
                  <div
                    className="insights-monthly-pattern"
                    role="img"
                    aria-label="Month-on-month spending vertical bar chart"
                  >
                    <div className="insights-monthly-bars">
                      {monthlyPatternBars.map((item) => (
                        <div className="insights-month-bar" key={item.month}>
                          <div className="insights-month-bar-track">
                            <div
                              className="insights-month-bar-fill"
                              style={{ height: `${item.height}%` }}
                              title={`${item.label}: ${formatCurrencyValue(item.total, dashboardCurrency)}`}
                            />
                          </div>
                          <span className="insights-month-bar-label">{item.label}</span>
                          <span className="insights-month-bar-value">
                            {formatCompactCurrencyValue(item.total, dashboardCurrency)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </article>

            </div>

            <div className="insights-category-grid">
              <article className="result-card insights-result-card insights-pie-card">
                <h3>Spending by Category</h3>
                {categoryPie.segments.length === 0 ? (
                  <div className="insights-empty-actions">
                    <p>No confirmed expenses for this period.</p>
                    <div className="row">
                      {canGoToLedger && (
                        <button type="button" className="btn-main" onClick={onGoToLedger}>
                          Add expense
                        </button>
                      )}
                      {canGoToRecurring && (
                        <button type="button" className="btn-ghost" onClick={onGoToRecurring}>
                          Open recurring
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="insights-pie-shell">
                      <svg
                        className="insights-pie-chart"
                        viewBox={categoryPie.viewBox}
                        role="img"
                        aria-label="Spending by category pie chart"
                      >
                        {categoryPie.segments.map((segment) => {
                          const isActive = activePieSliceKey === segment.key;
                          const isHovered = hoveredPieSliceKey === segment.key;
                          const pullDistance = isActive ? 14 : isHovered ? 7 : 0;
                          const offsetX = segment.pullX * pullDistance;
                          const offsetY = segment.pullY * pullDistance;
                          const isDimmed =
                            Boolean(activePieSegment) && activePieSegment.key !== segment.key;
                          return (
                            <path
                              key={segment.key}
                              d={segment.path}
                              fill={segment.color}
                              className={
                                isActive
                                  ? isDimmed
                                    ? "insights-pie-slice is-active is-dimmed"
                                    : "insights-pie-slice is-active"
                                  : isDimmed
                                    ? "insights-pie-slice is-dimmed"
                                    : "insights-pie-slice"
                              }
                              style={{
                                transform: `translate(${offsetX.toFixed(2)}px, ${offsetY.toFixed(2)}px)`,
                              }}
                              tabIndex={0}
                              role="button"
                              aria-label={`${segment.category} ${segment.percentage.toFixed(1)} percent`}
                              onMouseEnter={() => setHoveredPieSliceKey(segment.key)}
                              onMouseLeave={() => setHoveredPieSliceKey("")}
                              onFocus={() => setHoveredPieSliceKey(segment.key)}
                              onBlur={() => setHoveredPieSliceKey("")}
                              onClick={() =>
                                setActivePieSliceKey((previous) =>
                                  previous === segment.key ? "" : segment.key
                                )
                              }
                              onKeyDown={(event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  setActivePieSliceKey((previous) =>
                                    previous === segment.key ? "" : segment.key
                                  );
                                }
                              }}
                            />
                          );
                        })}
                      </svg>

                      <div className="insights-pie-hole">
                        <span>{activePieSegment ? activePieSegment.category : "Total"}</span>
                        <strong>
                          {activePieSegment
                            ? `${activePieSegment.percentage.toFixed(1)}%`
                            : formatCompactCurrencyValue(categoryPie.total, dashboardCurrency)}
                        </strong>
                        {activePieSegment && (
                          <small>
                            {formatCompactCurrencyValue(activePieSegment.total, dashboardCurrency)}
                          </small>
                        )}
                      </div>
                    </div>

                    <div className="insights-pie-legend">
                      {categoryPie.segments.map((segment) => (
                        <button
                          type="button"
                          className={
                            activePieSegment?.key === segment.key
                              ? "insights-pie-legend-item active"
                              : "insights-pie-legend-item"
                          }
                          key={segment.key}
                          onMouseEnter={() => setHoveredPieSliceKey(segment.key)}
                          onMouseLeave={() => setHoveredPieSliceKey("")}
                          onFocus={() => setHoveredPieSliceKey(segment.key)}
                          onBlur={() => setHoveredPieSliceKey("")}
                          onClick={() =>
                            setActivePieSliceKey((previous) =>
                              previous === segment.key ? "" : segment.key
                            )
                          }
                        >
                          <span
                            className="insights-pie-legend-dot"
                            style={{ backgroundColor: segment.color }}
                            aria-hidden="true"
                          />
                          <span className="insights-pie-legend-name">{segment.category}</span>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </article>

              <article className="result-card insights-result-card insights-card-person">
                <h3>Spending by Family Member</h3>
                {personSplit.length === 0 ? (
                  <div className="insights-empty-actions">
                    <p>No family-member data yet.</p>
                    {canGoToLedger && (
                      <div className="row">
                        <button type="button" className="btn-ghost" onClick={onGoToLedger}>
                          View ledger
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="category-split-list insights-category-list insights-person-list">
                    {personSplit.map((item, index) => {
                      const personKey =
                        String(item.id || "").trim() ||
                        normalizeTaxonomyName(item.name) ||
                        `person-${index}`;
                      const normalizedPersonName = normalizeTaxonomyName(item.name);
                      const isExpanded = expandedPersonKey === personKey;
                      const entriesById = personEntriesByKey.get(personKey) || [];
                      const entriesByName = normalizedPersonName
                        ? personEntriesByKey.get(normalizedPersonName) || []
                        : [];
                      const personEntries =
                        entriesById.length > 0 && entriesByName.length > 0
                          ? Array.from(
                              new Map(
                                [...entriesById, ...entriesByName].map((expense) => [
                                  String(expense?.id || ""),
                                  expense,
                                ])
                              ).values()
                            )
                          : entriesById.length > 0
                            ? entriesById
                            : entriesByName;
                      const panelId = `person-expense-panel-${index}`;
                      const hiddenEntriesCount = Math.max(Number(item.count || 0) - personEntries.length, 0);

                      return (
                        <article
                          key={`${personKey}-${index}`}
                          className={
                            isExpanded
                              ? "category-split-item insights-category-item insights-person-item expanded"
                              : "category-split-item insights-category-item insights-person-item"
                          }
                        >
                          <button
                            type="button"
                            className="bar-row insights-bar-row category-bar-button insights-person-toggle"
                            aria-expanded={isExpanded}
                            aria-controls={panelId}
                            onClick={() => handleTogglePerson(item)}
                          >
                            <span>{item.name}</span>
                            <div className="bar-track">
                              <div
                                className="bar-fill accent"
                                style={{
                                  width: `${Math.max((item.total / maxUserTotal) * 100, 2)}%`,
                                  background: INSIGHTS_PERSON_COLORS[index % INSIGHTS_PERSON_COLORS.length],
                                }}
                              />
                            </div>
                            <div className="category-bar-tail">
                              <strong>{formatCurrencyValue(item.total, dashboardCurrency)}</strong>
                              <span className="category-chevron" aria-hidden="true">
                                v
                              </span>
                            </div>
                          </button>
                          {isExpanded && (
                            <div id={panelId} className="category-expense-panel insights-person-expense-panel">
                              {categoryFeedLoading ? (
                                <p className="category-expense-empty">Loading entries...</p>
                              ) : categoryFeedError ? (
                                <p className="category-expense-empty">{categoryFeedError}</p>
                              ) : personEntries.length === 0 ? (
                                <p className="category-expense-empty">
                                  No entries found in this period for this family member.
                                </p>
                              ) : (
                                <>
                                  <ul className="category-expense-list">
                                    {personEntries.map((expense) => (
                                      <li className="category-expense-item" key={`person-expense-${personKey}-${expense.id}`}>
                                        <div>
                                          <p className="category-expense-title">
                                            {expense.description ||
                                              expense.merchant_or_item ||
                                              "Expense entry"}
                                          </p>
                                          <p className="category-expense-meta">
                                            {formatDateValue(expense.date_incurred)}
                                            {expense.category ? ` | ${expense.category}` : ""}
                                            {expense.subcategory ? ` / ${expense.subcategory}` : ""}
                                            {expense.logged_by_name ? ` | logged by ${expense.logged_by_name}` : ""}
                                          </p>
                                        </div>
                                        <strong className="category-expense-amount">
                                          {formatCurrencyValue(expense.amount, expense.currency)}
                                        </strong>
                                      </li>
                                    ))}
                                  </ul>
                                  {hiddenEntriesCount > 0 && (
                                    <p className="category-expense-footnote">
                                      Showing {personEntries.length} of {item.count} entries for this family member.
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
              </article>

              <article className="result-card insights-result-card insights-card-category">
                <h3>Category Split</h3>
                {categorySplit.length === 0 ? (
                  <div className="insights-empty-actions">
                    <p>No confirmed expenses for this period.</p>
                    <div className="row">
                      {canGoToLedger && (
                        <button type="button" className="btn-main" onClick={onGoToLedger}>
                          Add expense
                        </button>
                      )}
                      {canGoToRecurring && (
                        <button type="button" className="btn-ghost" onClick={onGoToRecurring}>
                          Open recurring
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="category-split-list insights-category-list">
                    {categorySplit.map((item, index) => {
                      const categoryLabel = String(item.category || "Other").trim() || "Other";
                      const categoryKey = normalizeTaxonomyName(categoryLabel);
                      const isExpanded = expandedCategoryKey === categoryKey;
                      const categoryEntries = categoryEntriesByKey.get(categoryKey) || [];
                      const panelId = `category-detail-${index}`;
                      const hiddenEntriesCount = Math.max(item.count - categoryEntries.length, 0);

                      return (
                        <article
                          key={`${categoryLabel}-${index}`}
                          className={
                            isExpanded
                              ? "category-split-item insights-category-item expanded"
                              : "category-split-item insights-category-item"
                          }
                        >
                          <button
                            type="button"
                            className="bar-row insights-bar-row category-bar-button insights-category-toggle"
                            aria-expanded={isExpanded}
                            aria-controls={panelId}
                            onClick={() => handleToggleCategory(categoryLabel)}
                          >
                            <span>{categoryLabel}</span>
                            <div className="bar-track">
                              <div
                                className="bar-fill accent"
                                style={{
                                  width: `${Math.max((item.total / maxCategoryTotal) * 100, 2)}%`,
                                }}
                              />
                            </div>
                            <div className="category-bar-tail">
                              <strong>{formatCurrencyValue(item.total, dashboardCurrency)}</strong>
                              <span className="category-chevron" aria-hidden="true">
                                v
                              </span>
                            </div>
                          </button>
                          {isExpanded && (
                            <div id={panelId} className="category-expense-panel">
                              {categoryFeedLoading ? (
                                <p className="category-expense-empty">Loading entries...</p>
                              ) : categoryFeedError ? (
                                <p className="category-expense-empty">{categoryFeedError}</p>
                              ) : categoryEntries.length === 0 ? (
                                <p className="category-expense-empty">
                                  No entries found in this period for this category.
                                </p>
                              ) : (
                                <>
                                  <ul className="category-expense-list">
                                    {categoryEntries.map((expense) => (
                                      <li className="category-expense-item" key={expense.id}>
                                        <div>
                                          <p className="category-expense-title">
                                            {expense.description ||
                                              expense.merchant_or_item ||
                                              "Expense entry"}
                                          </p>
                                          <p className="category-expense-meta">
                                            {formatDateValue(expense.date_incurred)}
                                            {expense.subcategory ? ` | ${expense.subcategory}` : ""}
                                            {(expense.attributed_family_member_name || expense.logged_by_name)
                                              ? ` | ${expense.attributed_family_member_name || expense.logged_by_name}`
                                              : ""}
                                          </p>
                                        </div>
                                        <strong className="category-expense-amount">
                                          {formatCurrencyValue(expense.amount, expense.currency)}
                                        </strong>
                                      </li>
                                    ))}
                                  </ul>
                                  {hiddenEntriesCount > 0 && (
                                    <p className="category-expense-footnote">
                                      Showing {categoryEntries.length} of {item.count} entries for this category.
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
              </article>
            </div>
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

function formatCompactCurrencyValue(value, currencyCode = "INR") {
  const numeric = parseNumeric(value);
  if (numeric === null) return value;
  const normalized = String(currencyCode || "INR").toUpperCase();
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: normalized,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(numeric);
  } catch {
    return `${Math.round(numeric).toLocaleString()} ${normalized}`;
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
    <section className={embedded ? "embedded-panel insights-ai-panel" : "panel"}>
      <div className="insights-ai-hero">
        <div>
          <p className="kicker insights-ai-kicker">SQL Agent AI</p>
          {embedded ? <h3 className="insights-ai-title">Ask AI</h3> : <h2 className="insights-ai-title">Ask AI</h2>}
          <p className="hint insights-ai-subtitle">
            Natural language to validated SQL for chart/table-backed answers.
          </p>
        </div>
        <div className="insights-ai-hero-meta">
          <span className="insights-agent-badge">Enabled</span>
        </div>
      </div>

      <div className="prompt-pills insights-prompt-pills">
        {analyticsPrompts.map((prompt) => (
          <button
            type="button"
            key={prompt}
            className="btn-ghost prompt-pill insights-prompt-pill"
            onClick={() => void runQuery(prompt)}
            disabled={loading || analyticsVoiceTranscribing}
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="stack insights-ai-stack">
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
          className="btn-main insights-run-button"
          onClick={() => void runQuery()}
          disabled={loading || analyticsVoiceTranscribing}
        >
          {loading ? "Analyzing..." : "Run SQL Insight"}
        </button>
      </div>
      {loading && <p className="hint subtle-loader">Analyzing ledger data...</p>}
      {error && <p className="form-error">{error}</p>}

      {result && (
        <div className="analytics-results insights-analytics-results">
          <article className="result-card insights-result-card insights-assistant-card">
            <div className="row draft-header insights-assistant-header">
              <h3>Assistant</h3>
            </div>
            <article className="assistant-bubble markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {result.answer ?? ""}
              </ReactMarkdown>
            </article>
          </article>

          {result.chart?.points?.length > 0 && (
            <article className="result-card insights-result-card">
              <h3>{result.chart.title}</h3>
              <div className="bar-list insights-bar-list">
                {result.chart.points.map((point) => (
                  <div className="bar-row insights-bar-row" key={`${point.label}-${point.value}`}>
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
            <article className="result-card insights-result-card">
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

function InsightsViewSwitch({ activeView, onChange }) {
  return (
    <div className="insights-switch" role="tablist" aria-label="Insights Sections">
      <button
        type="button"
        role="tab"
        aria-selected={activeView === "overview"}
        className={activeView === "overview" ? "insights-tab active" : "insights-tab"}
        onClick={() => onChange("overview")}
      >
        Overview
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeView === "ai"}
        className={activeView === "ai" ? "insights-tab active" : "insights-tab"}
        onClick={() => onChange("ai")}
      >
        Ask AI <span className="insights-tab-pill">SQL</span>
      </button>
    </div>
  );
}

function InsightsPanel({ token, activeView, onGoToLedger, onGoToRecurring, onOpenSettings }) {
  return (
    <section className="panel insights-panel-shell">
      {activeView === "overview" ? (
        <DashboardPanel
          token={token}
          embedded
          onGoToLedger={onGoToLedger}
          onGoToRecurring={onGoToRecurring}
          onOpenSettings={onOpenSettings}
        />
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
  const [activeTab, setActiveTab] = useState("insights");
  const [sessionTransitionVisible, setSessionTransitionVisible] = useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [insightsView, setInsightsView] = useState("overview");
  const [capturePrefillText, setCapturePrefillText] = useState("");
  const [globalNotice, setGlobalNotice] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => safeStorageGet("expense_workspace_sidebar_collapsed") === "1"
  );

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    document.body.classList.add("app-theme-unified");
    return () => {
      document.body.classList.remove("app-theme-unified");
    };
  }, []);

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
    if (!auth?.token) return;
    if (String(auth?.user?.household_name || "").trim()) return;
    let cancelled = false;
    async function hydrateHouseholdName() {
      try {
        const household = await fetchHousehold(auth.token);
        const nextName = String(household?.household_name || "").trim();
        if (!nextName || cancelled) return;
        setAuth((previous) => ({
          ...previous,
          user: previous?.user ? { ...previous.user, household_name: nextName } : previous?.user,
        }));
      } catch {
        // no-op: this is a non-blocking enhancement for older stored sessions
      }
    }
    hydrateHouseholdName();
    return () => {
      cancelled = true;
    };
  }, [auth?.token, auth?.user?.household_name]);

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

  useEffect(() => {
    safeStorageSet("expense_workspace_sidebar_collapsed", sidebarCollapsed ? "1" : "0");
  }, [sidebarCollapsed]);

  const tabLabel = useMemo(() => {
    if (activeTab === "settings") return "Settings";
    return tabs.find((tab) => tab.id === activeTab)?.label ?? "Dashboard";
  }, [activeTab]);

  if (!auth?.token) {
    return (
      <RuntimeErrorBoundary>
        <main className="app-shell app-shell-unified">
          <Header user={null} onLogout={() => {}} />
          <AuthCard onAuthSuccess={setAuth} />
        </main>
      </RuntimeErrorBoundary>
    );
  }

  if (sessionTransitionVisible) {
    return (
      <RuntimeErrorBoundary>
        <main className="app-shell app-shell-unified">
          <SessionTransition />
        </main>
      </RuntimeErrorBoundary>
    );
  }

  return (
    <RuntimeErrorBoundary>
      <main className="app-shell app-shell-unified">
        <ToastNotice message={globalNotice} placement="top-right" />
        <Header
          user={auth.user}
          onQuickAdd={() => setQuickAddOpen(true)}
          onOpenSettings={() => setActiveTab("settings")}
          settingsActive={activeTab === "settings"}
          onLogout={() => {
            setAuth({ token: null, user: null });
            setActiveTab("insights");
            setQuickAddOpen(false);
            setCapturePrefillText("");
            setGlobalNotice("");
          }}
        />
        <section className={sidebarCollapsed ? "workspace sidebar-collapsed" : "workspace"}>
          <aside className="side-tabs">
            <button
              type="button"
              className="sidebar-toggle"
              onClick={() => setSidebarCollapsed((previous) => !previous)}
              aria-label={sidebarCollapsed ? "Expand workspace sidebar" : "Collapse workspace sidebar"}
            >
              <span className={sidebarCollapsed ? "sidebar-toggle-icon collapsed" : "sidebar-toggle-icon"} aria-hidden="true">
                {"<"}
              </span>
              <span className="sidebar-toggle-label">
                {sidebarCollapsed ? "Expand" : "Collapse"}
              </span>
            </button>
            <p className="kicker">Workspace</p>
            {tabs.map((tab) => (
              <button
                type="button"
                key={tab.id}
                className={activeTab === tab.id ? "tab active" : "tab"}
                onClick={() => setActiveTab(tab.id)}
                title={tab.label}
              >
                <span className="tab-icon" aria-hidden="true">
                  <TabIcon tabId={tab.id} />
                </span>
                <span className="tab-label">{tab.label}</span>
              </button>
            ))}
          </aside>
          <div className="content">
            <div className={activeTab === "insights" ? "content-header content-header-insights" : "content-header"}>
              <h1>{tabLabel}</h1>
              {activeTab === "insights" && (
                <div className="content-header-actions">
                  <InsightsViewSwitch activeView={insightsView} onChange={setInsightsView} />
                </div>
              )}
            </div>
            {activeTab === "capture" && (
              <ExpenseLogPanel
                token={auth.token}
                user={auth.user}
                prefilledText={capturePrefillText}
                onPrefilledTextConsumed={() => setCapturePrefillText("")}
              />
            )}
            {activeTab === "ledger" && (
              <LedgerPanel token={auth.token} user={auth.user} onOpenSettings={() => setActiveTab("settings")} />
            )}
            {activeTab === "recurring" && <RecurringPanel token={auth.token} user={auth.user} />}
            {activeTab === "insights" && (
              <InsightsPanel
                token={auth.token}
                activeView={insightsView}
                onGoToLedger={() => setActiveTab("ledger")}
                onGoToRecurring={() => setActiveTab("recurring")}
                onOpenSettings={() => setActiveTab("settings")}
              />
            )}
            {activeTab === "people" && <HouseholdPanel token={auth.token} user={auth.user} />}
            {activeTab === "settings" && (
              <SettingsPanel
                token={auth.token}
                user={auth.user}
                onUserUpdated={(updatedUser) =>
                  setAuth((previous) => ({
                    ...previous,
                    user: previous?.user ? { ...previous.user, ...updatedUser } : updatedUser,
                  }))
                }
              />
            )}
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
          user={auth.user}
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
  const householdLabel = String(user?.household_name || "My Home").trim() || "My Home";

  return (
    <header className="topbar">
      <div>
        <p className="kicker">LedgerLoop</p>
        <h2 className="topbar-home">
          <HomeIcon />
          <span>{householdLabel}</span>
        </h2>
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
