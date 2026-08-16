// Tipos alineados 1:1 con GET /api/rules y PATCH /rules/{id}
// (server/main.py). Pantalla ampliada 2026-08-16 (ver PENDIENTES.md)
// para mostrar el modelo heurístico completo -- métrica, evento,
// parámetros, actividad y auditoría -- no solo nombre + peso + estado.

export interface HeuristicRule {
  id: number;
  name: string;
  label: string;
  description: string | null;
  weight: number;
  threshold: number;
  window_seconds: number | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;

  event_type_name: string | null;
  event_type_label: string;
  event_type_description: string | null;

  metric_type_name: string | null;
  metric_type_description: string | null;
  metric_unit: string | null;

  alerts_30d: number;
  last_triggered_at: string | null;

  // Calculados por el servidor (misma fuente de verdad que valida
  // PATCH /rules/{id}) -- evita duplicar estos sets acá.
  is_deferred: boolean;
  is_honeyfile: boolean;
  has_fixed_scoring: boolean;
}

export interface RulesSummary {
  total: number;
  active: number;
  inactive: number;
  alerts_30d_total: number;
}

export interface RulesResponse {
  summary: RulesSummary;
  rules: HeuristicRule[];
}

export interface RuleUpdatePayload {
  weight?: number;
  is_active?: boolean;
  threshold?: number;
  window_seconds?: number;
}

export interface RuleUpdateResult {
  message: string;
  rule_id: number;
  name: string;
  weight: number;
  is_active: boolean;
  threshold: number;
  window_seconds: number | null;
  updated_at: string | null;
}
