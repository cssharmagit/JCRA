export type Expense = {
  id: string;
  merchant: string;
  meta: string;
  amount: string;
  mark: string;
  tone: string;
  status: "ready" | "attention";
  policyLabel: string;
};

export type OpenQuestion = {
  id: string;
  expenseId: string;
  field: string;
  prompt: string;
  reason: string;
};

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

export type Claim = {
  id: string;
  title: string;
  subtitle: string;
  status: "DRAFT" | "READY" | "SUBMITTED";
  currency: string;
  total: string;
  totalNote: string | null;
  readiness: number;
  headline: string;
  detail: string;
  intro: string;
  submittable: boolean;
  openQuestion: OpenQuestion | null;
  expenses: Expense[];
  summary: { processed: number; ready: number; needsReview: number; duplicates: number };
  messages: ChatMessage[];
  preview: { filename: string; confidence: string; merchant: string; amount: string } | null;
  notice: string | null;
  provider: string;
  employee: { name: string; dept: string };
  uiAction?: "focus_chat" | "show_expenses";
};

export type Insights = {
  currency: string;
  total: number;
  expenseCount: number;
  claimCount: number;
  byCategory: { category: string; total: number }[];
  byClaim: { id: string; title: string; status: string; expenseCount: number; total: number }[];
};

export async function getInsights(): Promise<Insights> {
  const response = await fetch("/api/insights");
  if (!response.ok) throw new Error("Could not load insights.");
  return response.json();
}

export function reopenClaim(id: string): Promise<Claim> {
  return request(`/claims/${id}/reopen`, { method: "POST" });
}

async function request(path: string, init?: RequestInit): Promise<Claim> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `The assistant could not finish that (${response.status}).`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      /* keep the fallback */
    }
    throw new Error(detail);
  }
  return response.json();
}

export function getClaim(): Promise<Claim> {
  return request("/claims/active");
}

export function uploadFiles(files: FileList | File[]): Promise<Claim> {
  const body = new FormData();
  Array.from(files).forEach((file) => body.append("files", file));
  return request("/claims/active/documents", { method: "POST", body });
}

export function sendMessage(text: string): Promise<Claim> {
  return request("/claims/active/messages", { method: "POST", body: JSON.stringify({ text }) });
}

export type ClaimSummary = {
  id: string;
  title: string;
  subtitle: string;
  status: "DRAFT" | "READY" | "SUBMITTED";
  expenseCount: number;
  createdAt: string;
  submittedAt: string | null;
};

export type ExpenseDetail = {
  id: string;
  merchant: string | null;
  date: string | null;
  amount: string | null;
  currency: string | null;
  category: string | null;
  categoryDetail: string | null;
  attendees: string | null;
  purpose: string | null;
  status: string;
  policyLabel: string;
  confidence: number | null;
  summary: string;
  findings: { severity: string; code: string; message: string }[];
  missing: { field: string; question: string; reason: string }[];
  isDuplicate: boolean;
  duplicateReason: string;
  overrideReason: string | null;
  overrideBy: string | null;
  document: { id: string; filename: string; mediaType: string; extractedText: string } | null;
};

export async function listClaims(): Promise<{ activeId: string | null; claims: ClaimSummary[] }> {
  const response = await fetch("/api/claims");
  if (!response.ok) throw new Error("Could not load claims.");
  return response.json();
}

export function newClaim(): Promise<Claim> {
  return request("/claims", { method: "POST" });
}

export function openClaim(id: string): Promise<Claim> {
  return request(`/claims/${id}/open`, { method: "POST" });
}

export function deleteClaim(id: string): Promise<Claim> {
  return request(`/claims/${id}`, { method: "DELETE" });
}

export async function getExpenseDetail(id: string): Promise<ExpenseDetail> {
  const response = await fetch(`/api/claims/active/expenses/${id}`);
  if (!response.ok) throw new Error("Could not load that expense.");
  return response.json();
}

export function deleteExpense(id: string): Promise<Claim> {
  return request(`/claims/active/expenses/${id}`, { method: "DELETE" });
}

export function renameClaim(title: string): Promise<Claim> {
  return request("/claims/active/title", { method: "PATCH", body: JSON.stringify({ title }) });
}

export function overrideExpense(id: string, reason: string): Promise<Claim> {
  return request(`/claims/active/expenses/${id}/override`, { method: "POST", body: JSON.stringify({ reason }) });
}

export type Conversation = {
  claimId: string;
  title: string;
  status: string;
  messageCount: number;
  lastAt: string;
  messages: { role: string; content: string; created_at: string }[];
};

export async function listConversations(q?: string): Promise<{ conversations: Conversation[] }> {
  const response = await fetch(`/api/conversations${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  if (!response.ok) throw new Error("Could not load conversations.");
  return response.json();
}

export function answerQuestion(id: string, text: string): Promise<Claim> {
  return request(`/claims/active/questions/${id}/answer`, { method: "POST", body: JSON.stringify({ text }) });
}

export function submitClaim(): Promise<Claim> {
  return request("/claims/active/submit", { method: "POST" });
}
