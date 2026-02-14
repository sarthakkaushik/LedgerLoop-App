const defaultBase = "http://127.0.0.1:8000";

function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL || defaultBase;
  return configured.trim().replace(/\/+$/, "");
}

function parseErrorPayload(data) {
  const message = data?.detail || data?.message || "Request failed";
  return typeof message === "string" ? message : JSON.stringify(message);
}

function parseDownloadFilename(contentDisposition) {
  if (!contentDisposition) return "expenses.csv";
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
  const basicMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
  if (basicMatch?.[1]) return basicMatch[1];
  return "expenses.csv";
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseErrorPayload(data));
  }
  return data;
}

export async function apiRequest(path, { method = "GET", token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse(res);
}

export async function registerUser(payload) {
  return apiRequest("/auth/register", { method: "POST", body: payload });
}

export async function loginUser(payload) {
  return apiRequest("/auth/login", { method: "POST", body: payload });
}

export async function joinHousehold(payload) {
  return apiRequest("/auth/join", { method: "POST", body: payload });
}

export async function createInviteCode(token) {
  return apiRequest("/auth/invite", { method: "POST", token });
}

export async function fetchHousehold(token) {
  return apiRequest("/auth/household", { token });
}

export async function deleteHouseholdMember(token, memberId) {
  return apiRequest(`/auth/members/${memberId}`, { method: "DELETE", token });
}

export async function parseExpenseText(token, text) {
  return apiRequest("/expenses/log", {
    method: "POST",
    token,
    body: { text },
  });
}

export async function confirmExpenses(token, payload) {
  return apiRequest("/expenses/confirm", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function fetchDashboard(token, monthsBack = 6) {
  return apiRequest(`/expenses/dashboard?months_back=${monthsBack}`, { token });
}

export async function fetchExpenseFeed(token, { status = "confirmed", limit = 100 } = {}) {
  const search = new URLSearchParams({
    status,
    limit: String(limit),
  });
  return apiRequest(`/expenses/list?${search.toString()}`, { token });
}

export async function deleteExpense(token, expenseId) {
  return apiRequest(`/expenses/${expenseId}`, { method: "DELETE", token });
}

export async function askAnalysis(token, text) {
  return apiRequest("/analysis/ask", {
    method: "POST",
    token,
    body: { text },
  });
}

export async function downloadExpenseCsv(token, { status = "confirmed" } = {}) {
  const search = new URLSearchParams({ status });
  const response = await fetch(`${getApiBaseUrl()}/expenses/export.csv?${search.toString()}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(parseErrorPayload(data));
  }

  const blob = await response.blob();
  const filename = parseDownloadFilename(response.headers.get("Content-Disposition"));
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}
