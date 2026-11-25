/** Typed API client for the chat-pdf backend. */

const BASE = "/api";

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  isForm = false,
): Promise<T> {
  const headers: HeadersInit = isForm ? {} : { "Content-Type": "application/json" };
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers,
    body: isForm ? (body as FormData) : body != null ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail ?? res.statusText), { status: res.status });
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// --- Types ---

export interface Account {
  account_id: string;
  email: string;
}

export interface Document {
  id: string;
  original_filename: string;
  status: "uploading" | "processing" | "ready" | "failed" | "soft_deleted";
  page_count: number | null;
  size_bytes: number;
  failure_reason: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citation_pages: number[];
  citation_status: string;
  created_at: string;
}

export interface Conversation {
  document_id: string;
  messages: Message[];
}

// --- Auth ---

export const auth = {
  signup: (email: string, password: string) =>
    request<Account>("POST", "/auth/signup", { email, password }),
  login: (email: string, password: string) =>
    request<Account>("POST", "/auth/login", { email, password }),
  logout: () => request<void>("POST", "/auth/logout"),
  me: () => request<Account>("GET", "/auth/me"),
};

// --- Documents ---

export const documents = {
  list: () =>
    request<{ documents: Document[] }>("GET", "/documents").then((r) => r.documents),
  get: (id: string) => request<Document>("GET", `/documents/${id}`),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ document_id: string; status: string }>("POST", "/documents", fd, true);
  },
  delete: (id: string) => request<Document>("DELETE", `/documents/${id}`),
  purge: (id: string) => request<void>("DELETE", `/documents/${id}/purge`),
  restore: (id: string) => request<Document>("POST", `/documents/${id}/restore`),
};

// --- Conversation ---

export const conversation = {
  history: (documentId: string) =>
    request<Conversation>("GET", `/documents/${documentId}/conversation`),
  ask: (documentId: string, question: string) =>
    request<Message>("POST", `/documents/${documentId}/questions`, { question }),
};
