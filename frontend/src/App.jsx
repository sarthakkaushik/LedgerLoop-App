import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  askAnalysis,
  confirmExpenses,
  createInviteCode,
  deleteExpense,
  deleteHouseholdMember,
  downloadExpenseCsv,
  fetchDashboard,
  fetchExpenseFeed,
  fetchHousehold,
  joinHousehold,
  loginUser,
  parseExpenseText,
  registerUser,
} from "./api";

const tabs = [
  { id: "log", label: "Chat Log" },
  { id: "dashboard", label: "Dashboard" },
  { id: "household", label: "Household" },
  { id: "analytics", label: "Analytics Chat" },
];

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

const initialJoin = {
  full_name: "",
  email: "",
  password: "",
  invite_code: "",
};

const expenseCategories = [
  "Groceries",
  "Food",
  "Dining",
  "Transport",
  "Fuel",
  "Shopping",
  "Utilities",
  "Rent",
  "EMI",
  "Healthcare",
  "Education",
  "Entertainment",
  "Travel",
  "Bills",
  "Gift",
  "Others",
];

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
        <p className="kicker">Family Ledger</p>
        <h1>LedgerLoop</h1>
        <p className="sub">
          Chat your expenses, review drafts, and tune your LLM parser from one place.
        </p>
        <div className="hero-visual" aria-hidden="true">
          <article className="mini-invoice">
            <p className="tiny">Shared Wallet</p>
            <strong>$1,876.50</strong>
            <small>Updated today</small>
            <div className="invoice-row">
              <span>Auto split</span>
              <span>ON</span>
            </div>
          </article>
          <article className="credit-panel">
            <p className="tiny">LedgerLoop Card</p>
            <strong>**** 2204</strong>
            <div className="card-footer">
              <span>VISA</span>
              <span>Secure</span>
            </div>
          </article>
        </div>
        <div className="logo-strip" aria-hidden="true">
          <span>autolog</span>
          <span>familysafe</span>
          <span>spendflow</span>
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

function ExpenseLogPanel({ token }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmResult, setConfirmResult] = useState(null);
  const [confirmKey, setConfirmKey] = useState("");
  const [error, setError] = useState("");

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
    setDrafts((prev) =>
      prev.map((draft, currentIndex) =>
        currentIndex === index ? { ...draft, [field]: value } : draft
      )
    );
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
      <h2>Chat Expense Drafting</h2>
      <p className="hint">
        Chat naturally, or log spends directly. Example:{" "}
        <code>Bought groceries for 500 and paid 1200 for electricity yesterday</code>
      </p>
      <div className="stack">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder="Type your message..."
        />
        <button className="btn-main" onClick={handleParse} disabled={loading}>
          {loading ? "Thinking..." : "Send"}
        </button>
      </div>
      {error && <p className="form-error">{error}</p>}

      {result && (
        <div className="result-grid">
          <div className="result-card">
            <h3>Assistant</h3>
            {result.assistant_message ? (
              <article className="assistant-bubble">{result.assistant_message}</article>
            ) : (
              <p>Draft parsing completed.</p>
            )}
            <p className="hint">
              Mode: <strong>{result.mode === "chat" ? "Conversation" : "Expense Parsing"}</strong>
            </p>
          </div>
          <div className="result-card">
            <h3>Clarifications</h3>
            <p>
              Status:{" "}
              <strong>{result.needs_clarification ? "Needs clarification" : "Ready to confirm"}</strong>
            </p>
            {result.clarification_questions.length === 0 ? (
              <p>No questions.</p>
            ) : (
              <ul>
                {result.clarification_questions.map((q, idx) => (
                  <li key={idx}>{q}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {drafts.length > 0 && (
        <div className="result-card draft-editor">
          <div className="row draft-header">
            <h3>Review and Confirm Drafts</h3>
            <button className="btn-main" onClick={handleConfirm} disabled={confirming}>
              {confirming ? "Confirming..." : "Confirm Expenses"}
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
                      !expenseCategories.some(
                        (category) =>
                          category.toLowerCase() === draft.category.toLowerCase()
                      ) && <option value={draft.category}>{draft.category}</option>}
                    {expenseCategories.map((category) => (
                      <option key={category} value={category}>
                        {category}
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
            <p className="form-ok">
              Confirmed {confirmResult.confirmed_count} expense(s)
              {confirmResult.idempotent_replay ? " (idempotent replay)." : "."}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function HouseholdPanel({ token, user }) {
  const [household, setHousehold] = useState(null);
  const [feed, setFeed] = useState(null);
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [loading, setLoading] = useState(false);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [deletingMemberId, setDeletingMemberId] = useState(null);
  const [deletingExpenseId, setDeletingExpenseId] = useState(null);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadHouseholdData() {
    setLoading(true);
    setError("");
    try {
      const [householdData, feedData] = await Promise.all([
        fetchHousehold(token),
        fetchExpenseFeed(token, { status: statusFilter, limit: 100 }),
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
    loadHouseholdData();
  }, [statusFilter, token]);

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
      await loadHouseholdData();
    } catch (err) {
      setError(err.message);
    } finally {
      setInviteBusy(false);
    }
  }

  async function handleDeleteMember(member) {
    const allowDelete = window.confirm(
      `Remove access for ${member.full_name} (${member.email})? Their past expenses will stay in the ledger.`
    );
    if (!allowDelete) return;

    setDeletingMemberId(member.id);
    setError("");
    setMessage("");
    try {
      const data = await deleteHouseholdMember(token, member.id);
      setMessage(data.message);
      await loadHouseholdData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingMemberId(null);
    }
  }

  async function handleDeleteExpense(item) {
    const canDelete = user?.role === "admin" || item.logged_by_user_id === user?.id;
    if (!canDelete) return;

    const allowDelete = window.confirm(
      `Delete this expense for ${item.date_incurred} (${Number(item.amount || 0).toFixed(2)} ${item.currency})?`
    );
    if (!allowDelete) return;

    setDeletingExpenseId(item.id);
    setError("");
    setMessage("");
    try {
      const data = await deleteExpense(token, item.id);
      setMessage(data.message || "Expense deleted.");
      await loadHouseholdData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingExpenseId(null);
    }
  }

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

  return (
    <section className="panel">
      <div className="dashboard-header">
        <h2>Household Collaboration</h2>
        <button className="btn-ghost" type="button" onClick={loadHouseholdData} disabled={loading}>
          Refresh
        </button>
      </div>
      <p className="hint">
        Use invite code to add your spouse. Everyone in this household can see who logged each expense.
      </p>

      {loading && <p>Loading household details...</p>}
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
              <p className="kicker">Visible Entries</p>
              <h3>{feed?.items?.length || 0}</h3>
              <p className="metric-sub">of {feed?.total_count || 0} total in filter</p>
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
                  <p className="hint">Share this code with your wife to join this household.</p>
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
                          onClick={() => handleDeleteMember(member)}
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
                <p>No expense rows in this filter.</p>
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
                      <strong>{item.total.toFixed(2)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>

          <article className="result-card household-ledger">
            <div className="row draft-header">
              <h3>Expense Ledger (Who Logged What)</h3>
              <div className="member-actions">
                <label>
                  Status
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="confirmed">Confirmed</option>
                    <option value="draft">Draft</option>
                    <option value="all">All</option>
                  </select>
                </label>
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
              <p>No expenses in this filter.</p>
            ) : (
              <div className="table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Logged By</th>
                      <th>Category</th>
                      <th>Description</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feed.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.date_incurred}</td>
                        <td>{item.logged_by_name}</td>
                        <td>{item.category || "Other"}</td>
                        <td>{item.description || item.merchant_or_item || "-"}</td>
                        <td>
                          {Number(item.amount || 0).toFixed(2)} {item.currency}
                        </td>
                        <td>{item.status}</td>
                        <td>
                          {(user?.role === "admin" || item.logged_by_user_id === user?.id) && (
                            <button
                              type="button"
                              className="btn-danger"
                              onClick={() => handleDeleteExpense(item)}
                              disabled={deletingExpenseId === item.id}
                            >
                              {deletingExpenseId === item.id ? "Deleting..." : "Delete"}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </>
      )}
    </section>
  );
}

function DashboardPanel({ token }) {
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
    <section className="panel">
      <div className="dashboard-header">
        <h2>Household Dashboard</h2>
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

      {loading && <p>Loading dashboard...</p>}
      {error && <p className="form-error">{error}</p>}

      {dashboard && !loading && (
        <>
          <div className="stats-grid">
            <article className="stat-card">
              <p className="kicker">Current Month</p>
              <h3>{dashboard.period_month}</h3>
              <p className="metric-value">{dashboard.total_spend.toFixed(2)}</p>
              <small>
                {dashboard.period_start} to {dashboard.period_end}
              </small>
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
                      <span>{item.month}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${Math.max((item.total / maxMonthlyTotal) * 100, 2)}%`,
                          }}
                        />
                      </div>
                      <strong>{item.total.toFixed(2)}</strong>
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
                      <strong>{item.total.toFixed(2)}</strong>
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
                      <strong>{item.total.toFixed(2)}</strong>
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

function AnalyticsPanel({ token }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showDebug, setShowDebug] = useState(false);

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
    const query = customText ?? text;
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setShowDebug(false);
    try {
      const data = await askAnalysis(token, query);
      setResult(data);
      if (!customText) setText("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <h2>Analytics Chat</h2>
      <p className="hint">
        Ask household spend questions. Tool routing is automatic and household-safe.
      </p>
      <div className="prompt-pills">
        {analyticsPrompts.map((prompt) => (
          <button
            type="button"
            key={prompt}
            className="btn-ghost prompt-pill"
            onClick={() => runQuery(prompt)}
            disabled={loading}
          >
            {prompt}
          </button>
        ))}
      </div>
      <div className="stack">
        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask anything about household spending..."
        />
        <button className="btn-main" onClick={() => runQuery()} disabled={loading}>
          {loading ? "Analyzing..." : "Ask Analytics"}
        </button>
      </div>
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
                    <strong>{point.value.toFixed(2)}</strong>
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
                <div className="table-wrap">
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
              )}
            </article>
          )}
        </div>
      )}
    </section>
  );
}

export default function App() {
  const [auth, setAuth] = useState(() => {
    const token = localStorage.getItem("expense_auth_token");
    const userRaw = localStorage.getItem("expense_auth_user");
    return {
      token,
      user: userRaw ? JSON.parse(userRaw) : null,
    };
  });
  const [activeTab, setActiveTab] = useState("log");

  useEffect(() => {
    if (auth?.token) {
      localStorage.setItem("expense_auth_token", auth.token);
    } else {
      localStorage.removeItem("expense_auth_token");
    }
    if (auth?.user) {
      localStorage.setItem("expense_auth_user", JSON.stringify(auth.user));
    } else {
      localStorage.removeItem("expense_auth_user");
    }
  }, [auth]);

  const tabLabel = useMemo(
    () => tabs.find((tab) => tab.id === activeTab)?.label ?? "Chat Log",
    [activeTab]
  );

  if (!auth?.token) {
    return (
      <main className="app-shell">
        <Header user={null} onLogout={() => {}} />
        <AuthCard onAuthSuccess={setAuth} />
      </main>
    );
  }

  return (
    <main className="app-shell">
      <Header user={auth.user} onLogout={() => setAuth({ token: null, user: null })} />
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
              {tab.label}
            </button>
          ))}
        </aside>
        <div className="content">
          <div className="content-header">
            <h1>{tabLabel}</h1>
          </div>
          {activeTab === "log" && <ExpenseLogPanel token={auth.token} />}
          {activeTab === "dashboard" && <DashboardPanel token={auth.token} />}
          {activeTab === "household" && <HouseholdPanel token={auth.token} user={auth.user} />}
          {activeTab === "analytics" && <AnalyticsPanel token={auth.token} />}
        </div>
      </section>
    </main>
  );
}

function Header({ user, onLogout }) {
  return (
    <header className="topbar">
      <div>
        <p className="kicker">Family Ledger</p>
        <h2>Expense Tracker</h2>
      </div>
      <div className="topbar-actions">
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
