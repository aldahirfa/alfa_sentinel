// Tipos alineados 1:1 con GET /api/respuesta (server/main.py).
//
// Desde la corrección definitiva del motor heurístico (2026-08-17, ver
// PENDIENTES.md), el aislamiento AUTOMÁTICO es real de punta a punta:
// cuando se cumple la condición (sección 30 de la especificación),
// server/main.py::report_alert() deja una orden 'REQUESTED' en
// 'host_isolations'; el agente de ese endpoint la recoge (polling,
// agent/isolation_sync.py) y la ejecuta (agent/isolation_executor.py),
// confirmando 'EXECUTED' o 'ISOLATION_FAILED'.
//
// Extendido 2026-08-17 (ver PENDIENTES.md, "Aislamiento de host --
// modo development, laboratorio y producción"): el disparo MANUAL
// (POST /incidents/{id}/isolate) usa exactamente el mismo mecanismo,
// más la operación inversa UNISOLATE (POST /host-isolations/{id}/release).
// La ejecución real vs. simulada depende de ALFA_SENTINEL_ENV
// (development=simulado, controlled_test/production=real) -- ver
// agent/isolation_executor.py.

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
  // Estado más reciente de aislamiento para este incidente (null si
  // nunca se ordenó ninguno) -- decide si el botón "Aislar" de la
  // tabla está disponible o ya hay una orden en curso/cumplida.
  isolation_status: string | null;
  // id de esa misma fila de host_isolations -- lo que necesita el
  // botón "Liberar" para llamar a POST /host-isolations/{id}/release.
  isolation_id: number | null;
}

// 'isolation_type'/'status' siguen siendo VARCHAR libre (sin CHECK
// constraint) -- los valores válidos de 'status' son REQUESTED,
// EXECUTED, ISOLATION_FAILED, RELEASE_REQUESTED, RELEASED (y
// RECOMMENDED como legado, ver server/main.py::ISOLATION_STATUS_LABELS_ES),
// que el servidor traduce igual que alerts.status/incidents.status.
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
