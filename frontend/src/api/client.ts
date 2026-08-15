import type {
  ActivityRange,
  ActivitySeriesResponse,
  DashboardOverview,
  Severity,
} from "../types/dashboard";
import type { EndpointDrawerData, EndpointsQuery, EndpointsResponse } from "../types/endpoints";
import type { AlertsQuery, AlertsResponse, IncidenteDrawerData } from "../types/alerts";
import type { IncidentClassification, IncidentesQuery, IncidentesResponse, IncidentStatus, ItemKind } from "../types/incidentes";
import type {
  DeployHoneyfilePayload,
  DeployHoneyfileResult,
  HoneyfileDetail,
  HoneyfilesQuery,
  HoneyfilesResponse,
} from "../types/honeyfiles";
import type { RuleUpdatePayload, RuleUpdateResult, RulesResponse } from "../types/rules";
import type { RespuestaResponse } from "../types/respuesta";
import type { GenerateReportPayload, GenerateReportResult, ReportsResponse } from "../types/reports";
import type {
  AgentSettingsResponse,
  AuditLogsResponse,
  EnrollmentTokenResult,
  UserCreatePayload,
  UserUpdatePayload,
  UsersResponse,
} from "../types/admin";

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

// GET /api/alerts -- lista dedicada para la pantalla Alertas en React.
export function fetchAlerts(query: AlertsQuery): Promise<AlertsResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.severity) params.set("severity", query.severity);
  if (query.status) params.set("status", query.status);
  if (query.since) params.set("since", query.since);
  if (query.rule) params.set("rule", query.rule);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.page_size ?? 15));
  return request<AlertsResponse>(`/api/alerts?${params.toString()}`);
}

// GET /api/incidentes/alert/{id}/drawer -- mismo endpoint real que ya
// usa /incidentes (Jinja2) para su panel lateral (sirve tanto un
// incidente agrupado como una alerta suelta); acá se reusa tal cual
// para el drawer de la pantalla Alertas.
export function fetchAlertDrawer(id: number): Promise<IncidenteDrawerData> {
  return request<IncidenteDrawerData>(`/api/incidentes/alert/${id}/drawer`);
}

// GET /api/incidentes -- versión JSON de /incidentes (Jinja2) para la
// pantalla Incidentes en React. Une incidentes agrupados y alertas
// sueltas en una sola lista (COMBINED_CTE), igual que la consola real.
export function fetchIncidentes(query: IncidentesQuery): Promise<IncidentesResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.severity) params.set("severity", query.severity);
  if (query.rule) params.set("rule", query.rule);
  if (query.since) params.set("since", query.since);
  params.set("page", String(query.page ?? 1));
  return request<IncidentesResponse>(`/api/incidentes?${params.toString()}`);
}

// GET /api/incidentes/{kind}/{id}/drawer -- versión genérica de
// fetchAlertDrawer, sirve tanto un incidente agrupado como una alerta
// suelta (mismo endpoint real que ya usa /incidentes en Jinja2).
export function fetchIncidenteDrawer(kind: ItemKind, id: number): Promise<IncidenteDrawerData> {
  return request<IncidenteDrawerData>(`/api/incidentes/${kind}/${id}/drawer`);
}

async function patchJson(path: string, body: unknown): Promise<void> {
  const res = await fetch(path, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || `Error ${res.status} al actualizar ${path}`);
  }
}

// PATCH /incidents/{id}/status -- endpoint real ya existente, usado
// hoy por incidentes.html. Cambia el ciclo de vida del incidente
// (Abierto -> En investigación -> Contenido -> Cerrado).
export function updateIncidentStatus(id: number, status: IncidentStatus): Promise<void> {
  return patchJson(`/incidents/${id}/status`, { status });
}

// PATCH /incidents/{id}/assign -- user_id null desasigna.
export function assignIncident(id: number, userId: number | null): Promise<void> {
  return patchJson(`/incidents/${id}/assign`, { user_id: userId });
}

// PATCH /incidents/{id}/classification -- separado del estado a
// propósito (ver INCIDENT_CLASSIFICATION_LABELS_ES en el servidor).
export function classifyIncident(id: number, classification: IncidentClassification): Promise<void> {
  return patchJson(`/incidents/${id}/classification`, { classification });
}

// POST /incidents -- escala una alerta suelta a incidente. Endpoint
// real ya existente (create_incident); si la alerta ya tenía
// incidente, el servidor devuelve ese en vez de crear uno nuevo.
export async function escalateAlertToIncident(alertId: number): Promise<{ incident_id: number }> {
  const res = await fetch("/incidents", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert_id: alertId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo escalar la alerta a incidente");
  }
  return res.json();
}

// GET /api/honeyfiles -- versión JSON de /honeyfiles (Jinja2), misma
// consulta e igual sin paginar (el inventario real hoy es chico).
export function fetchHoneyfiles(query: HoneyfilesQuery): Promise<HoneyfilesResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.os) params.set("os", query.os);
  if (query.agent_id) params.set("agent_id", String(query.agent_id));
  return request<HoneyfilesResponse>(`/api/honeyfiles?${params.toString()}`);
}

// GET /api/honeyfiles/{id}/detail -- endpoint real ya existente, ya
// usado por el drawer de honeyfiles.html.
export function fetchHoneyfileDetail(id: number): Promise<HoneyfileDetail> {
  return request<HoneyfileDetail>(`/api/honeyfiles/${id}/detail`);
}

// POST /api/honeyfiles/{id}/toggle-status -- alterna ACTIVE/INACTIVE
// (o desactiva uno ya activado/comprometido).
export async function toggleHoneyfileStatus(id: number): Promise<{ id: number; status: string; message: string }> {
  const res = await fetch(`/api/honeyfiles/${id}/toggle-status`, { method: "POST", credentials: "include" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.error || "No se pudo cambiar el estado");
  }
  return res.json();
}

// POST /api/honeyfiles/deploy -- crea una plantilla y la asigna a los
// agentes elegidos (o auto_deploy a futuro). La fila real en
// 'honeyfiles' se crea recién cuando el agente la escribe y lo
// confirma -- este endpoint no inserta un honeyfile "fantasma".
export async function deployHoneyfile(payload: DeployHoneyfilePayload): Promise<DeployHoneyfileResult> {
  const res = await fetch("/api/honeyfiles/deploy", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.error || "No se pudo desplegar el honeyfile");
  }
  return res.json();
}

// GET /api/rules -- versión JSON de Detección > Reglas en
// /configuracion (Jinja2), misma consulta exacta.
export function fetchRules(): Promise<RulesResponse> {
  return request<RulesResponse>("/api/rules");
}

// PATCH /rules/{id} -- endpoint real ya existente, ya usado por
// configuracion.html. Solo se manda lo que cambió.
export async function updateRule(id: number, payload: RuleUpdatePayload): Promise<RuleUpdateResult> {
  const res = await fetch(`/rules/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo actualizar la regla");
  }
  return res.json();
}

// GET /api/respuesta -- versión JSON del placeholder honesto de
// /respuesta (Jinja2): no hay aislamiento automático real, se
// muestran los incidentes críticos que requieren atención manual y el
// historial real (vacío hoy) de 'host_isolations'.
export function fetchRespuesta(): Promise<RespuestaResponse> {
  return request<RespuestaResponse>("/api/respuesta");
}

// GET /api/reportes -- versión JSON de /reportes (Jinja2), misma
// consulta exacta sobre 'reports'.
export function fetchReportes(page: number = 1): Promise<ReportsResponse> {
  return request<ReportsResponse>(`/api/reportes?page=${page}`);
}

// POST /reportes/generar -- endpoint real ya existente, ya usado por
// reportes.html. Genera el PDF/XLSX en el momento y lo guarda en disco.
export async function generateReport(payload: GenerateReportPayload): Promise<GenerateReportResult> {
  const res = await fetch("/reportes/generar", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo generar el informe");
  }
  return res.json();
}

// GET /api/users -- versión JSON de /usuarios (Jinja2), misma consulta
// exacta. Cualquier sesión válida puede leerla (igual que la real).
export function fetchUsers(): Promise<UsersResponse> {
  return request<UsersResponse>("/api/users");
}

// POST /users -- solo admin (endpoint real ya existente).
export async function createUser(payload: UserCreatePayload): Promise<{ message: string; user_id: number }> {
  const res = await fetch("/users", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo crear el usuario");
  }
  return res.json();
}

// PATCH /users/{id} -- solo admin (endpoint real ya existente).
export async function updateUserAccount(id: number, payload: UserUpdatePayload): Promise<{ message: string }> {
  const res = await fetch(`/users/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo actualizar el usuario");
  }
  return res.json();
}

// GET /api/config/agentes -- versión JSON de Configuración > Agentes.
export function fetchAgentSettings(): Promise<AgentSettingsResponse> {
  return request<AgentSettingsResponse>("/api/config/agentes");
}

// PATCH /settings/{key} -- endpoint real ya existente, whitelist
// KNOWN_SETTINGS (hoy solo 'agent_stale_seconds').
export async function updateSetting(key: string, value: string): Promise<{ message: string; key: string; value: string }> {
  const res = await fetch(`/settings/${key}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo actualizar el parámetro");
  }
  return res.json();
}

// GET /api/audit-logs -- versión JSON de Configuración > Auditoría.
export function fetchAuditLogs(page: number = 1): Promise<AuditLogsResponse> {
  return request<AuditLogsResponse>(`/api/audit-logs?page=${page}`);
}

// POST /enrollment-tokens -- solo admin (endpoint real ya existente).
// Token válido 15 minutos, se muestra una sola vez.
export async function createEnrollmentToken(): Promise<EnrollmentTokenResult> {
  const res = await fetch("/enrollment-tokens", { method: "POST", credentials: "include" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || "No se pudo generar el token");
  }
  return res.json();
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
