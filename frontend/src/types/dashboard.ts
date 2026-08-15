// Tipos alineados 1:1 con lo que devuelven server/main.py::api_dashboard_overview
// y api_dashboard_activity_series. Si el contrato del backend cambia,
// este archivo es el primer lugar a actualizar.

export type Severity = "NORMAL" | "SUSPICIOUS" | "HIGH" | "CRITICAL";

export interface DashboardSummary {
  endpoints_total: number;
  endpoints_online: number;
  endpoints_offline: number;
  endpoints_isolated: number;
  alerts_active: number;
  alerts_trend_pct: number | null;
  incidents_active: number;
  honeyfiles_activated_today: number;
}

export interface RiskDistributionItem {
  level: Severity;
  label: string;
  count: number;
  color: string;
}

export interface EndpointAtRisk {
  hostname: string;
  os: string;
  status: string;
  last_seen_ago: string;
  severity: Severity;
  alerts_count: number;
}

export interface RecentAlert {
  id: number;
  severity: Severity;
  title: string;
  hostname: string;
  process: string | null;
  time: string;
  status: string;
}

export interface HoneyfileRecent {
  hostname: string;
  time: string;
  file_name: string | null;
}

export interface HoneyfileActivity {
  active_total: number;
  activated_today: number;
  recent: HoneyfileRecent[];
}

export interface EndpointStatus {
  online: number;
  offline: number;
  isolated: number;
  agent_health_pct: number;
}

export interface TopDetection {
  rule_name: string;
  rule_label: string;
  count: number;
}

export interface RecentActivityItem {
  kind: "alert" | "honeyfile_created" | "endpoint_registered";
  severity: Severity | null;
  type_label: string;
  label: string;
  hostname: string;
  time: string;
  ago: string;
}

export interface SystemStatus {
  api_ok: boolean;
  db_ok: boolean;
  agents_comm_ok: boolean;
  detection_engine_ok: boolean;
  agents_connected: number;
  agents_total: number;
  last_sync_ago: string;
}

export interface DashboardOverview {
  db_ok: boolean;
  generated_at: string;
  summary: DashboardSummary;
  risk_distribution: RiskDistributionItem[];
  endpoints_at_risk: EndpointAtRisk[];
  recent_alerts: RecentAlert[];
  honeyfile_activity: HoneyfileActivity;
  endpoint_status: EndpointStatus;
  top_detections: TopDetection[];
  recent_activity: RecentActivityItem[];
  system_status: SystemStatus;
}

export type ActivityRange = "24h" | "7d" | "30d";

export interface ActivitySeriesPoint {
  bucket: string;
  alerts: number;
  activity: number;
  incidents: number;
  honeyfiles: number;
}

export interface ActivitySeriesResponse {
  range: ActivityRange;
  points: ActivitySeriesPoint[];
}
