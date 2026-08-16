// Tipos alineados 1:1 con lo que devuelven server/main.py::api_alerts
// (GET /api/alerts) y get_incidente_drawer (GET
// /api/incidentes/alert/{id}/drawer, reusado tal cual para el drawer
// de una alerta suelta -- no se creó un endpoint de detalle nuevo).

import type { Severity } from "./dashboard";

export type AlertStatus = "NEW" | "ACKNOWLEDGED" | "ESCALATED" | "CLOSED" | "FALSE_POSITIVE";

export interface AlertListItem {
  id: number;
  severity: Severity;
  severity_label: string;
  title: string;
  hostname: string;
  risk_score: number;
  status: AlertStatus;
  status_label: string;
  created_at: string;
  incident_id: number | null;
  rule_name: string | null;
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
  severity_label: string;
  risk_score: number | null;
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
  severity_label: string;
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
  rules: MatchedRule[];
  timeline: TimelineEntry[];
  created_at: string | null;
  origin_alert: OriginAlert | null;
}
