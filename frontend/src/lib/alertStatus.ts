import type { CSSProperties } from "react";
import type { AlertStatus } from "../types/alerts";

// Estado del flujo de trabajo de una alerta (Nueva/En investigación/
// Confirmada/Cerrada/Falso positivo) es un eje aparte de la severidad
// -- usa la escala neutral/informativa (--info, --off, --brand), nunca
// los 4 colores de severidad (Verde/Amarillo/Naranja/Rojo), que se
// reservan exclusivamente para el nivel de riesgo.

export const STATUS_LABEL: Record<AlertStatus, string> = {
  NEW: "Nueva",
  ACKNOWLEDGED: "En investigación",
  ESCALATED: "Confirmada",
  CLOSED: "Cerrada",
  FALSE_POSITIVE: "Falso positivo",
};

export const STATUS_VAR: Record<AlertStatus, string> = {
  NEW: "var(--info)",
  ACKNOWLEDGED: "var(--info)",
  ESCALATED: "var(--brand)",
  CLOSED: "var(--off)",
  FALSE_POSITIVE: "var(--off)",
};

export function statusPillStyle(status: AlertStatus): CSSProperties {
  if (status === "NEW") {
    return { background: "var(--info-soft)", color: "var(--info)" };
  }
  if (status === "ESCALATED") {
    return { background: "var(--brand-soft)", color: "var(--brand)" };
  }
  if (status === "ACKNOWLEDGED") {
    return { border: "1px solid var(--info)", color: "var(--info)" };
  }
  return { border: "1px solid var(--line)", color: "var(--tx-mute)" };
}
