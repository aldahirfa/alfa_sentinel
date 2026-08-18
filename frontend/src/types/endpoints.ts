// Tipos alineados 1:1 con lo que devuelve server/main.py::api_endpoints
// (GET /api/endpoints). Si el contrato del backend cambia, este
// archivo es el primer lugar a actualizar.

import type { Severity } from "./dashboard";

export type ConnStatus = "ONLINE" | "OFFLINE" | "ISOLATED";
export type AgentHealth = "HEALTHY" | "WARNING" | "OFFLINE";

export interface EndpointListItem {
  id: number;
  hostname: string;
  operating_system: string;
  os_version: string;
  ip_address: string;
  conn_status: ConnStatus;
  risk: Severity;
  agent_health: AgentHealth;
  last_seen_ago: string;
  alerts_count: number;
  last_activity_ago: string | null;
}

export interface EndpointsSummary {
  total: number;
  online: number;
  offline: number;
  isolated: number;
  critical: number;
}

export interface EndpointsResponse {
  summary: EndpointsSummary;
  os_families: string[];
  page: number;
  page_size: number;
  total_pages: number;
  filtered_total: number;
  endpoints: EndpointListItem[];
}

export interface EndpointsQuery {
  search?: string;
  status?: ConnStatus | "";
  risk?: Severity | "";
  os_family?: string;
  page?: number;
  page_size?: number;
}

// Alineado 1:1 con GET /api/endpoints/{id}/drawer -- este mismo
// endpoint ya lo consume server/templates/endpoints.html (Jinja2)
// para el drawer real que ya existe en la consola vieja, así que
// estos campos son honestos: no se inventó ninguno, y algunos
// (agent_health, last_seen_ago, alerts_active, incidents_total/active,
// honeyfiles_violated_ago) se agregaron al backend reusando fórmulas
// ya existentes en otras partes del sistema (ver PENDIENTES.md).
export interface LatestAlert {
  title: string;
  severity: Severity;
  created_at: string;
  file_path: string | null;
  rule_name: string;
}

export interface EndpointDrawerData {
  id: number;
  agent_code: string;
  hostname: string;
  operating_system: string;
  os_version: string;
  architecture: string | null;
  ip_address: string;
  mac_address: string | null;
  agent_version: string;
  status: string;
  agent_health: AgentHealth;
  last_seen_at: string;
  last_seen_ago: string;
  enrolled_at: string;
  risk_bucket: Severity;
  risk_score: number;
  is_isolated: boolean;
  // Fila más reciente de host_isolations para este endpoint (o null) --
  // lo que necesita el botón "Liberar" para llamar a
  // POST /host-isolations/{id}/release. Agregados 2026-08-17, ver
  // PENDIENTES.md, "Corrección de tiempo real, ordenamiento y
  // consistencia".
  isolation_id: number | null;
  isolation_status: string | null;
  // Incidente activo más reciente de este endpoint, o null si no hay
  // ninguno -- lo que necesita el botón "Aislar endpoint manualmente"
  // para saber a qué incidente asociar la orden (host_isolations.
  // incident_id es NOT NULL). Agregado 2026-08-17, ver PENDIENTES.md,
  // "Aislamiento de host -- modo development, laboratorio y producción".
  active_incident_id: number | null;
  alerts_active: number;
  incidents_total: number;
  incidents_active: number;
  honeyfiles_total: number;
  honeyfiles_violated_file: string | null;
  honeyfiles_violated_ago: string | null;
  latest_alert: LatestAlert | null;
}
