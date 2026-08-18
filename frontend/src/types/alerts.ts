// Tipos alineados 1:1 con lo que devuelven server/main.py::api_alerts
// (GET /api/alerts) y get_incidente_drawer (GET
// /api/incidentes/alert/{id}/drawer, reusado tal cual para el drawer
// de una alerta suelta -- no se creó un endpoint de detalle nuevo).

import type { Severity } from "./dashboard";

export type AlertStatus = "NEW" | "ACKNOWLEDGED" | "ESCALATED" | "CLOSED" | "FALSE_POSITIVE";

export interface AlertListItem {
  id: number;
  severity: Severity;
  // Título GENERAL por nivel de riesgo (ACTIVIDAD ANÓMALA/SOSPECHOSA,
  // POSIBLE ATAQUE DE RANSOMWARE, ATAQUE DE RANSOMWARE PROBABLE) --
  // ya no es el nombre de una regla individual (2026-08-18, ver
  // PENDIENTES.md, "Corrección definitiva en la lógica y presentación
  // de ALERTAS"). Qué reglas contribuyeron se ve en el detalle
  // (IncidenteDrawerData.rules).
  title: string;
  hostname: string;
  risk_score: number;
  status: AlertStatus;
  status_label: string;
  created_at: string;
  incident_id: number | null;
  // Reemplaza a 'rule_name' (2026-08-18, ver PENDIENTES.md) -- mostrar
  // el nombre de UNA sola regla acá era exactamente el problema
  // reportado ("por qué dice Consumo de CPU si la alerta es de Acceso
  // Honeyfile"), porque esa regla se elegía de forma arbitraria cuando
  // había más de una vinculada a la misma alerta. La tabla ahora solo
  // indica CUÁNTAS reglas contribuyeron; el detalle las lista todas.
  rule_count: number;
  agent_id: number;
}

export interface AlertsSummary {
  total: number;
  active: number;
  critical: number;
  investigating: number;
  resolved: number;
}

export interface RuleOption {
  value: string;
  label: string;
}

export interface AlertsResponse {
  summary: AlertsSummary;
  rules: RuleOption[];
  page: number;
  page_size: number;
  total_pages: number;
  filtered_total: number;
  alerts: AlertListItem[];
}

export interface AlertsQuery {
  search?: string;
  severity?: Severity | "";
  status?: AlertStatus | "";
  since?: "24h" | "7d" | "30d" | "";
  rule?: string;
  // Vista operativa vs. historial (2026-08-18, ver PENDIENTES.md,
  // problema G): "activas" (default) excluye Cerrada/Falso positivo sin
  // borrar nada de la base; "todos" trae el historial completo. Si
  // 'status' viene elegido explícitamente, ese filtro manda igual.
  view?: "activas" | "todos";
  page?: number;
  page_size?: number;
}

export interface TimelineEntry {
  at: string;
  kind: "event" | "honeyfile";
  label: string;
  detail: string;
}

export interface MatchedRule {
  rule_name: string;
  weight_applied: number;
  matched_at: string;
}

// Alerta que dio origen a un incidente agrupado (la primera por fecha
// entre las vinculadas) -- solo viene poblado cuando kind === "incident".
export interface OriginAlert {
  id: number;
  code: string;
  severity: Severity | null;
  risk_score: number | null;
}

// Proceso involucrado (2026-08-18, ver PENDIENTES.md, "Corrección
// definitiva en la lógica y presentación de ALERTAS", sección 5) --
// correlación real por ventana de tiempo contra 'events'/
// 'honeyfile_activations' del mismo agente, NUNCA inventado. Cualquier
// campo puede venir null -- el frontend debe mostrar "No disponible",
// nunca inferir o rellenar con datos de otra fuente (ej. "el proceso
// estaba corriendo en el endpoint" no es lo mismo que "este proceso
// causó esta alerta"). 'executable_path'/'username' hoy SIEMPRE vienen
// null -- ninguna tabla real los guarda todavía (ver PENDIENTES.md,
// "Atribución de proceso en eventos de archivo").
export interface InvolvedProcess {
  process_name: string | null;
  process_id: number | null;
  executable_path: string | null;
  username: string | null;
}

// Respuesta de /api/incidentes/{kind}/{id}/drawer -- compartida entre
// "incident" y "alert". Para una alerta suelta, classification/
// assigned_to siempre vienen null (no aplican).
export interface IncidenteDrawerData {
  kind: "incident" | "alert";
  id: number;
  code: string;
  title: string;
  description: string | null;
  status: string;
  status_label: string;
  severity: Severity | null;
  risk_score: number | null;
  classification: string | null;
  classification_label: string | null;
  assigned_to: number | null;
  assigned_to_name: string | null;
  hostname: string;
  ip_address: string;
  operating_system: string;
  is_online: boolean;
  agent_id: number;
  detection_count: number;
  is_honeyfile: boolean;
  incident_id: number | null;
  resolved_at: string | null;
  // Orden de relevancia real (Acceso Honeyfile primero, después el
  // resto de las reglas "fuertes", después las demás; dentro de cada
  // nivel, mayor peso primero; en empate, más reciente primero) -- ver
  // sort_contributing_rules() en el servidor (2026-08-18, ver
  // PENDIENTES.md, "Corrección definitiva en la lógica y presentación
  // de ALERTAS"). Nunca depende del orden en que Postgres devolvía las
  // filas.
  rules: MatchedRule[];
  process: InvolvedProcess;
  timeline: TimelineEntry[];
  created_at: string | null;
  origin_alert: OriginAlert | null;
  // Agregados 2026-08-17 (ver PENDIENTES.md, "Aislamiento de host --
  // modo development, laboratorio y producción") -- para kind ===
  // 'incident' es siempre 'id'; para kind === 'alert' es el
  // incident_id de la alerta (o null si todavía no escaló). El botón
  // "Aislar" del drawer usa esto para saber a qué incidente asociar
  // la orden manual, y 'isolation_status' para saber si ya hay una en
  // curso/cumplida.
  isolatable_incident_id: number | null;
  isolation_status: string | null;
  // id de esa misma fila de host_isolations -- lo que necesita el
  // botón "Liberar" para llamar a POST /host-isolations/{id}/release
  // (mismo backend/máquina de estados que en todos los demás puntos
  // de entrada, sección 13 de "ALFA_SENTINEL — CORRECCIÓN DE TIEMPO
  // REAL...", 2026-08-17, ver PENDIENTES.md).
  isolation_id: number | null;
}
