// Tipos alineados 1:1 con GET /api/incidentes (server/main.py::api_incidentes),
// la versión JSON de /incidentes (Jinja2) -- misma consulta (COMBINED_CTE),
// mismos filtros y KPIs, no una fuente de verdad paralela.

import type { Severity } from "./dashboard";

export type ItemKind = "incident" | "alert";

// Vocabulario unificado que ya usa incidentes.html (STATUS_BUCKET_LABELS_ES
// en el servidor) -- traduce los dos vocabularios reales que no coinciden
// (incidents.status vs alerts.status) a un único eje visual.
export type StatusBucket =
  | "nuevo"
  | "investigando"
  | "confirmado"
  | "contenido"
  | "cerrado"
  | "falso_positivo";

export interface CombinedItem {
  kind: ItemKind;
  id: number;
  code: string;
  created_at: string;
  raw_status: string;
  status_bucket: StatusBucket;
  status_label: string;
  hostname: string;
  ip_address: string;
  agent_id: number;
  severity: Severity | null;
  risk_score: number | null;
  rule_label: string;
  detection_count: number;
  assigned_to: number | null;
  assigned_to_name: string | null;
  // Agregado 2026-08-17 (ver PENDIENTES.md, "Corrección de tiempo real,
  // ordenamiento y consistencia", sección 12) -- estado más reciente de
  // aislamiento para este incidente (null para 'kind===alert' o si
  // nunca se ordenó ninguno). Lo que necesita el botón "Aislar" de esta
  // misma tabla (antes deshabilitado permanentemente) para no ofrecer
  // aislar de nuevo si ya hay una orden en curso/cumplida.
  isolation_status: string | null;
}

export interface IncidentesSummary {
  critical_incidents: number;
  active_alerts: number;
  isolated_hosts: number;
  mttr_minutes: number | null;
}

export interface FilterOption {
  value: string;
  label: string;
}

export interface AssignableUser {
  id: number;
  full_name: string;
}

export interface IncidentesFiltersData {
  status_options: FilterOption[];
  severity_options: FilterOption[];
  rule_options: FilterOption[];
  since_options: FilterOption[];
  assignable_users: AssignableUser[];
}

export interface IncidentesResponse {
  summary: IncidentesSummary;
  filters: IncidentesFiltersData;
  page: number;
  page_size: number;
  total_pages: number;
  filtered_total: number;
  items: CombinedItem[];
}

export interface IncidentesQuery {
  status?: StatusBucket | "";
  severity?: Severity | "";
  rule?: string;
  since?: "24h" | "7d" | "30d" | "";
  search?: string;
  // Ver AlertsQuery.view (2026-08-18, ver PENDIENTES.md, problema G) --
  // mismo criterio, acá "activas" excluye el bucket 'cerrado'.
  view?: "activas" | "todos";
  page?: number;
}

// Estados reales de 'incidents.status' (distintos de alerts.status --
// ver INCIDENT_STATUS_LABELS_ES en el servidor).
export type IncidentStatus = "OPEN" | "IN_PROGRESS" | "CONTAINED" | "CLOSED";

export type IncidentClassification =
  | "CONFIRMED"
  | "POSSIBLE_THREAT"
  | "FALSE_POSITIVE"
  | "LEGITIMATE_ACTIVITY"
  | "UNDETERMINED";
