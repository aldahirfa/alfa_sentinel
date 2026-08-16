// Tipos alineados 1:1 con GET /api/respuesta (server/main.py).
//
// Desde el motor heurístico definitivo (2026-08-16), 'host_isolations'
// SÍ puede tener filas reales con status='RECOMMENDED': el servidor
// evalúa la condición de aislamiento (sección 30 de la especificación)
// y deja constancia de que se cumplió, pero no ejecuta nada -- el
// agente sigue sin tener canal de comandos remotos (agent/main.py es
// de una sola pasada). Un aislamiento REQUESTED/EXECUTED de verdad
// seguiría siendo manual, fuera de la consola.

import type { Severity } from "./dashboard";

export interface RespuestaSummary {
  isolated_now: number;
  total_isolations: number;
  critical_incidents_open: number;
}

export interface CriticalIncidentItem {
  id: number;
  code: string;
  title: string;
  status: string;
  status_label: string;
  opened_at: string | null;
  hostname: string;
  assigned_to: number | null;
  assigned_to_name: string | null;
  severity: Severity | null;
  severity_label: string;
}

// 'isolation_type'/'status' siguen siendo VARCHAR libre (sin CHECK
// constraint), pero desde el motor heurístico definitivo (2026-08-16)
// el servidor sí puede escribir acá (status='RECOMMENDED', ver
// server/main.py::report_alert) y ahora traduce ambos campos igual
// que alerts.status/incidents.status (ISOLATION_STATUS_LABELS_ES /
// ISOLATION_TYPE_LABELS_ES).
export interface IsolationRecord {
  id: number;
  isolation_type: string;
  isolation_type_label: string;
  status: string;
  status_label: string;
  reason: string | null;
  requested_at: string | null;
  executed_at: string | null;
  released_at: string | null;
  result: string | null;
  hostname: string;
  requested_by_name: string | null;
  incident_id: number;
}

export interface RespuestaResponse {
  summary: RespuestaSummary;
  critical_incidents: CriticalIncidentItem[];
  isolations: IsolationRecord[];
}
