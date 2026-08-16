import type { CSSProperties } from "react";
import type { Severity } from "../types/dashboard";

// Escala de color fija de todo el proyecto (ver server/main.py,
// RISK_COLOR_HEX, y la convención usada en el resto de la consola
// Jinja2): Bajo=Verde, Medio=Amarillo, Alto=Naranja, Crítico=Rojo. El
// rojo se reserva para Crítico -- no se usa en ningún otro lado de la
// UI.
//
// Etiquetas actualizadas 2026-08-16 a los 4 niveles que pide la
// especificación definitiva del motor heurístico (Bajo/Medio/Alto/
// Crítico, antes Normal/Sospechoso/Alto/Crítico) -- ver
// RISK_LABELS_ES/ALERT_SEVERITY_LABELS_ES en server/main.py. Los
// valores de 'Severity' (NORMAL/SUSPICIOUS/HIGH/CRITICAL) NO cambian,
// solo la traducción.
//
// Los valores de color en sí viven en los tokens Nocturne
// (index.css, --ok/--warn/--high/--crit) para que temas claro/oscuro
// los resuelvan solos -- acá solo se mapea Severity -> variable.

export const SEVERITY_LABEL: Record<Severity, string> = {
  NORMAL: "Bajo",
  SUSPICIOUS: "Medio",
  HIGH: "Alto",
  CRITICAL: "Crítico",
};

export const SEVERITY_VAR: Record<Severity, string> = {
  NORMAL: "var(--ok)",
  SUSPICIOUS: "var(--warn)",
  HIGH: "var(--high)",
  CRITICAL: "var(--crit)",
};

export const SEVERITY_SOFT_VAR: Record<Severity, string> = {
  NORMAL: "var(--ok-soft)",
  SUSPICIOUS: "var(--warn-soft)",
  HIGH: "var(--high-soft)",
  CRITICAL: "var(--crit-soft)",
};

// Pill sólida (fondo de color, texto blanco) -- para el badge de
// nivel en tablas/tarjetas, igual que el mockup ("CRÍTICO" en rojo
// sólido, el resto con fondo suave).
export function severityPillStyle(sev: Severity): CSSProperties {
  if (sev === "CRITICAL") {
    return { background: "var(--crit)", color: "#fff" };
  }
  return { background: SEVERITY_SOFT_VAR[sev], color: SEVERITY_VAR[sev] };
}
