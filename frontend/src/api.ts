const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, msg: string) {
    super(msg);
    this.status = status;
  }
}

function token(): string | null {
  return localStorage.getItem("tripcast.token");
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(
      res.status,
      (body && (body.detail ?? body.message)) ?? res.statusText,
    );
  }
  return body as T;
}

// --- types (mirror backend schemas) -------------------------------------

export interface User {
  id: number;
  email: string;
  telegram_chat_id: string | null;
  telegram_enabled: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface TripPlace {
  id?: number;
  visit_date: string;
  order_index: number;
  sido: string;
  sigungu: string;
  name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  nx?: number | null;
  ny?: number | null;
  /** 주변 지역/유가 검색 반경(m). 기본 10,000 */
  radius_m?: number;
}

export interface Trip {
  id: number;
  title: string;
  start_date: string;
  end_date: string;
  telegram_chat_id: string | null;
  telegram_enabled: boolean;
  notify_lead_days: number;
  places: TripPlace[];
  created_at: string;
}

// --- endpoints -----------------------------------------------------------

export const AuthApi = {
  register: (data: {
    email: string;
    password: string;
    telegram_chat_id?: string;
    telegram_enabled?: boolean;
  }) => api<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (email: string, password: string) =>
    api<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
};

export const UserApi = {
  me: () => api<User>("/users/me"),
  update: (data: {
    password?: string;
    telegram_chat_id?: string;
    telegram_enabled?: boolean;
  }) => api<User>("/users/me", { method: "PATCH", body: JSON.stringify(data) }),
};

export const TripApi = {
  list: () => api<Trip[]>("/trips"),
  get: (id: number) => api<Trip>(`/trips/${id}`),
  create: (data: Omit<Trip, "id" | "created_at">) =>
    api<Trip>("/trips", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<Trip>) =>
    api<Trip>(`/trips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  remove: (id: number) => api<void>(`/trips/${id}`, { method: "DELETE" }),
};
