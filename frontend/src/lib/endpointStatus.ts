import type { CSSProperties } from "react";
import type { AgentHealth, ConnStatus } from "../types/endpoints";

// Estado de conexión (Online/Offline/Aislado) es un eje aparte del
// riesgo -- usa la escala neutral/azul-rojo de conectividad, nunca
// los 4 colores de severidad (ver server/main.py, comentario en
// endpoints_page: "esta vista NO mezcla severidad de amenazas con el
// estado de conexión").

export const CONN_STATUS_LABEL: Record<ConnStatus, string> = {
  ONLINE: "Online",
  OFFLINE: "Offline",
  ISOLATED: "Aislado",
};

export const CONN_STATUS_VAR: Record<ConnStatus, string> = {
  ONLINE: "var(--ok)",
  OFFLINE: "var(--off)",
  ISOLATED: "var(--crit)",
};

export function connStatusPillStyle(status: ConnStatus): CSSProperties {
  if (status === "ISOLATED") {
    return { background: "var(--crit)", color: "#fff" };
  }
  return { border: "1px solid var(--line)", color: "var(--tx-dim)" };
}

export const AGENT_HEALTH_LABEL: Record<AgentHealth, string> = {
  HEALTHY: "Healthy",
  WARNING: "Warning",
  OFFLINE: "Offline",
};

export const AGENT_HEALTH_VAR: Record<AgentHealth, string> = {
  HEALTHY: "var(--ok)",
  WARNING: "var(--warn)",
  OFFLINE: "var(--off)",
};

// Prioridad visual pedida: Crítico -> Aislado -> Alto -> Sospechoso ->
// Normal. Se usa para ordenar/realzar sin pintar la fila entera.
export const RISK_PRIORITY: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 2,
  SUSPICIOUS: 1,
  NORMAL: 0,
};
