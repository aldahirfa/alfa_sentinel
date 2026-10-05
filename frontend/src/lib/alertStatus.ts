import type { CSSProperties } from "react";
import type { AlertStatus, AlertStatusFilter } from "../types/alerts";

// Estado del flujo de trabajo de una alerta (Nueva/En investigación/
// Confirmada/Cerrada/Falso positivo) es un eje aparte de la severidad
// -- usa la escala neutral/informativa (--info, --off, --brand), nunca
// los 4 colores de severidad (Verde/Amarillo/Naranja/Rojo), que se
// reservan exclusivamente para el nivel de riesgo.

export const STATUS_LABEL: Record<AlertStatus, string> = {
  NEW: "Pendiente",
  ESCALATED: "Escalada",
  FALSE_POSITIVE: "Descartada · falso positivo",
  LEGITIMATE_ACTIVITY: "Descartada · actividad legítima",
};

export const STATUS_FILTER_LABEL: Record<AlertStatusFilter, string> = {
  NEW: "Pendiente",
  ESCALATED: "Escalada",
  DISCARDED: "Descartada",
};

export const STATUS_VAR: Record<AlertStatus, string> = {
  NEW: "var(--info)",
  ESCALATED: "var(--brand)",
  FALSE_POSITIVE: "var(--off)",
  LEGITIMATE_ACTIVITY: "var(--off)",
};

export function statusPillStyle(status: AlertStatus): CSSProperties {
  if (status === "NEW") {
    return { background: "var(--info-soft)", color: "var(--info)" };
  }
  if (status === "ESCALATED") {
    return { background: "var(--brand-soft)", color: "var(--brand)" };
  }
  return { border: "1px solid var(--line)", color: "var(--tx-mute)" };
}
