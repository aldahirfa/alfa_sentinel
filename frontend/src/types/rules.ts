// Tipos alineados 1:1 con GET /api/rules y PATCH /rules/{id}
// (server/main.py). Solo 'weight' e 'is_active' se muestran editables
// en la UI -- son los únicos dos campos que configuracion.html (la
// consola real) también deja tocar; 'threshold'/'window_seconds' son
// reales pero se muestran de solo lectura a propósito, para que esta
// pantalla sea "comprensible, no una consola técnica".

export interface HeuristicRule {
  id: number;
  name: string;
  label: string;
  description: string | null;
  weight: number;
  threshold: number;
  window_seconds: number;
  is_active: boolean;
  updated_at: string | null;
  event_type_label: string;
  alerts_30d: number;
  last_triggered_at: string | null;
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
}

export interface RuleUpdateResult {
  message: string;
  rule_id: number;
  name: string;
  weight: number;
  is_active: boolean;
  threshold: number;
  window_seconds: number;
}
