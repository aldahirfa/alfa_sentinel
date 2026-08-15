// Tipos alineados 1:1 con GET /api/respuesta (server/main.py) -- la
// versión JSON del placeholder honesto que hoy vive en /respuesta
// (Jinja2). No hay respuesta automática real todavía: 'host_isolations'
// existe en el schema pero ningún endpoint escribe ahí (el agente no
// tiene canal de comandos remotos). Esta pantalla no inventa un botón
// de aislamiento que funcione -- muestra lo real: el historial (vacío
// hoy) y los incidentes críticos abiertos que sí requieren contención
// manual, fuera de la consola.

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

// 'isolation_type'/'status' no tienen un vocabulario fijo en el
// código (VARCHAR libre, sin CHECK constraint, y nada lo escribe
// nunca todavía) -- se muestran tal cual, sin traducir, a diferencia
// de alerts.status/incidents.status que sí tienen una tabla de
// etiquetas en español definida en el servidor.
export interface IsolationRecord {
  id: number;
  isolation_type: string;
  status: string;
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
