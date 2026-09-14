// Tipos alineados 1:1 con las APIs de respuesta del servidor.

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
  isolation_status: string | null;
  isolation_id: number | null;
}

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

export interface ResponseEndpointSummary {
  total_endpoints: number;
  isolated_now: number;
  pending_now: number;
  with_history: number;
}

export interface ResponseEndpointItem {
  agent_id: number;
  hostname: string;
  operating_system: string;
  os_version: string;
  ip_address: string;
  agent_status: string;
  last_seen_at: string | null;
  isolation_id: number | null;
  isolation_status: string | null;
  isolation_status_label: string;
  latest_action_at: string | null;
  active_incident_id: number | null;
  incident_count: number;
  isolation_count: number;
}

export interface ResponseEndpointsResponse {
  summary: ResponseEndpointSummary;
  endpoints: ResponseEndpointItem[];
}

export interface ResponseEndpointIncident {
  id: number;
  code: string;
  title: string;
  status: string;
  status_label: string;
  opened_at: string | null;
  closed_at: string | null;
  assigned_to_name: string | null;
  severity: Severity | null;
  risk_score: number;
  detection_count: number;
}

export interface ResponseEndpointIsolation {
  id: number;
  status: string;
  status_label: string;
  reason: string | null;
  requested_at: string | null;
  executed_at: string | null;
  released_at: string | null;
  result: string | null;
  requested_by_name: string | null;
  incident_id: number;
}

export interface ResponseEndpointDetailInfo {
  agent_id: number;
  hostname: string;
  operating_system: string;
  os_version: string;
  ip_address: string;
  agent_status: string;
  last_seen_at: string | null;
  agent_version: string | null;
  isolation_id: number | null;
  isolation_status: string | null;
  isolation_status_label: string;
  active_incident_id: number | null;
}

export interface ResponseEndpointDetail {
  endpoint: ResponseEndpointDetailInfo;
  summary: {
    incidents_total: number;
    isolations_total: number;
    isolated_now: boolean;
  };
  incidents: ResponseEndpointIncident[];
  isolations: ResponseEndpointIsolation[];
}
