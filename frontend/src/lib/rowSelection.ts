import type { CSSProperties } from "react";

// Estilo compartido por todas las tablas con drawer de detalle, para
// que el registro abierto en el drawer se sienta "seleccionado/activo"
// -- mismo lenguaje visual que ya usa el ítem activo del sidebar
// (fondo var(--brand-soft) + barra izquierda var(--brand), ver
// Sidebar.tsx). Dos capas:
//  - `isFlashing`: resaltado fuerte, solo los primeros segundos tras
//    seleccionar (useRowFlash.ts controla la duración). Se desvanece
//    solo, vía la transición de `background`.
//  - `isSelected`: indicador persistente y sutil (solo la barra
//    izquierda) mientras el drawer de ese registro siga abierto.
// El borde siempre está presente (transparente si no aplica) para que
// activarlo no mueva el contenido de la fila un par de píxeles.
export function rowSelectionStyle(isSelected: boolean, isFlashing: boolean): CSSProperties {
  return {
    background: isFlashing ? "var(--brand-soft)" : "transparent",
    borderLeft: isSelected ? "2px solid var(--brand)" : "2px solid transparent",
    transition: "background-color 2.5s ease",
  };
}
