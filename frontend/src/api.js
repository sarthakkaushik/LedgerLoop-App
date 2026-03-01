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

export async function updateHouseholdName(token, householdName) {
  return apiRequest("/auth/household/name", {
    method: "PATCH",
    token,
    body: { household_name: householdName },
  });
}

export async function updateHouseholdBudget(token, monthlyBudget) {
  return apiRequest("/auth/household/budget", {
    method: "PATCH",
    token,
    body: { monthly_budget: monthlyBudget },
  });
}

export async function fetchTaxonomy(token) {
  return apiRequest("/settings/taxonomy", { token });
}

export async function createTaxonomyCategory(token, payload) {
  return apiRequest("/settings/taxonomy/categories", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function updateTaxonomyCategory(token, categoryId, payload) {
  return apiRequest(`/settings/taxonomy/categories/${categoryId}`, {
    method: "PATCH",
    token,
    body: payload,
  });
}

export async function deleteTaxonomyCategory(token, categoryId) {
  return apiRequest(`/settings/taxonomy/categories/${categoryId}`, {
    method: "DELETE",
    token,
  });
}

export async function createTaxonomySubcategory(token, categoryId, payload) {
  return apiRequest(`/settings/taxonomy/categories/${categoryId}/subcategories`, {
    method: "POST",
    token,
    body: payload,
  });
}

export async function updateTaxonomySubcategory(token, subcategoryId, payload) {
  return apiRequest(`/settings/taxonomy/subcategories/${subcategoryId}`, {
    method: "PATCH",
    token,
    body: payload,
  });
}

export async function deleteTaxonomySubcategory(token, subcategoryId) {
  return apiRequest(`/settings/taxonomy/subcategories/${subcategoryId}`, {
    method: "DELETE",
    token,
  });
}

export async function deleteHouseholdMember(token, memberId) {
  return apiRequest(`/auth/members/${memberId}`, { method: "DELETE", token });
}

export async function fetchFamilyMembers(token, { includeInactive = false } = {}) {
  const search = new URLSearchParams();
  if (includeInactive) {
    search.set("include_inactive", "true");
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return apiRequest(`/family-members${suffix}`, { token });
}

export async function createFamilyMember(token, payload) {
  return apiRequest("/family-members", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function updateFamilyMember(token, familyMemberId, payload) {
  return apiRequest(`/family-members/${familyMemberId}`, {
    method: "PATCH",
    token,
    body: payload,
  });
}

export async function deleteFamilyMemberProfile(token, familyMemberId) {
  return apiRequest(`/family-members/${familyMemberId}`, {
    method: "DELETE",
    token,
  });
}

export async function parseExpenseText(token, text) {
  return apiRequest("/expenses/log", {
    method: "POST",
    token,
    body: { text },
  });
}

export async function transcribeExpenseAudio(token, formData) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${getApiBaseUrl()}/expenses/transcribe-audio`, {
    method: "POST",
    headers,
    body: formData,
  });
  return parseResponse(res);
}

export async function confirmExpenses(token, payload) {
  return apiRequest("/expenses/confirm", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function fetchDashboard(token, monthsBack = 6) {
  const search = new URLSearchParams({ months_back: String(monthsBack) });
  const timezone =
    typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "";
  if (timezone) {
    search.set("client_timezone", timezone);
  }
  return apiRequest(`/expenses/dashboard?${search.toString()}`, { token });
}

export async function fetchExpenseFeed(
  token,
  { status = "confirmed", limit = 100, recurringOnly = false } = {}
) {
  const search = new URLSearchParams({
    status,
    limit: String(limit),
  });
  if (recurringOnly) {
    search.set("recurring_only", "true");
  }
  return apiRequest(`/expenses/list?${search.toString()}`, { token });
}

export async function deleteExpense(token, expenseId) {
  return apiRequest(`/expenses/${expenseId}`, { method: "DELETE", token });
}

export async function updateExpense(token, expenseId, payload) {
  return apiRequest(`/expenses/${expenseId}`, {
    method: "PATCH",
    token,
    body: payload,
  });
}

export async function updateExpenseRecurring(token, expenseId, isRecurring) {
  return apiRequest(`/expenses/${expenseId}/recurring`, {
    method: "PATCH",
    token,
    body: { is_recurring: Boolean(isRecurring) },
  });
}

export async function createRecurringExpense(token, payload) {
  return apiRequest("/expenses/recurring", {
    method: "POST",
    token,
    body: payload,
  });
}

export async function askAnalysis(token, text) {
  return apiRequest("/analysis/ask", {
    method: "POST",
    token,
    body: { text },
  });
}

export async function downloadExpenseCsv(
  token,
  { status = "confirmed", recurringOnly = false } = {}
) {
  const search = new URLSearchParams({ status });
  if (recurringOnly) {
    search.set("recurring_only", "true");
  }
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

export async function fetchAdminOverview(token) {
  return apiRequest("/admin/overview", { token });
}

export async function fetchAdminSchema(token) {
  return apiRequest("/admin/schema", { token });
}

export async function downloadAdminAllData(token) {
  const response = await fetch(`${getApiBaseUrl()}/admin/export/all.zip`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(parseErrorPayload(data));
  }

  const blob = await response.blob();
  const filename = parseDownloadFilename(response.headers.get("Content-Disposition")) || "all_tables.zip";
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export async function downloadAdminTableCsv(token, tableName) {
  const normalizedTable = String(tableName || "").trim().toLowerCase();
  if (!normalizedTable) {
    throw new Error("Table name is required.");
  }
  const response = await fetch(
    `${getApiBaseUrl()}/admin/export/${encodeURIComponent(normalizedTable)}.csv`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(parseErrorPayload(data));
  }

  const blob = await response.blob();
  const filename =
    parseDownloadFilename(response.headers.get("Content-Disposition")) || `${normalizedTable}.csv`;
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}
