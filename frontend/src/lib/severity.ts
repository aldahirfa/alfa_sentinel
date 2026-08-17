import type { CSSProperties } from "react";
import type { Severity } from "../types/dashboard";

// Escala de color fija de todo el proyecto (ver server/main.py,
// RISK_COLOR_HEX): Bajo=Verde, Medio=Amarillo, Alto=Naranja,
// Crítico=Rojo. El rojo se reserva para Crítico -- no se usa en
// ningún otro lado de la UI.
//
// SEVERITY_LABEL se eliminó (2026-08-16, corrección arquitectónica:
// "si un dato existe en un catálogo de PostgreSQL, ese dato es la
// fuente de verdad"). 'Severity' ya son los 4 nombres reales de
// severity_levels.name en español (BAJO/MEDIO/ALTO/CRÍTICO,
// renombrados en la BD -- ver PENDIENTES.md) -- lo que llega de la
// API se muestra tal cual, sin traducir. Lo único que sigue siendo
// decisión de esta capa (presentación legítima, no un dato) es qué
// color/variable CSS le corresponde a cada nombre.
//
// Los valores de color en sí viven en los tokens Nocturne
// (index.css, --ok/--warn/--high/--crit) para que temas claro/oscuro
// los resuelvan solos -- acá solo se mapea Severity -> variable.

export const SEVERITY_VAR: Record<Severity, string> = {
  BAJO: "var(--ok)",
  MEDIO: "var(--warn)",
  ALTO: "var(--high)",
  CRÍTICO: "var(--crit)",
};

export const SEVERITY_SOFT_VAR: Record<Severity, string> = {
  BAJO: "var(--ok-soft)",
  MEDIO: "var(--warn-soft)",
  ALTO: "var(--high-soft)",
  CRÍTICO: "var(--crit-soft)",
};

// Pill sólida (fondo de color, texto blanco) -- para el badge de
// nivel en tablas/tarjetas, igual que el mockup ("CRÍTICO" en rojo
// sólido, el resto con fondo suave).
export function severityPillStyle(sev: Severity): CSSProperties {
  if (sev === "CRÍTICO") {
    return { background: "var(--crit)", color: "#fff" };
  }
  return { background: SEVERITY_SOFT_VAR[sev], color: SEVERITY_VAR[sev] };
}
