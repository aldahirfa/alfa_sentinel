import type {
  ActivityRange,
  ActivitySeriesResponse,
  DashboardOverview,
  Severity,
} from "../types/dashboard";
import type { EndpointDrawerData, EndpointsQuery, EndpointsResponse } from "../types/endpoints";

// Todo pasa por el proxy de Vite (ver vite.config.ts) -- rutas
// relativas, sin host, para que la cookie de sesión viaje como
// same-origin de verdad.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "include" });

  if (res.status === 401) {
    throw new ApiError(401, "Sesión expirada o no iniciada");
  }
  if (!res.ok) {
    throw new ApiError(res.status, `Error ${res.status} al pedir ${path}`);
  }

  return res.json() as Promise<T>;
}

export function fetchDashboardOverview(): Promise<DashboardOverview> {
  return request<DashboardOverview>("/api/dashboard/overview");
}

export interface MeResponse {
  id: number;
  username: string;
  full_name: string;
  roles: string[];
}

// Sesión real (GET /me, ya existía en el servidor) -- se usa para
// mostrar el nombre de quien inició sesión en el topbar en vez de un
// texto genérico fijo.
export function fetchMe(): Promise<MeResponse> {
  return request<MeResponse>("/me");
}

export function fetchActivitySeries(
  range: ActivityRange
): Promise<ActivitySeriesResponse> {
  return request<ActivitySeriesResponse>(
    `/api/dashboard/activity-series?period=${range}`
  );
}

export interface OpenAlert {
  id: number;
  severity: Severity;
  title: string;
  hostname: string;
  created_at: string;
}

export interface OpenAlertsResponse {
  count: number;
  alerts: OpenAlert[];
}

// GET /alerts/open -- endpoint real ya existente en el servidor,
// pensado justo para esto (alertas NEW, hasta 10). Se usa para el
// dropdown de la campana del topbar.
export function fetchOpenAlerts(): Promise<OpenAlertsResponse> {
  return request<OpenAlertsResponse>("/alerts/open");
}

export async function logout(): Promise<void> {
  await fetch("/logout", { method: "POST", credentials: "include" });
}

// GET /api/endpoints -- lista para la pantalla Endpoints en React.
export function fetchEndpoints(query: EndpointsQuery): Promise<EndpointsResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.risk) params.set("risk", query.risk);
  if (query.os_family) params.set("os_family", query.os_family);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.page_size ?? 10));
  return request<EndpointsResponse>(`/api/endpoints?${params.toString()}`);
}

// GET /api/endpoints/{id}/drawer -- mismo endpoint real que ya usa
// server/templates/endpoints.html (Jinja2) para su panel lateral, no
// se creó nada paralelo.
export function fetchEndpointDrawer(id: number): Promise<EndpointDrawerData> {
  return request<EndpointDrawerData>(`/api/endpoints/${id}/drawer`);
}

export interface LoginResult {
  username: string;
  roles: string[];
}

export async function login(username: string, password: string): Promise<LoginResult> {
  const res = await fetch("/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo iniciar sesión");
  }

  // El servidor devuelve {message, username, roles} -- lo usamos para
  // mostrar el nombre real de quien inició sesión en el topbar, en
  // vez de un texto genérico fijo.
  return res.json() as Promise<LoginResult>;
}
