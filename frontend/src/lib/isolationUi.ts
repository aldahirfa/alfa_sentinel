// Textos/iconos/confirmación ÚNICOS para la acción de aislamiento
// (2026-08-18, ver PENDIENTES.md, "Revisión y corrección integral de
// ALFA-Sentinel", problema I: "unificar el componente visual -- no
// tener dos implementaciones HTML distintas si representan la misma
// acción").
//
// Antes cada pantalla tenía su propio texto escrito a mano y habían
// divergido: IncidentDrawer.tsx decía "Aislar endpoint",
// EndpointDrawer.tsx decía "Aislar endpoint manualmente",
// IncidentesTable.tsx decía "Aislar equipo", CriticalIncidentsTable.tsx
// decía solo "Aislar" -- los 4 disparan exactamente la MISMA acción real
// (POST /incidents/{id}/isolate, el mismo mecanismo de backend/agente).
// Este archivo es la única fuente de esos textos: quien necesite mostrar
// el botón de aislar/liberar/pendiente importa de acá, no escribe el
// string de nuevo. No es un componente React (los 4 lugares tienen
// layout/tamaño distintos por el espacio real disponible -- un botón de
// 'drawer' de ancho completo vs. una celda de tabla compacta -- pero
// texto, icono, color, tooltip y mensaje de confirmación no deben
// volver a divergir).
//
// Colores: se mantienen los ya usados en todo el sistema --
// var(--crit) para "Aislar"/"Aislado" (acción/estado de alto impacto),
// var(--warn) para "Liberar"/"En curso" (Liberar es lo opuesto de
// aislar, no una acción de riesgo -- nunca rojo).

import type { CSSProperties } from "react";

// Botón "Aislar" compacto (celdas de tabla) -- ÚNICA fuente del
// fondo/borde/tamaño (2026-08-18, ver PENDIENTES.md, "cosas a
// corregir": "el boton de aislar de la pantalla no es igual a la de
// incidentes, no tienen el mismo background"). Antes IncidentesTable.tsx
// usaba una píldora rellena (borde + fondo var(--crit-soft)) y
// CriticalIncidentsTable.tsx usaba un link de texto plano sin fondo --
// misma acción, dos apariencias distintas. Ambas tablas ahora importan
// estas 2 constantes en vez de escribir su propio className/style.
export const ISOLATE_BUTTON_CLASS_COMPACT =
  "flex items-center gap-1.5 text-[11.5px] font-bold px-2 py-1 rounded cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 whitespace-nowrap transition-premium btn-hover";
export const ISOLATE_BUTTON_STYLE_COMPACT: CSSProperties = {
  border: "1px solid var(--crit)",
  color: "var(--crit)",
  background: "var(--crit-soft)",
};

export const ISOLATE_ICON_CLASS = "ph ph-plugs";
export const ISOLATED_ICON_CLASS = "ph-fill ph-plugs";
export const RELEASE_ICON_CLASS = "ph ph-plug";
export const PENDING_ICON_CLASS = "ph-fill ph-hourglass-medium";
export const SPINNER_ICON_CLASS = "ph ph-circle-notch animate-spin";

// Variante completa -- drawers y paneles con espacio para una oración.
export const ISOLATE_LABEL_FULL = "Aislar endpoint";
export const ISOLATED_LABEL_FULL = "Endpoint aislado";
export const RELEASE_LABEL_FULL = "Liberar endpoint";
export const PENDING_LABEL_FULL = "Orden enviada -- esperando confirmación del agente";

// Variante compacta -- celdas de tabla, sin espacio para una oración
// completa (mismo significado, texto más corto).
export const ISOLATE_LABEL_COMPACT = "Aislar";
export const ISOLATED_LABEL_COMPACT = "Aislado";
export const RELEASE_LABEL_COMPACT = "Liberar";
export const PENDING_LABEL_COMPACT = "En curso";

export const SENDING_LABEL = "Enviando...";

export const ISOLATE_TOOLTIP = "Envía la orden de aislamiento real al agente de este endpoint.";
export const RELEASE_TOOLTIP = "Envía la orden de liberación real al agente de este endpoint.";

// Confirmación (2026-08-18, problema I: "confirmación" es parte del
// comportamiento unificado que se pidió) -- aislar corta la
// conectividad real del endpoint, así que las 4 pantallas piden
// confirmación con el MISMO texto antes de disparar la orden. Se usa
// window.confirm() a propósito -- no se agrega una librería de modales
// nueva solo para esto (mismo criterio de "no rehacer arquitectura").
export function confirmIsolate(hostname?: string | null): boolean {
  const target = hostname ? `"${hostname}"` : "este endpoint";
  return window.confirm(
    `¿Aislar ${target} de la red ahora?\n\nEsto corta su conectividad real hasta que se libere manualmente.`
  );
}
