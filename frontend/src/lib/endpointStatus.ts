import type { CSSProperties } from "react";
import type { ConnStatus } from "../types/endpoints";

// Estado de conexión: regla única del servidor (agent_online_sql en
// server/main.py). En línea = heartbeat dentro de agent_stale_seconds;
// Sin comunicación = heartbeat vencido o nunca recibido (no presupone
// la causa); Aislado = aislamiento vigente, con prioridad.
//
// Es un eje aparte del
// riesgo -- usa la escala neutral/azul-rojo de conectividad, nunca
// los 4 colores de severidad (ver server/main.py, comentario en
// endpoints_page: "esta vista NO mezcla severidad de amenazas con el
// estado de conexión").

export const CONN_STATUS_LABEL: Record<ConnStatus, string> = {
  ONLINE: "En línea",
  OFFLINE: "Sin comunicación",
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

// Prioridad visual pedida: Crítico -> Aislado -> Alto -> Sospechoso ->
// Normal. Se usa para ordenar/realzar sin pintar la fila entera.
export const RISK_PRIORITY: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 2,
  SUSPICIOUS: 1,
  NORMAL: 0,
};
