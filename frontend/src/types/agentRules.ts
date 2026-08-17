// Tipos alineados 1:1 con GET/PATCH/DELETE /api/agents/{agent_id}/rules[/{rule_id}]
// (server/main.py::api_agent_rules / update_agent_rule / delete_agent_rule,
// 2026-08-16, ver PENDIENTES.md). Configuración de reglas heurísticas
// POR ENDPOINT -- reusa la tabla 'agent_rule' que ya existía, no crea
// ninguna tabla nueva. Distinto de types/rules.ts (que es la config
// GLOBAL, 'heuristic_rules'): acá cada regla trae su valor global, su
// override puntual (si existe) y el valor EFECTIVO ya resuelto por el
// servidor (COALESCE override -> global), para que la interfaz no
// tenga que calcular la herencia a mano.

export interface AgentRuleFieldSet {
  weight: number;
  threshold: number;
  window_seconds: number | null;
  is_active: boolean;
}

// A diferencia de AgentRuleFieldSet (valores globales/efectivos, que
// siempre están resueltos), acá weight/threshold/window_seconds
// pueden ser null INDIVIDUALMENTE -- significa "este endpoint no
// personalizó ese campo puntual, hereda el valor global solo para
// ese campo" (override parcial). 'is_active' nunca es null: la
// columna no admite NULL en la base (ver schema.sql), así que si
// 'override' no es null, is_active siempre trae un valor concreto.
export interface AgentRuleOverride {
  id: number;
  weight: number | null;
  threshold: number | null;
  window_seconds: number | null;
  is_active: boolean;
}

export interface AgentRuleItem {
  id: number;
  name: string;
  description: string | null;
  event_type_name: string | null;
  event_type_label: string;
  metric_type_name: string | null;
  global: AgentRuleFieldSet;
  override: AgentRuleOverride | null;
  effective: AgentRuleFieldSet;
  has_override: boolean;
  is_deferred: boolean;
  is_honeyfile: boolean;
  has_fixed_scoring: boolean;
}

export interface AgentRulesResponse {
  agent_id: number;
  hostname: string;
  rules: AgentRuleItem[];
}

// Semántica de PATCH parcial con NULL significativo (ver
// server/main.py::update_agent_rule / AgentRuleUpdate): un campo
// AUSENTE de este objeto no se toca; presente con 'null' vuelve a
// heredar el valor global para ESE campo puntual; presente con un
// valor concreto lo reemplaza. 'is_active' es la excepción -- nunca
// se manda en null (el servidor lo rechaza con 422).
export interface AgentRuleUpdatePayload {
  weight?: number | null;
  threshold?: number | null;
  window_seconds?: number | null;
  is_active?: boolean;
}

export interface AgentRuleUpdateResult {
  message: string;
  override: AgentRuleOverride;
}
