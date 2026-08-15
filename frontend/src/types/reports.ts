// Tipos alineados 1:1 con GET /api/reportes, POST /reportes/generar y
// GET /reportes/{id}/archivo (server/main.py) -- estos dos últimos ya
// existían y los usaba reportes.html, se reusan tal cual.

export type ReportType = "SECURITY" | "ENDPOINTS" | "INCIDENTS";
export type ReportFormat = "PDF" | "XLSX";
export type ReportPeriod = "7d" | "30d" | "90d" | "all";

export interface ReportOption {
  value: string;
  label: string;
}

export interface EndpointOption {
  id: number;
  hostname: string;
}

export interface ReportHistoryItem {
  id: number;
  code: string;
  title: string;
  report_type: ReportType;
  report_type_label: string;
  format: ReportFormat;
  period_label: string;
  created_at: string;
  endpoint: string;
  generated_by: string;
}

export interface ReportsResponse {
  total_reports: number;
  last_generated_at: string | null;
  last_generated_by: string | null;
  endpoint_options: EndpointOption[];
  report_type_options: ReportOption[];
  period_options: ReportOption[];
  history: ReportHistoryItem[];
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GenerateReportPayload {
  report_type: ReportType;
  period: ReportPeriod;
  format: ReportFormat;
  endpoint_id: number | null;
}

export interface GenerateReportResult {
  message: string;
  report: {
    id: number;
    code: string;
    title: string;
    report_type_label: string;
    format: ReportFormat;
    period_label: string;
    endpoint: string;
    generated_by: string;
    created_at: string;
  };
}
